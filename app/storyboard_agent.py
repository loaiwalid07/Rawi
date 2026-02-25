"""
Storyboard Agent - Generates detailed storyboard descriptions for Veo video generation
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
load_dotenv()

# Try Google AI SDK (genai) first - uses API key
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

# Mock ADK imports for development
try:
    from google.adk import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    
    class Agent:
        def __init__(self, name, description, tools=None, model=None):
            self.name = name
            self.description = description
            self.tools = tools or []
            self.model = model

# Mock Vertex AI for development
try:
    import vertexai
    from vertexai.preview.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    GenerativeModel = None

from app.models.story_frame import StoryboardFrame
import structlog

logger = structlog.get_logger(__name__)


class StoryboardAgent:
    """
    Generates detailed storyboard visual descriptions that guide Veo video generation.
    Creates camera angles, transitions, color palettes, and character actions.
    """
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self._project_id = project_id
        self._location = location
        self.model = None
        self.genai_client = None
        self.model_name = None
        
        # Try Google AI API key first
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=api_key)
                self.genai_client = genai
                self.model_name = "gemini-2.0-flash"
                logger.info("Initialized StoryboardAgent with Google AI API", model=self.model_name)
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Google AI: {e}")
        
        # Fall back to Vertex AI
        if VERTEXAI_AVAILABLE and GenerativeModel:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel("gemini-2.5-flash")
                logger.info("Initialized StoryboardAgent with Vertex AI", project=project_id)
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI: {e}, using mock mode")
                self.model = None
        else:
            logger.warning("No AI backend available, using mock mode")
        
        # Agent metadata
        self.name = "storyboard_agent"
        self.description = "Generates storyboard visual descriptions"
        
        logger.info("Initialized StoryboardAgent", project=project_id)
    
    async def generate_storyboard(
        self,
        narration: str,
        segment_id: int,
        total_segments: int,
        previous_frame: Optional[StoryboardFrame] = None
    ) -> StoryboardFrame:
        """
        Generate a detailed storyboard description for a story segment.
        
        Args:
            narration: Narration text for this segment
            segment_id: Current segment number (1-based)
            total_segments: Total number of segments
            previous_frame: Previous storyboard frame for continuity
            
        Returns:
            StoryboardFrame with detailed visual description
        """
        prompt = self._create_storyboard_prompt(
            narration, segment_id, total_segments, previous_frame
        )
        
        response = await self.model.generate_content_async(prompt)
        storyboard = self._parse_storyboard_response(response.text, segment_id)
        
        logger.info(
            "Generated storyboard",
            segment_id=segment_id,
            total=total_segments
        )
        
        return storyboard
    
    def _create_storyboard_prompt(
        self,
        narration: str,
        segment_id: int,
        total_segments: int,
        previous_frame: Optional[StoryboardFrame]
    ) -> str:
        """Create prompt for storyboard generation"""
        
        continuity_section = ""
        if previous_frame:
            continuity_section = f"""
            Previous scene context:
            - Characters: {', '.join(previous_frame.characters)}
            - Color palette: {previous_frame.color_palette}
            
            Ensure visual continuity with the previous scene.
            """
        
        prompt = f"""
        Create a detailed storyboard description for this story segment:
        
        Narration: {narration}
        Segment: {segment_id} of {total_segments}
        
        {continuity_section}
        
        Provide the following details:
        
        1. Visual Prompt: A comprehensive description of what to show in the scene
        2. Camera Angles: 2-3 specific camera angles (e.g., "wide shot showing the entire bakery", "close-up on the baker's hands")
        3. Transitions: How to transition from the previous scene (e.g., "smooth fade", "quick cut", "zoom out")
        4. Color Palette: Dominant colors and mood (e.g., "warm golden tones", "soft pastels", "vibrant and energetic")
        5. Characters: Any characters to include and their expressions (e.g., "baker with warm smile", "curious child with wide eyes")
        6. Key Actions: 2-3 main actions to animate (e.g., "kneading dough", "oven opening with steam", "customers entering")
        
        Guidelines:
        - Keep it child-friendly and educational
        - Create engaging, dynamic visuals
        - Ensure smooth flow between segments
        - Use warm, inviting colors
        - Show, don't just tell
        
        Format your response as structured text that can be easily parsed.
        """
        
        return prompt
    
    def _parse_storyboard_response(
        self,
        response_text: str,
        segment_id: int
    ) -> StoryboardFrame:
        """Parse AI response into StoryboardFrame"""
        
        # Initialize with defaults
        storyboard = StoryboardFrame(
            segment_id=segment_id,
            visual_prompt="",
            camera_angles=[],
            transitions="fade",
            color_palette="warm tones",
            characters=[],
            key_actions=[]
        )
        
        lines = response_text.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            line_lower = line.lower()
            
            if "visual prompt" in line_lower or "description" in line_lower:
                current_section = "visual_prompt"
            elif "camera" in line_lower:
                current_section = "camera_angles"
            elif "transition" in line_lower:
                current_section = "transitions"
            elif "color" in line_lower or "palette" in line_lower:
                current_section = "color_palette"
            elif "character" in line_lower:
                current_section = "characters"
            elif "action" in line_lower:
                current_section = "key_actions"
            elif line and ":" in line:
                value = line.split(":", 1)[1].strip()
                
                if current_section == "visual_prompt":
                    storyboard.visual_prompt += value + " "
                elif current_section == "camera_angles" and value:
                    storyboard.camera_angles.append(value)
                elif current_section == "transitions":
                    storyboard.transitions = value
                elif current_section == "color_palette":
                    storyboard.color_palette = value
                elif current_section == "characters" and value:
                    storyboard.characters.extend([c.strip() for c in value.split(",")])
                elif current_section == "key_actions" and value:
                    storyboard.key_actions.extend([a.strip() for a in value.split(",")])
        
        # Fallback if parsing failed
        if not storyboard.visual_prompt:
            storyboard.visual_prompt = response_text[:500]
        
        logger.info("Parsed storyboard", prompt_length=len(storyboard.visual_prompt))
        return storyboard
    
    async def generate_complete_storyboard(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[StoryboardFrame]:
        """
        Generate storyboard frames for all segments in a story.
        
        Args:
            segments: List of story segments with narration
            
        Returns:
            List of StoryboardFrame objects
        """
        storyboards = []
        previous_frame = None
        
        for i, segment in enumerate(segments, start=1):
            storyboard = await self.generate_storyboard(
                narration=segment.get("narration", ""),
                segment_id=i,
                total_segments=len(segments),
                previous_frame=previous_frame
            )
            
            storyboards.append(storyboard)
            previous_frame = storyboard
        
        logger.info("Generated complete storyboard", count=len(storyboards))
        return storyboards
