"""
Media Engine - Integrates Imagen, Veo, and Gemini TTS for media generation
"""

import os
import asyncio
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote
from datetime import timedelta
from typing import Dict, Optional, Tuple, List
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


def _to_proxy_url(uri: str) -> str:
    """Convert a GCS URI to a local proxy URL for serving via FastAPI."""
    if uri.startswith("gs://"):
        without_scheme = uri[len("gs://"):]
        bucket, _, blob_path = without_scheme.partition("/")
        if bucket and blob_path:
            return f"/media/{bucket}/{quote(blob_path, safe='/')}"
    elif uri.startswith("https://storage.googleapis.com/"):
        without_host = uri[len("https://storage.googleapis.com/"):]
        bucket, _, blob_path = without_host.partition("/")
        if bucket and blob_path:
            return f"/media/{bucket}/{quote(blob_path, safe='/')}"
    return uri


def _to_proxy_video_url(bucket: str, blob_path: str) -> str:
    """Create a proxy video URL for video content."""
    return f"/video/{bucket}/{quote(blob_path, safe='/')}"


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
                # Use imagen-3.0-fast for better parallel performance and throughput
                self.imagen_model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")
                logger.info("Initialized Imagen 3.0 Fast model", project=project_id)
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
        """
        # Return mock URL if no bucket available
        if not self.storage_client:
            logger.warning("No storage client available, returning mock image URL")
            return f"https://via.placeholder.com/1280x720.png?text=Story+Image+Placeholder"
        
        # Try to use Imagen
        if self.imagen_model:
            try:
                full_prompt = f"{prompt}. Style: {style}, educational, child-friendly."
                logger.info("Generating image with Imagen", prompt_length=len(full_prompt))
                
                # Valid aspect ratios: "1:1", "9:16", "16:9", "4:3", "3:4"
                valid_ratios = ["1:1", "9:16", "16:9", "4:3", "3:4"]
                target_ratio = aspect_ratio if aspect_ratio in valid_ratios else "16:9"

                images = await asyncio.to_thread(
                    self.imagen_model.generate_images,
                    prompt=full_prompt,
                    number_of_images=1,
                    aspect_ratio=target_ratio
                )
                
                # Handle both list (older SDK) and response object (newer SDK)
                image_list = images.images if hasattr(images, "images") else images
                
                if image_list and len(image_list) > 0:
                    filename = f"storyboards/{uuid.uuid4()}.png"
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        temp_path = tmp.name
                    try:
                        # Check if image has data before saving
                        target_image = image_list[0]
                        if hasattr(target_image, '_image_bytes') or hasattr(target_image, 'gcs_uri'):
                            await asyncio.to_thread(target_image.save, temp_path, include_generation_parameters=False)
                            with open(temp_path, "rb") as f:
                                image_bytes = f.read()
                            gcs_url = await self._upload_to_gcs(image_bytes, filename)
                            logger.info("Image generated and uploaded", gcs_url=gcs_url)
                            return gcs_url
                        else:
                            raise ValueError("Image object returned by model is empty or invalid")
                    finally:
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                else:
                    raise ValueError("Model returned no images")
            except Exception as e:
                logger.warning(f"Imagen generation failed: {e}")
        
        # Fallback to mock URL
        logger.warning("Returning mock image URL")
        return f"https://via.placeholder.com/1280x720.png?text=Story+Image+Placeholder"
    
    async def _upload_to_gcs(self, image_bytes: bytes, filename: str) -> str:
        """Upload image bytes to Google Cloud Storage and return proxy URL"""
        local_path = _save_bytes_local(self.local_output_dir, filename, image_bytes)
        logger.info("Saved image locally", local_path=local_path)

        if not self.storage_client:
            logger.warning("No storage client available, returning local path")
            return f"file://{local_path}"
        
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_string(image_bytes, content_type="image/png")
            logger.info("Uploaded image to GCS", filename=filename)
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")
        except Exception as e:
            logger.error("Failed to upload image to GCS", error=str(e))
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")


class VoiceGenerator:
    """Generates voiceover using Google Cloud TTS"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
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
        
        logger.info("Initialized VoiceGenerator", project=project_id)
    
    async def generate(self, text: str, voice: str = "male", emotion: str = "warm", language: str = "auto") -> str:
        if language == "auto":
            language = self._detect_language(text)
        
        # Normalize language code for TTS API
        lang_code = "en-US"
        if "ar" in language.lower(): lang_code = "ar-SA"
        elif "fr" in language.lower(): lang_code = "fr-FR"
        elif "es" in language.lower(): lang_code = "es-ES"
        elif "de" in language.lower(): lang_code = "de-DE"

        if not self.client:
            return "https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"
        
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice_name = self._get_voice_name(lang_code, voice)
            voice_params = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
            
            speaking_rate = self._get_speaking_rate(emotion)
            pitch = self._get_pitch(emotion)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
                pitch=pitch
            )
            
            logger.info("Generating voiceover", lang=lang_code, voice=voice_name)
            response = await asyncio.to_thread(
                self.client.synthesize_speech,
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )
            
            filename = f"voiceovers/{uuid.uuid4()}.mp3"
            return await self._upload_to_gcs(response.audio_content, filename)
        except Exception as e:
            logger.error("TTS failed", error=str(e))
            return "https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"

    def _detect_language(self, text: str) -> str:
        text_lower = text.lower()
        if any(word in text_lower for word in ['في', 'من', 'إلى']): return "ar-SA"
        if any(word in text_lower for word in ['le', 'la', 'les']): return "fr-FR"
        if any(word in text_lower for word in ['el', 'la', 'los']): return "es-ES"
        if any(word in text_lower for word in ['der', 'die', 'das']): return "de-DE"
        return "en-US"

    def _get_voice_name(self, language: str, voice_type: str = "male") -> str:
        voices = {
            "en-US": {"male": "en-US-Neural2-J", "female": "en-US-Neural2-F", "neutral": "en-US-Neural2-D"},
            "ar-SA": {"male": "ar-SA-Neural2-A", "female": "ar-SA-Neural2-B", "neutral": "ar-SA-Neural2-A"},
            "fr-FR": {"male": "fr-FR-Neural2-D", "female": "fr-FR-Neural2-E", "neutral": "fr-FR-Neural2-D"},
            "es-ES": {"male": "es-ES-Neural2-D", "female": "es-ES-Neural2-F", "neutral": "es-ES-Neural2-D"},
            "de-DE": {"male": "de-DE-Neural2-C", "female": "de-DE-Neural2-F", "neutral": "de-DE-Neural2-C"}
        }
        lang_voices = voices.get(language, voices["en-US"])
        return lang_voices.get(voice_type, lang_voices["neutral"])

    def _get_speaking_rate(self, emotion: str) -> float:
        rates = {"excited": 1.1, "calm": 0.9, "warm": 1.0, "concerned": 0.95, "mysterious": 0.85}
        return rates.get(emotion.lower(), 1.0)

    def _get_pitch(self, emotion: str) -> float:
        pitches = {"excited": 1.2, "calm": 0.9, "warm": 1.0, "concerned": 0.8, "mysterious": 0.85}
        return pitches.get(emotion.lower(), 1.0)

    async def _upload_to_gcs(self, audio_content: bytes, filename: str) -> str:
        local_path = _save_bytes_local(self.local_output_dir, filename, audio_content)
        if not self.storage_client: return f"file://{local_path}"
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_string(audio_content, content_type="audio/mpeg")
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")
        except Exception as e:
            logger.error("Failed to upload audio", error=str(e))
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")


class VideoGenerator:
    """Generates video segments using Veo"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        self.local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "local_media")
        
        if GCS_AVAILABLE:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.storage_client = None
            self.bucket = None
        
        self.genai_client = None
        if GENAI_AVAILABLE and genai:
            try:
                self.genai_client = genai.Client(vertexai=True, project=project_id, location=location)
                logger.info("Initialized Veo client")
            except Exception as e:
                logger.warning(f"Failed to initialize Veo client: {e}")
    
    # Class-level semaphore to limit concurrent Veo calls project-wide
    # Increased to 3 for better throughput while respecting rate limits
    _semaphore = asyncio.Semaphore(3)
    _rate_limit_backoff = 60  # Base backoff in seconds

    async def generate(self, prompt: str, duration: int = 15, resolution: str = "1080p", image_url: Optional[str] = None) -> str:
        if not self.genai_client or not genai_types:
            return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

        max_retries = 3
        base_backoff = 30
        
        for attempt in range(max_retries):
            try:
                async with self._semaphore:
                    logger.info("Generating video with Veo", attempt=attempt+1, prompt_length=len(prompt), image_ref=bool(image_url))
                    safe_duration = max(5, min(duration, 8))
                    
                    # Configure generation inputs
                    video_config = genai_types.GenerateVideosConfig(
                        number_of_videos=1,
                        duration_seconds=safe_duration,
                        resolution=resolution,
                        output_gcs_uri=f"gs://{self.bucket_name}/videos",
                    )
                    
                    # Add image reference for visual continuity if provided
                    if image_url:
                        gcs_uri = None
                        if image_url.startswith("gs://"):
                            gcs_uri = image_url
                        elif "/media/" in image_url:
                            # Convert proxy URL back to GCS URI
                            parts = image_url.split("/")
                            gcs_uri = f"gs://{parts[2]}/{'/'.join(parts[3:])}"
                        
                        if gcs_uri:
                            logger.info("Using image reference for Veo", gcs_uri=gcs_uri)
                            video_config.reference_images = [
                                genai_types.VideoGenerationReferenceImage(
                                    image=genai_types.Image(gcs_uri=gcs_uri, mime_type="image/png"),
                                    reference_type="ASSET"
                                )
                            ]
                        else:
                            logger.warning("Image URL is not a valid GCS URI, skipping reference for Veo", image_url=image_url)
                    
                    operation = await asyncio.to_thread(
                        self.genai_client.models.generate_videos,
                        model="veo-3.1-fast-generate-001",
                        prompt=prompt,
                        config=video_config
                    )

                    max_polls = 100
                    for _ in range(max_polls):
                        if getattr(operation, "done", False): break
                        await asyncio.sleep(10)
                        operation = await asyncio.to_thread(self.genai_client.operations.get, operation)

                    if not getattr(operation, "done", False): raise TimeoutError("Veo timeout")

                    response = getattr(operation, "response", None)
                    generated_videos = getattr(response, "generated_videos", None) if response else None

                    if generated_videos:
                        video = generated_videos[0].video if generated_videos[0] else None
                        if video and getattr(video, "uri", None):
                            parsed = _parse_gcs_uri(video.uri)
                            if parsed and self.storage_client:
                                src_bucket, src_blob = parsed
                                try:
                                    blob = self.storage_client.bucket(src_bucket).blob(src_blob)
                                    local_path = str(Path(self.local_output_dir) / src_blob)
                                    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                                    await asyncio.to_thread(blob.download_to_filename, local_path)
                                    return _to_proxy_url(video.uri)
                                except Exception as save_err:
                                    logger.warning(f"Local save failed: {save_err}")
                                return _to_proxy_url(video.uri)
                
                # If we get here without a return, it failed
                raise ValueError("No video generated in response")

            except Exception as e:
                error_str = str(e).lower()
                if ("429" in error_str or "quota" in error_str or "rate limit" in error_str) and attempt < max_retries - 1:
                    wait_time = base_backoff * (attempt + 1)
                    logger.warning(f"Veo rate limited (attempt {attempt+1}), retrying in {wait_time}s...", error=str(e))
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(f"Veo failed: {e}")
                    break
        
        return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

    async def _upload_to_gcs(self, video_bytes: bytes, filename: str) -> str:
        local_path = _save_bytes_local(self.local_output_dir, filename, video_bytes)
        if not self.storage_client: return f"file://{local_path}"
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_string(video_bytes, content_type="video/mp4")
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")
        except Exception as e:
            logger.error("Failed to upload video", error=str(e))
            return _to_proxy_url(f"gs://{self.bucket_name}/{filename}")


class MediaEngine:
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.image_gen = ImageGenerator(project_id, location)
        self.voice_gen = VoiceGenerator(project_id, location)
        self.video_gen = VideoGenerator(project_id, location)
    
    async def generate_story_media(self, image_prompt: str, voiceover_text: str, video_prompt: str, emotion: str = "warm", language: str = "auto") -> Dict[str, str]:
        # Generate image and voiceover in parallel first
        image_url, voiceover_url = await asyncio.gather(
            self.image_gen.generate(image_prompt),
            self.voice_gen.generate(voiceover_text, emotion=emotion, language=language)
        )
        
        # Now generate video USING the image as a reference for visual continuity
        video_url = await self.video_gen.generate(video_prompt, image_url=image_url)
        
        return {"image_url": image_url, "voiceover_url": voiceover_url, "video_url": video_url}
