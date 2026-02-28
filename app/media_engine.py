"""
Media Engine - Integrates Imagen, Veo, and Gemini TTS for media generation
"""

import os
import asyncio
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()

# Mock Google Cloud imports for development
try:
    from google.cloud import storage
    from google.cloud import texttospeech
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None
    texttospeech = None

# Vertex image generation (Imagen)
try:
    from vertexai.preview.vision_models import ImageGenerationModel
    IMAGEN_AVAILABLE = True
except ImportError:
    IMAGEN_AVAILABLE = False
    ImageGenerationModel = None

# Vertex-compatible GenAI client (Veo)
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    genai_types = None


import structlog

logger = structlog.get_logger(__name__)


def ensure_bucket_exists(storage_client, bucket_name: str, location: str = "us-central1"):
    """Create bucket if it doesn't exist"""
    try:
        bucket = storage_client.bucket(bucket_name)
        if bucket.exists():
            return bucket
        
        # Create the bucket
        bucket.location = location
        bucket.create()
        logger.info(f"Created bucket: {bucket_name}")
        return bucket
    except Exception as e:
        logger.warning(f"Could not create bucket {bucket_name}: {e}")
        return None


def _to_public_storage_url(uri: str) -> str:
    """Normalize GCS URI into https://storage.googleapis.com URL."""
    if uri.startswith("gs://"):
        without_scheme = uri[len("gs://"):]
        bucket, _, blob_path = without_scheme.partition("/")
        if not bucket:
            return uri
        if not blob_path:
            return f"https://storage.googleapis.com/{bucket}"
        return f"https://storage.googleapis.com/{bucket}/{quote(blob_path, safe='/')}"
    return uri


def _parse_gcs_uri(uri: str) -> Optional[Tuple[str, str]]:
    """Parse gs://bucket/path or https://storage.googleapis.com/bucket/path."""
    if uri.startswith("gs://"):
        without_scheme = uri[len("gs://"):]
        bucket, _, blob_path = without_scheme.partition("/")
        if bucket and blob_path:
            return bucket, blob_path
        return None

    if uri.startswith("https://storage.googleapis.com/"):
        without_host = uri[len("https://storage.googleapis.com/"):]
        bucket, _, blob_path = without_host.partition("/")
        if bucket and blob_path:
            return bucket, blob_path
        return None

    return None


def _save_bytes_local(base_dir: str, relative_path: str, content: bytes):
    """Save bytes to local output folder, preserving subdirectories."""
    local_path = Path(base_dir) / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    return str(local_path)


class ImageGenerator:
    """Generates images using Imagen"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        self.local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "local_media")
        
        if GCS_AVAILABLE:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.storage_client = None
            self.bucket = None
        
        # Try to initialize Vertex AI for Imagen
        self.imagen_model = None
        if IMAGEN_AVAILABLE and ImageGenerationModel:
            try:
                import vertexai
                vertexai.init(project=project_id, location=location)
                self.imagen_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
                logger.info("Initialized Imagen model", project=project_id)
            except Exception as e:
                logger.warning(f"Failed to initialize Imagen: {e}")
        
        logger.info("Initialized ImageGenerator", project=project_id, bucket=self.bucket_name)
    
    async def generate(
        self,
        prompt: str,
        style: str = "illustration",
        aspect_ratio: str = "16:9"
    ) -> str:
        """
        Generate an image using Imagen.
        
        Args:
            prompt: Text description of the image
            style: Image style (illustration, photo, etc.)
            aspect_ratio: Aspect ratio of the image
            
        Returns:
            GCS URL of the generated image
        """
        # Return mock URL if no bucket available
        if not self.bucket:
            logger.warning("No bucket available, returning mock image URL")
            return f"https://via.placeholder.com/1280x720.png?text=Story+Image+Placeholder"
        
        # Try to use Imagen
        if self.imagen_model:
            try:
                full_prompt = f"{prompt}. Style: {style}, educational, child-friendly."
                logger.info("Generating image with Imagen", prompt_length=len(full_prompt))
                
                images = self.imagen_model.generate_images(
                    prompt=full_prompt,
                    number_of_images=1,
                    aspect_ratio=aspect_ratio
                )
                
                if images:
                    filename = f"storyboards/{uuid.uuid4()}.png"
                    # Use public SDK method instead of private internals.
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        temp_path = tmp.name
                    try:
                        images[0].save(temp_path, include_generation_parameters=False)
                        with open(temp_path, "rb") as f:
                            image_bytes = f.read()
                        gcs_url = await self._upload_to_gcs(image_bytes, filename)
                        logger.info("Image generated and uploaded", gcs_url=gcs_url)
                        return gcs_url
                    finally:
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
            except Exception as e:
                logger.warning(f"Imagen generation failed: {e}")
        
        # Fallback to mock URL
        logger.warning("Returning mock image URL")
        return f"https://via.placeholder.com/1280x720.png?text=Story+Image+Placeholder"
    
    async def _upload_to_gcs(self, image_bytes: bytes, filename: str) -> str:
        """Upload image bytes to Google Cloud Storage"""
        local_path = _save_bytes_local(self.local_output_dir, filename, image_bytes)
        logger.info("Saved image locally", local_path=local_path)

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(image_bytes, content_type="image/png")
        
        # Generate public URL directly (bucket must be publicly readable)
        return _to_public_storage_url(f"gs://{self.bucket_name}/{filename}")


class VoiceGenerator:
    """Generates voiceover using Gemini 2.5 Flash-TTS"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        self.local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "local_media")
        
        if GCS_AVAILABLE:
            self.client = texttospeech.TextToSpeechClient()
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.client = None
            self.storage_client = None
            self.bucket = None
        
        logger.info("Initialized VoiceGenerator", project=project_id, bucket=self.bucket_name)
        
        logger.info("Initialized VoiceGenerator", project=project_id)
    
    async def generate(
        self,
        text: str,
        voice: str = "male",
        emotion: str = "warm",
        language: str = "auto"
    ) -> str:
        """
        Generate voiceover audio using Gemini TTS.
        
        Args:
            text: Text to convert to speech
            voice: Voice type (male, female, neutral)
            emotion: Emotional tone
            language: Language code (auto-detect if "auto")
            
        Returns:
            GCS URL of the generated audio
        """
        # Auto-detect language from text
        if language == "auto":
            language = self._detect_language(text)
        
        # Return mock URL if no bucket available
        if not self.bucket:
            logger.warning("No bucket available, returning mock audio URL")
            return f"https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"
        
        # Return mock URL for development
        if not GCS_AVAILABLE or not self.client:
            logger.warning("Google Cloud TTS not available, returning mock audio URL")
            return f"https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Get voice name based on language and gender
        voice_name = self._get_voice_name(language, voice)
        
        # Configure voice
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=voice_name
        )
        
        # Adjust audio config based on emotion
        speaking_rate = self._get_speaking_rate(emotion)
        pitch = self._get_pitch(emotion)
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch
        )
        
        logger.info("Generating voiceover", text_length=len(text), emotion=emotion, language=language)
        
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )
        
        # Save to GCS
        filename = f"voiceovers/{uuid.uuid4()}.mp3"
        gcs_url = await self._upload_to_gcs(response.audio_content, filename)
        
        logger.info("Voiceover generated and uploaded", gcs_url=gcs_url)
        return gcs_url
    
    def _detect_language(self, text: str) -> str:
        """Auto-detect language from text"""
        # Simple language detection based on common words
        text_lower = text.lower()
        
        # Arabic indicators
        arabic_indicators = ['في', 'من', 'إلى', 'هذا', 'تلك', 'التي', 'الذي', 'كان', 'هو', 'هي', 'و', 'أو', 'هل']
        if any(word in text_lower for word in arabic_indicators):
            return "ar-SA"
        
        # French indicators
        french_indicators = ['le', 'la', 'les', 'un', 'une', 'des', 'et', 'est', 'sont', 'avec', 'pour', 'dans', 'ce', 'cette']
        if any(word in text_lower for word in french_indicators):
            return "fr-FR"
        
        # Spanish indicators
        spanish_indicators = ['el', 'la', 'los', 'las', 'un', 'una', 'es', 'son', 'con', 'para', 'en', 'que', 'como']
        if any(word in text_lower for word in spanish_indicators):
            return "es-ES"
        
        # German indicators
        german_indicators = ['der', 'die', 'das', 'und', 'ist', 'sind', 'mit', 'für', 'ein', 'eine', 'zu', 'auf']
        if any(word in text_lower for word in german_indicators):
            return "de-DE"
        
        # Default to English
        return "en-US"
    
    def _get_voice_name(self, language: str, voice_type: str = "male") -> str:
        """Get valid voice name based on language and gender"""
        # Standard Google Cloud TTS voices
        voices = {
            "en-US": {
                "male": "en-US-Neural2-J",
                "female": "en-US-Neural2-F",
                "neutral": "en-US-Neural2-D"
            },
            "ar-SA": {
                "male": "ar-SA-Neural2-A",
                "female": "ar-SA-Neural2-B",
                "neutral": "ar-SA-Neural2-A"
            },
            "fr-FR": {
                "male": "fr-FR-Neural2-D",
                "female": "fr-FR-Neural2-E",
                "neutral": "fr-FR-Neural2-D"
            },
            "es-ES": {
                "male": "es-ES-Neural2-D",
                "female": "es-ES-Neural2-F",
                "neutral": "es-ES-Neural2-D"
            },
            "de-DE": {
                "male": "de-DE-Neural2-C",
                "female": "de-DE-Neural2-F",
                "neutral": "de-DE-Neural2-C"
            }
        }
        
        lang_voices = voices.get(language, voices["en-US"])
        return lang_voices.get(voice_type, lang_voices["neutral"])
    
    def _get_speaking_rate(self, emotion: str) -> float:
        """Get speaking rate based on emotion"""
        rates = {
            "excited": 1.1,
            "calm": 0.9,
            "warm": 1.0,
            "concerned": 0.95,
            "mysterious": 0.85
        }
        return rates.get(emotion.lower(), 1.0)
    
    def _get_pitch(self, emotion: str) -> float:
        """Get pitch based on emotion"""
        pitches = {
            "excited": 1.2,
            "calm": 0.9,
            "warm": 1.0,
            "concerned": 0.8,
            "mysterious": 0.85
        }
        return pitches.get(emotion.lower(), 1.0)
    
    async def _upload_to_gcs(self, audio_content: bytes, filename: str) -> str:
        """Upload audio content to Google Cloud Storage"""
        local_path = _save_bytes_local(self.local_output_dir, filename, audio_content)
        logger.info("Saved audio locally", local_path=local_path)

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(audio_content, content_type="audio/mpeg")
        
        return f"https://storage.googleapis.com/{self.bucket_name}/{filename}"


class VideoGenerator:
    """Generates video segments using Veo"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        self.local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "local_media")
        
        if GCS_AVAILABLE:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.storage_client = None
            self.bucket = None
        
        # Initialize Vertex-compatible GenAI client for Veo.
        self.genai_client = None
        if GENAI_AVAILABLE and genai:
            try:
                self.genai_client = genai.Client(
                    vertexai=True,
                    project=project_id,
                    location=location,
                )
                logger.info("Initialized Veo client", project=project_id)
            except Exception as e:
                logger.warning(f"Failed to initialize Veo client: {e}")
        
        logger.info("Initialized VideoGenerator", project=project_id, bucket=self.bucket_name)
    
    async def generate(
        self,
        prompt: str,
        duration: int = 15,
        resolution: str = "1080p"
    ) -> str:
        """
        Generate a video segment using Veo.
        
        Args:
            prompt: Text description of the video
            duration: Duration in seconds
            resolution: Video resolution
            
        Returns:
            GCS URL of the generated video
        """
        # Return mock URL if no bucket available
        if not self.bucket:
            logger.warning("No bucket available, returning mock video URL")
            return "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
        
        # Try to use Veo via Vertex API.
        if self.genai_client and genai_types:
            try:
                logger.info("Generating video with Veo", prompt_length=len(prompt), duration=duration)

                # Veo commonly supports short clips; clamp unsupported durations.
                safe_duration = max(5, min(duration, 8))
                if safe_duration != duration:
                    logger.info("Adjusted video duration for Veo", requested=duration, used=safe_duration)

                operation = await asyncio.to_thread(
                    self.genai_client.models.generate_videos,
                    model="veo-3.1-fast-generate-001",
                    prompt=prompt,
                    config=genai_types.GenerateVideosConfig(
                        number_of_videos=1,
                        duration_seconds=safe_duration,
                        resolution=resolution,
                        output_gcs_uri=f"gs://{self.bucket_name}/videos",
                    ),
                )

                # Poll operation until done.
                max_polls = 90  # 15 minutes at 10s interval.
                for _ in range(max_polls):
                    if getattr(operation, "done", False):
                        break
                    await asyncio.sleep(10)
                    operation = await asyncio.to_thread(self.genai_client.operations.get, operation)

                if not getattr(operation, "done", False):
                    raise TimeoutError("Veo operation timed out before completion.")

                response = getattr(operation, "response", None)
                generated_videos = getattr(response, "generated_videos", None) if response else None

                if generated_videos:
                    video = generated_videos[0].video if generated_videos[0] else None
                    if video and getattr(video, "uri", None):
                        # Vertex already persisted output to GCS.
                        parsed = _parse_gcs_uri(video.uri)
                        if parsed and self.storage_client:
                            src_bucket, src_blob = parsed
                            try:
                                blob = self.storage_client.bucket(src_bucket).blob(src_blob)
                                local_path = str(Path(self.local_output_dir) / src_blob)
                                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                                await asyncio.to_thread(blob.download_to_filename, local_path)
                                logger.info("Saved video locally", local_path=local_path)
                            except Exception as save_err:
                                logger.warning(f"Failed to save generated video locally: {save_err}")
                        logger.info("Video generated and stored in GCS", uri=video.uri)
                        return _to_public_storage_url(video.uri)
                    if video and getattr(video, "video_bytes", None):
                        filename = f"videos/{uuid.uuid4()}.mp4"
                        gcs_url = await self._upload_to_gcs(video.video_bytes, filename)
                        logger.info("Video generated and uploaded", gcs_url=gcs_url)
                        return gcs_url
                
                # Better diagnostics when operation completes but no video returned.
                filtered_count = getattr(response, "rai_media_filtered_count", None) if response else None
                filtered_reasons = getattr(response, "rai_media_filtered_reasons", None) if response else None
                logger.warning(
                    "Veo operation completed without videos",
                    filtered_count=filtered_count,
                    filtered_reasons=filtered_reasons,
                )
            except Exception as e:
                logger.warning(f"Veo generation failed: {e}")
        
        # Fallback to mock URL
        logger.warning("Returning mock video URL")
        return "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
    
    async def _upload_to_gcs(self, video_bytes: bytes, filename: str) -> str:
        """Upload video bytes to Google Cloud Storage"""
        local_path = _save_bytes_local(self.local_output_dir, filename, video_bytes)
        logger.info("Saved video locally", local_path=local_path)

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(video_bytes, content_type="video/mp4")
        
        return _to_public_storage_url(f"gs://{self.bucket_name}/{filename}")


class MediaEngine:
    """Unified interface for all media generation"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.image_gen = ImageGenerator(project_id, location)
        self.voice_gen = VoiceGenerator(project_id, location)
        self.video_gen = VideoGenerator(project_id, location)
        
        logger.info("Initialized MediaEngine", project=project_id)
    
    async def generate_story_media(
        self,
        image_prompt: str,
        voiceover_text: str,
        video_prompt: str,
        emotion: str = "warm",
        language: str = "auto"
    ) -> Dict[str, str]:
        """
        Generate all media for a story segment.
        
        Args:
            image_prompt: Prompt for storyboard image
            voiceover_text: Text for voiceover
            video_prompt: Prompt for video generation
            emotion: Emotional tone
            language: Language code (auto-detect if "auto")
            
        Returns:
            Dictionary with URLs for all generated media
        """
        # Generate all media in parallel
        import asyncio
        
        image_url, voiceover_url, video_url = await asyncio.gather(
            self.image_gen.generate(image_prompt),
            self.voice_gen.generate(voiceover_text, emotion=emotion, language=language),
            self.video_gen.generate(video_prompt)
        )
        
        return {
            "image_url": image_url,
            "voiceover_url": voiceover_url,
            "video_url": video_url
        }
