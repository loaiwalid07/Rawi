"""
RAWI - The Storyteller
Main entry point for the RawiAgent using Google ADK
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Mock google.adk imports for development (replace with actual imports when available)
try:
    from google.adk.agents import Agent
    from google.adk.tools import FunctionTool as Tool
    ADK_AVAILABLE = True
except ImportError:
    print("Warning: google-adk not installed, using mock classes")
    ADK_AVAILABLE = False
    
    class Agent:
        def __init__(self, name: str = "", description: str = "", tools: list = None, model: str = ""):
            self.name = name
            self.description = description
            self.tools = tools or []
            self.model = model
    
    class Tool:
        """Mock tool class for development"""
        def __init__(self, name: str = "", description: str = "", func=None):
            self.name = name
            self.description = description
            self.func = func
        
        def __call__(self, *args, **kwargs):
            if self.func:
                return self.func(*args, **kwargs)
            return None
    
class Context:
    def __init__(self, user_id, session_id):
        self.user_id = user_id
        self.session_id = session_id

from app.director_agent import DirectorAgent
from app.media_engine import MediaEngine, ImageGenerator, VoiceGenerator, VideoGenerator
from app.storyboard_agent import StoryboardAgent
from app.video_merger import VideoMerger
from app.models.story_frame import StoryFrame, MediaAsset, MediaType, InterleavedSegment
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class StoryRequest:
    topic: str
    audience: str = "general"
    metaphor: Optional[str] = None
    duration_minutes: int = 5
    language: str = "en"


@dataclass
class StoryOutput:
    frames: List[StoryFrame]
    video_url: str
    storyboard_urls: List[str]
    narration_text: str
    voiceover_url: str
    interleaved_stream: List[InterleavedSegment]


class RawiAgent:
    """
    Main RAWI agent that orchestrates storytelling using Google ADK.
    Transforms educational topics into immersive multimodal stories.
    """
    
    def __init__(self, project_id: Optional[str] = None):
        # Initialize configuration first
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or "rawi-demo"
        self._location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        # Initialize media engines
        self.image_gen = ImageGenerator(project_id=self._project_id)
        self.voice_gen = VoiceGenerator(project_id=self._project_id)
        self.video_gen = VideoGenerator(project_id=self._project_id)
        self.video_merger = VideoMerger(project_id=self._project_id)
        
        # Initialize sub-agents
        self.director = DirectorAgent(project_id=self._project_id)
        self.storyboard_agent = StoryboardAgent(project_id=self._project_id)
        self.media_engine = MediaEngine(project_id=self._project_id)
        
        # Define tools for ADK
        self.tools = [
            Tool(
                name="generate_storyboard",
                description="Generate storyboard images for story segments",
                func=self._generate_storyboard_tool
            ),
            Tool(
                name="generate_video_segment",
                description="Generate video segment using Veo",
                func=self._generate_video_segment_tool
            ),
            Tool(
                name="generate_voiceover",
                description="Generate emotive voiceover using Gemini TTS",
                func=self._generate_voiceover_tool
            ),
            Tool(
                name="merge_videos",
                description="Merge multiple video segments into final video",
                func=self._merge_videos_tool
            )
        ]
        
        # Agent metadata
        self.name = "rawi_storyteller"
        self.description = "Transforms educational topics into immersive multimodal stories"
        self.model = "gemini-3-flash"
        
        logger.info("Initialized RawiAgent", project_id=self._project_id)
    
    @property
    def project_id(self):
        """Get project ID for backward compatibility"""
        return self._project_id
    
    @property
    def location(self):
        """Get location for backward compatibility"""
        return self._location
    
    async def tell_story(self, request: StoryRequest) -> StoryOutput:
        """
        Main method to generate a complete multimodal story.
        
        Args:
            request: StoryRequest with topic, audience, metaphor, etc.
            
        Returns:
            StoryOutput with all generated media assets
        """
        logger.info("Starting story generation", topic=request.topic, audience=request.audience)
        
        try:
            # Phase 1: Generate story narrative and storyboard
            story_plan = await self.director.plan_story(
                topic=request.topic,
                audience=request.audience,
                metaphor=request.metaphor
            )
            
            logger.info("Story plan generated", num_segments=len(story_plan.get("segments", [])))
            
            # Phase 2: Generate storyboard frames
            storyboard_frames = await self.storyboard_agent.generate_complete_storyboard(
                segments=story_plan["segments"]
            )
            
            # Phase 3 & 4: Generate all media for segments
            video_segments = []
            all_storyboard_urls = []
            all_voiceovers = []
            interleaved_stream = []
            current_timestamp = 0.0
            
            for i, (segment, storyboard) in enumerate(zip(story_plan["segments"], storyboard_frames)):
                segment_id = segment.get("id", i + 1)
                
                # Create image prompt from storyboard
                image_prompt = f"""
                Create an illustration for this story segment:
                {segment['narration']}
                
                Visual style: Children's book illustration, warm and inviting, educational.
                Scene: {storyboard.visual_prompt}
                """
                
                # Create video prompt from storyboard
                video_prompt = f"""
                Create a short video (10-15 seconds) based on this illustration:
                {storyboard.visual_prompt}
                
                Narration to match timing: {segment['narration']}
                
                Camera: {', '.join(storyboard.camera_angles)}
                Style: Smooth animation, educational, child-friendly.
                Colors: {storyboard.color_palette}
                """
                
                # Generate all media
                media_urls = await self.media_engine.generate_story_media(
                    image_prompt=image_prompt,
                    voiceover_text=segment['narration'],
                    video_prompt=video_prompt,
                    emotion=segment.get('emotion', 'warm')
                )
                
                # Add to collections
                video_segments.append({
                    "url": media_urls["video_url"],
                    "segment_id": segment_id
                })
                all_storyboard_urls.append(media_urls["image_url"])
                all_voiceovers.append(media_urls["voiceover_url"])
                
                # Create interleaved segments
                segment_duration = segment.get('duration', 15.0)
                
                # Narration segment
                interleaved_stream.append(InterleavedSegment(
                    type=MediaType.NARRATION,
                    content=segment['narration'],
                    timestamp=current_timestamp,
                    duration=segment_duration,
                    metadata={"emotion": segment.get('emotion', 'warm')}
                ))
                
                # Image segment (display with narration)
                interleaved_stream.append(InterleavedSegment(
                    type=MediaType.IMAGE_URL,
                    content=media_urls["image_url"],
                    timestamp=current_timestamp,
                    duration=segment_duration,
                    metadata={"style": "illustration", "segment_id": segment_id}
                ))
                
                # Voiceover segment (play with narration)
                interleaved_stream.append(InterleavedSegment(
                    type=MediaType.VOICEOVER_BLOB,
                    content=media_urls["voiceover_url"],
                    timestamp=current_timestamp,
                    duration=segment_duration,
                    metadata={"format": "mp3", "segment_id": segment_id}
                ))
                
                current_timestamp += segment_duration + 0.5  # Small gap between segments
            
            # Phase 5: Merge into final video
            final_video_url = await self.video_merger.merge_segments(
                video_segments=video_segments,
                output_filename=f"story_{request.topic.replace(' ', '_').replace('/', '_')}.mp4"
            )
            
            # Create story frames
            frames = self.director.create_story_frames(story_plan)
            
            # Create output
            output = StoryOutput(
                frames=frames,
                video_url=final_video_url,
                storyboard_urls=all_storyboard_urls,
                narration_text=story_plan.get("summary", ""),
                voiceover_url=all_voiceovers[0] if all_voiceovers else "",
                interleaved_stream=interleaved_stream
            )
            
            logger.info("Story generation completed", video_url=final_video_url)
            return output
            
        except Exception as e:
            logger.error("Story generation failed", error=str(e))
            raise
    
    # Tool implementations for ADK
    async def _generate_storyboard_tool(
        self, 
        context: Context, 
        narration: str
    ) -> Dict[str, Any]:
        """ADK tool: Generate storyboard image from narration"""
        image_prompt = f"""
        Create an illustration for this educational story segment:
        {narration}
        
        Style: Children's book illustration, warm and inviting, educational.
        Format: 16:9 aspect ratio.
        """
        
        image_url = await self.image_gen.generate(
            prompt=image_prompt,
            style="illustration"
        )
        
        return {"image_url": image_url, "prompt": image_prompt}
    
    async def _generate_video_segment_tool(
        self,
        context: Context,
        storyboard_prompt: str,
        narration: str
    ) -> Dict[str, Any]:
        """ADK tool: Generate video segment using Veo"""
        video_prompt = f"""
        Create a short video (10-15 seconds) that illustrates:
        {storyboard_prompt}
        
        Narration to match timing: {narration}
        
        Style: Smooth animation, educational, child-friendly.
        """
        
        video_url = await self.video_gen.generate(
            prompt=video_prompt,
            duration=15
        )
        
        return {"video_url": video_url, "prompt": video_prompt}
    
    async def _generate_voiceover_tool(
        self,
        context: Context,
        text: str,
        emotion: str = "warm"
    ) -> Dict[str, Any]:
        """ADK tool: Generate emotive voiceover"""
        voiceover_url = await self.voice_gen.generate(
            text=text,
            voice="male-1",
            emotion=emotion,
            language="en"
        )
        
        return {"audio_url": voiceover_url, "text": text, "emotion": emotion}
    
    async def _merge_videos_tool(
        self,
        context: Context,
        video_urls: List[str]
    ) -> Dict[str, str]:
        """ADK tool: Merge video segments"""
        merged_url = await self.video_merger.merge_segments(
            video_segments=[{"url": url} for url in video_urls],
            output_filename="final_story.mp4"
        )
        
        return {"merged_video_url": merged_url}


# FastAPI app for deployment
app = FastAPI(
    title="RAWI - The Storyteller",
    description="Transforms educational topics into immersive multimodal stories",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StoryRequestAPI(BaseModel):
    topic: str
    audience: str = "general"
    metaphor: Optional[str] = None
    duration_minutes: int = 5
    language: str = "en"


class StoryResponseAPI(BaseModel):
    video_url: str
    storyboard_urls: List[str]
    narration_text: str
    voiceover_url: str
    segments: List[Dict[str, Any]]
    interleaved_stream: List[Dict[str, Any]]


# Initialize agent globally
rawi_agent = RawiAgent()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "RAWI - The Storyteller",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "rawi_storyteller"}


@app.post("/tell-story", response_model=StoryResponseAPI)
async def tell_story_endpoint(request: StoryRequestAPI):
    """
    Generate a multimodal story for the given topic.
    
    Example:
        POST /tell-story
        {
            "topic": "French Revolution",
            "audience": "10-year-old",
            "metaphor": "a bakery"
        }
    """
    try:
        logger.info("Received story request", topic=request.topic)
        
        story_request = StoryRequest(**request.dict())
        story_output = await rawi_agent.tell_story(story_request)
        
        response = StoryResponseAPI(
            video_url=story_output.video_url,
            storyboard_urls=story_output.storyboard_urls,
            narration_text=story_output.narration_text,
            voiceover_url=story_output.voiceover_url,
            segments=[frame.__dict__ for frame in story_output.frames],
            interleaved_stream=[seg.__dict__ for seg in story_output.interleaved_stream]
        )
        
        logger.info("Story generated successfully", video_url=story_output.video_url)
        return response
        
    except Exception as e:
        logger.error("Story generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docs")
async def docs():
    """Redirect to API documentation"""
    return {"docs": "/docs", "redoc": "/redoc"}


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info("Starting RAWI server", host=host, port=port)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
