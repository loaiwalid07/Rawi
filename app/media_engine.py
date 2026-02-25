"""
Media Engine - Integrates Imagen, Veo, and Gemini TTS for media generation
"""

import os
import uuid
from typing import Dict, Any, Optional
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

# Mock Vertex AI for development
try:
    from vertexai.preview.vision_models import ImageGenerationModel, VideoGenerationModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    ImageGenerationModel = None
    VideoGenerationModel = None

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


class ImageGenerator:
    """Generates images using Imagen"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        
        if GCS_AVAILABLE:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.storage_client = None
            self.bucket = None
        
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
        
        # Return mock URL for development
        if not VERTEXAI_AVAILABLE or not ImageGenerationModel:
            logger.warning("Vertex AI not available, returning mock image URL")
            return f"https://via.placeholder.com/1280x720.png?text=Story+Image+Placeholder"
        
        from vertexai.preview.vision_models import ImageGenerationModel
        
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        
        full_prompt = f"{prompt}. Style: {style}, educational, child-friendly."
        
        logger.info("Generating image", prompt_length=len(full_prompt))
        
        images = model.generate_images(
            prompt=full_prompt,
            number_of_images=1,
            aspect_ratio=aspect_ratio
        )
        
        if not images:
            raise ValueError("No images generated")
        
        # Save to GCS
        filename = f"storyboards/{uuid.uuid4()}.png"
        gcs_url = await self._upload_to_gcs(images[0]._image_bytes, filename)
        
        logger.info("Image generated and uploaded", gcs_url=gcs_url)
        return gcs_url
    
    async def _upload_to_gcs(self, image_bytes: bytes, filename: str) -> str:
        """Upload image bytes to Google Cloud Storage"""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(image_bytes, content_type="image/png")
        blob.make_public()
        
        return blob.public_url


class VoiceGenerator:
    """Generates voiceover using Gemini 2.5 Flash-TTS"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        
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
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(audio_content, content_type="audio/mpeg")
        blob.make_public()
        
        return blob.public_url


class VideoGenerator:
    """Generates video segments using Veo"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        
        if GCS_AVAILABLE:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        else:
            self.storage_client = None
            self.bucket = None
        
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
        
        # Return mock URL for development
        if not VERTEXAI_AVAILABLE or not VideoGenerationModel:
            logger.warning("Vertex AI Veo not available, returning mock video URL")
            return "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
        
        from vertexai.preview.vision_models import VideoGenerationModel
        
        model = VideoGenerationModel.from_pretrained("veo-2.0-generate-001")
        
        logger.info("Generating video", prompt_length=len(prompt), duration=duration)
        
        videos = model.generate_videos(
            prompt=prompt,
            duration=duration
        )
        
        if not videos:
            raise ValueError("No videos generated")
        
        # Save to GCS
        filename = f"videos/{uuid.uuid4()}.mp4"
        gcs_url = await self._upload_to_gcs(videos[0]._video_bytes, filename)
        
        logger.info("Video generated and uploaded", gcs_url=gcs_url)
        return gcs_url
    
    async def _upload_to_gcs(self, video_bytes: bytes, filename: str) -> str:
        """Upload video bytes to Google Cloud Storage"""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(video_bytes, content_type="video/mp4")
        blob.make_public()
        
        return blob.public_url


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
