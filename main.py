"""
RAWI - The Storyteller
Main entry point for the RawiAgent using Google ADK
"""

import os
import asyncio
import uuid
import json
import collections
import time
from pathlib import Path
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import structlog

# Mock google.adk imports for development
try:
    from google.adk.agents import Agent
    from google.adk.tools import FunctionTool as Tool
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    class Agent:
        def __init__(self, name: str = "", description: str = "", tools: list = None, model: str = ""):
            self.name, self.description, self.tools, self.model = name, description, tools or [], model
    class Tool:
        def __init__(self, name: str = "", description: str = "", func=None):
            self.name, self.description, self.func = name, description, func
        def __call__(self, *args, **kwargs): return self.func(*args, **kwargs) if self.func else None

class Context:
    def __init__(self, user_id, session_id):
        self.user_id, self.session_id = user_id, session_id

from app.director_agent import DirectorAgent
from app.media_engine import MediaEngine, ImageGenerator, VoiceGenerator, VideoGenerator
from app.storyboard_agent import StoryboardAgent
from app.video_merger import VideoMerger
from app.models.story_frame import StoryFrame, MediaAsset, MediaType, InterleavedSegment
from app.context_store import context_store
from app.chat_service import get_chat_service
from app.models.story_context import StoryContext

logger = structlog.get_logger(__name__)

# --- Progress Tracking Models ---

class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    STORYBOARDING = "storyboarding"
    GENERATING = "generating"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TaskProgress:
    task_id: str
    status: TaskStatus
    progress: int
    message: str
    result: Optional[Dict[str, Any]] = None
    timestamp: float = time.time()

class TaskStore:
    """In-memory store for tracking generation tasks and their progress."""
    def __init__(self):
        self.tasks: Dict[str, TaskProgress] = {}
        self.queues: Dict[str, asyncio.Queue] = collections.defaultdict(asyncio.Queue)

    def update(self, task_id: str, status: TaskStatus, progress: int, message: str, result: Optional[Dict[str, Any]] = None):
        t_progress = TaskProgress(
            task_id=task_id, status=status, progress=progress, message=message, 
            result=result, timestamp=time.time()
        )
        self.tasks[task_id] = t_progress
        # Notify subscribers
        if task_id in self.queues:
            asyncio.create_task(self.queues[task_id].put(t_progress))

    async def subscribe(self, task_id: str):
        queue = self.queues[task_id]
        # Send current state first if exists
        if task_id in self.tasks:
            yield f"data: {json.dumps(self.tasks[task_id].__dict__)}\n\n"
        
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item.__dict__)}\n\n"
            if item.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
        
        # Cleanup
        del self.queues[task_id]

task_store = TaskStore()

# --- Agent Models ---

@dataclass
class StoryRequest:
    topic: str
    audience: str = "10-year-old"
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
    def __init__(self, project_id: Optional[str] = None):
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "demo")
        self._location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        self.image_gen = ImageGenerator(project_id=self._project_id)
        self.voice_gen = VoiceGenerator(project_id=self._project_id)
        self.video_gen = VideoGenerator(project_id=self._project_id)
        self.video_merger = VideoMerger(project_id=self._project_id)
        
        self.director = DirectorAgent(project_id=self._project_id)
        self.storyboard_agent = StoryboardAgent(project_id=self._project_id)
        self.media_engine = MediaEngine(project_id=self._project_id)

    async def tell_story(self, request: StoryRequest, task_id: Optional[str] = None) -> StoryOutput:
        try:
            if task_id: task_store.update(task_id, TaskStatus.PLANNING, 10, "Drafting a magical story script...")

            story_plan = await self.director.plan_story(
                topic=request.topic, audience=request.audience, metaphor=request.metaphor
            )
            
            # Extract visual bible for consistency
            visual_bible = story_plan.get("visual_bible", {})
            
            if task_id: task_store.update(task_id, TaskStatus.STORYBOARDING, 25, "Sketching character worlds and camera angles...")

            storyboard_frames = await self.storyboard_agent.generate_complete_storyboard(
                segments=story_plan["segments"],
                visual_bible=visual_bible
            )
            
            if task_id: task_store.update(task_id, TaskStatus.GENERATING, 40, "Animating your story and bringing scenes to life...")

            video_segments, all_storyboard_urls, all_voiceovers, interleaved_stream = [], [], [], []
            current_timestamp = 0.0
            target_segment_duration = (request.duration_minutes * 60.0) / len(story_plan["segments"])
            
            # Use counter to track parallel progress
            completed_segments = 0
            total_segments = len(story_plan["segments"])
            
            async def generate_segment_assets(i, segment, storyboard):
                nonlocal completed_segments
                segment["duration"] = target_segment_duration
                
                # Use visual bible and storyboard details for high-quality prompting
                image_prompt = f"High-quality 3D children's animation: {storyboard.visual_prompt}. Pixar-style character design."
                video_prompt = f"Cinematic animation: {storyboard.visual_prompt}. Camera: {', '.join(storyboard.camera_angles)}."
                
                media_urls = await self.media_engine.generate_story_media(
                    image_prompt=image_prompt,
                    voiceover_text=segment['narration'],
                    video_prompt=video_prompt,
                    emotion=segment.get('emotion', 'warm'),
                    language=request.language
                )
                
                # Granular progress update
                completed_segments += 1
                if task_id:
                    progress_val = 40 + int((completed_segments / total_segments) * 40)
                    task_store.update(task_id, TaskStatus.GENERATING, progress_val, f"Successfully created {completed_segments} of {total_segments} animated scenes...")
                
                return {"segment": segment, "media_urls": media_urls, "id": i}

            gen_tasks = [generate_segment_assets(i, seg, sb) for i, (seg, sb) in enumerate(zip(story_plan["segments"], storyboard_frames))]
            generated_data = await asyncio.gather(*gen_tasks)
            generated_data.sort(key=lambda x: x["id"])

            if task_id: task_store.update(task_id, TaskStatus.MERGING, 85, "Final polishing and cinematic assembly...")

            for data in generated_data:
                seg, urls = data["segment"], data["media_urls"]
                # Only include valid videos
                if "/media/" in urls["video_url"] or "gs://" in urls["video_url"]:
                    video_segments.append({"url": urls["video_url"], "segment_id": data["id"], "duration": seg["duration"]})
                
                all_storyboard_urls.append(urls["image_url"])
                all_voiceovers.append(urls["voiceover_url"])
                
                interleaved_stream.append(InterleavedSegment(MediaType.NARRATION, seg['narration'], current_timestamp, seg["duration"], {}))
                interleaved_stream.append(InterleavedSegment(MediaType.IMAGE_URL, urls["image_url"], current_timestamp, seg["duration"], {}))
                interleaved_stream.append(InterleavedSegment(MediaType.VOICEOVER_BLOB, urls["voiceover_url"], current_timestamp, seg["duration"], {}))
                current_timestamp += seg["duration"] + 0.5

            if len(video_segments) < (total_segments / 2):
                logger.warning("Too many video segments failed", count=len(video_segments))
                if task_id: task_store.update(task_id, TaskStatus.FAILED, 0, "Production halted: Most video segments failed to animate.")
                raise RuntimeError("Failed to generate enough video segments")

            final_video_url = await self.video_merger.merge_segments(
                video_segments=video_segments,
                output_filename=f"story_{uuid.uuid4().hex[:8]}.mp4"
            )
            
            output = StoryOutput(
                frames=self.director.create_story_frames(story_plan),
                video_url=final_video_url,
                storyboard_urls=all_storyboard_urls,
                narration_text=" ".join([s["narration"] for s in story_plan["segments"]]),
                voiceover_url=all_voiceovers[0] if all_voiceovers else "",
                interleaved_stream=interleaved_stream
            )

            # Store story context for chat feature
            if task_id:
                story_context = StoryContext(
                    story_id=task_id,
                    topic=request.topic,
                    audience=request.audience,
                    metaphor=request.metaphor,
                    visual_bible=visual_bible,
                    segments=[seg.__dict__ for seg in output.interleaved_stream],
                    full_transcript=output.narration_text,
                    created_at=time.time()
                )
                context_store.store(task_id, story_context)

            if task_id:
                result = {
                    "video_url": output.video_url,
                    "narration_text": output.narration_text,
                    "interleaved_stream": [seg.__dict__ for seg in output.interleaved_stream]
                }
                task_store.update(task_id, TaskStatus.COMPLETED, 100, "Your story is ready for the premiere!", result=result)
            return output
            
        except Exception as e:
            logger.error("Story generation failed", error=str(e))
            if task_id: task_store.update(task_id, TaskStatus.FAILED, 0, f"Production Error: {str(e)}")
            raise e

# --- FastAPI App ---

app = FastAPI(title="RAWI - The Storyteller")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_rawi_agent = None

def get_agent():
    global _rawi_agent
    if _rawi_agent is None:
        _rawi_agent = RawiAgent()
    return _rawi_agent

@app.get("/health")
async def health(): return {"status": "healthy"}

@app.post("/tell-story")
async def tell_story_endpoint(request: Dict[str, Any]):
    task_id = str(uuid.uuid4())
    task_store.update(task_id, TaskStatus.PENDING, 0, "Initializing...")
    
    async def run_gen():
        try:
            agent = get_agent()
            req = StoryRequest(
                topic=request.get("topic", "A magical adventure"),
                audience=request.get("audience", "10-year-old"),
                metaphor=request.get("metaphor"),
                duration_minutes=int(request.get("duration_minutes", 5))
            )
            await agent.tell_story(req, task_id=task_id)
        except Exception as e: logger.error(f"Task {task_id} failed: {e}")

    asyncio.create_task(run_gen())
    return {"task_id": task_id}

@app.get("/stream-progress/{task_id}")
async def stream_progress(task_id: str):
    return StreamingResponse(task_store.subscribe(task_id), media_type="text/event-stream")

@app.get("/video/{bucket}/{path:path}")
@app.get("/media/{bucket}/{path:path}")
async def proxy_media(bucket: str, path: str):
    from google.cloud import storage
    try:
        agent = get_agent()
        blob = storage.Client(project=agent._project_id).bucket(bucket).blob(path)
        content = await asyncio.to_thread(blob.download_as_bytes)
        ext = path.split('.')[-1].lower()
        m_types = {"mp4": "video/mp4", "mp3": "audio/mpeg", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        return StreamingResponse(iter([content]), media_type=m_types.get(ext, "application/octet-stream"))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# --- Chat Endpoints ---

from fastapi import Request

@app.post("/chat/{story_id}")
async def chat_endpoint(story_id: str, request: Request):
    """Send message to chat about story."""
    body = await request.json()
    message = body.get("message", "")
    
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(status_code=404, detail="Story not found or expired")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    chat_service = get_chat_service()
    context_store.add_message(story_id, "user", message)
    
    async def generate():
        full_response = ""
        async for chunk in chat_service.chat(
            message, 
            context, 
            context_store.get_history(story_id)
        ):
            full_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        
        context_store.add_message(story_id, "assistant", full_response)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/story/{story_id}/context")
async def get_story_context(story_id: str):
    """Get story context for frontend."""
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(status_code=404, detail="Story not found or expired")
    
    return {
        "story_id": context.story_id,
        "topic": context.topic,
        "transcript": context.full_transcript,
        "segments": context.segments,
        "visual_bible": context.visual_bible,
        "audience": context.audience,
        "metaphor": context.metaphor
    }


@app.get("/story/{story_id}/history")
async def get_conversation_history(story_id: str):
    """Get conversation history for a story."""
    history = context_store.get_history(story_id)
    return {"history": history}


# Static files (must be defined last)
FRONTEND_DIR = Path(__file__).parent / "frontend-react" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
