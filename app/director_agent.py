"""
Director Agent - Main orchestrator for RAWI storytelling pipeline
"""

import os
from typing import Dict, Any, List, Optional

# Mock ADK imports for development
try:
    from google.adk.agents import Agent
    from google.adk.tools import FunctionTool as Tool
    ADK_AVAILABLE = True
except ImportError:
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

from app.story_generator import StoryGenerator
from app.models.story_frame import StoryFrame
import structlog

logger = structlog.get_logger(__name__)


class DirectorAgent:
    """
    Main orchestrator that coordinates storytelling pipeline.
    Breaks down topics into manageable segments and coordinates other agents.
    """
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self._project_id = project_id
        self._location = location
        self.story_generator = StoryGenerator(project_id, location)
        
        self.tools = [
            Tool(
                # name="plan_story",
                # description="Plan a story by breaking it into segments",
                func=self.plan_story
            ),
            Tool(
                # name="generate_narration",
                # description="Generate narrative text for a story segment",
                func=self.generate_narration
            )
        ]
        
        # Agent metadata
        self.name = "director_agent"
        self.description = "Orchestrates the storytelling pipeline"
        self.model = "gemini-2.5-flash"
        
        logger.info("Initialized DirectorAgent", project=project_id)
    
    async def plan_story(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str] = None,
        num_segments: int = 6
    ) -> Dict[str, Any]:
        """
        Plan a complete story by breaking it into segments.
        
        Args:
            topic: Educational topic to explain
            audience: Target audience
            metaphor: Optional metaphor to use
            num_segments: Number of story segments
            
        Returns:
            Story plan with segments and metadata
        """
        logger.info(
            "Planning story",
            topic=topic,
            audience=audience,
            metaphor=metaphor,
            segments=num_segments
        )
        
        story_plan = await self.story_generator.generate_story_plan(
            topic=topic,
            audience=audience,
            metaphor=metaphor,
            num_segments=num_segments
        )
        
        return story_plan
    
    async def generate_narration(
        self,
        topic: str,
        key_points: List[str],
        tone: str = "engaging"
    ) -> str:
        """Generate narration text using the story generator"""
        narration = await self.story_generator.generate_narration(
            topic=topic,
            key_points=key_points,
            tone=tone
        )
        
        return narration
    
    def create_story_frames(
        self,
        story_plan: Dict[str, Any]
    ) -> List[StoryFrame]:
        """Convert story plan segments to StoryFrame objects"""
        frames = []
        
        for segment_data in story_plan.get("segments", []):
            frame = StoryFrame(
                id=segment_data.get("id", 0),
                narration=segment_data.get("narration", ""),
                visual_elements=segment_data.get("visual_elements", []),
                emotion=segment_data.get("emotion", "warm"),
                transition=segment_data.get("transition"),
                duration=segment_data.get("duration", 15.0)
            )
            frames.append(frame)
        
        logger.info("Created story frames", count=len(frames))
        return frames
