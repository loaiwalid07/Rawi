"""
Story Generator - Uses Gemini 3 Flash to create engaging story narratives
"""

import os
import json
from typing import Dict, Any, List, Optional

# Mock Vertex AI imports for development
try:
    import vertexai
    from vertexai.preview.generative_models import GenerativeModel, Part
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    GenerativeModel = None
    Part = None

from app.models.story_frame import StoryFrame
import structlog

logger = structlog.get_logger(__name__)


class StoryGenerator:
    """Generates engaging story content using Gemini 3 Flash"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.model = None
        
        if VERTEXAI_AVAILABLE and GenerativeModel:
            try:
                # Initialize Vertex AI
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel("gemini-1.5-flash-002")
                logger.info("Initialized StoryGenerator with Vertex AI", project=project_id, location=location)
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI: {e}, using mock mode")
                self.model = None
        else:
            logger.warning("Vertex AI not available, using mock responses")
    
    async def generate_story_plan(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str] = None,
        num_segments: int = 6
    ) -> Dict[str, Any]:
        """
        Generate a complete story plan with multiple segments.
        
        Args:
            topic: Educational topic to explain
            audience: Target audience (e.g., "10-year-old", "general")
            metaphor: Optional metaphor to use (e.g., "a bakery")
            num_segments: Number of story segments to create
            
        Returns:
            Story plan with narration, visual elements, and structure
        """
        # If model is not available, return mock data for development
        if not self.model:
            logger.warning("No Vertex AI model available, using mock story plan")
            return self._get_mock_story_plan(topic, audience, metaphor, num_segments)
        
        try:
            prompt = self._create_story_plan_prompt(topic, audience, metaphor, num_segments)
            
            response = await self.model.generate_content_async(prompt)
            story_plan = self._parse_story_plan(response.text, num_segments)
            
            logger.info(
                "Generated story plan",
                topic=topic,
                audience=audience,
                num_segments=len(story_plan.get("segments", []))
            )
            
            return story_plan
            
        except Exception as e:
            logger.error(f"Vertex AI failed: {e}, using mock story plan")
            return self._get_mock_story_plan(topic, audience, metaphor, num_segments)
    
    def _get_mock_story_plan(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str],
        num_segments: int
    ) -> Dict[str, Any]:
        """Return mock story plan for development when AI is not available"""
        metaphor_text = f" using the metaphor of {metaphor}" if metaphor else ""
        
        segments = []
        for i in range(1, num_segments + 1):
            segments.append({
                "id": i,
                "title": f"Part {i}: {topic}",
                "narration": f"Once upon a time, there was a story about {topic}{metaphor_text}. This is segment {i} of the story, where we learn important lessons about {topic}.",
                "visual_elements": ["illustration", "characters", "scene"],
                "emotion": "warm",
                "transition": "fade" if i < num_segments else "end",
                "duration": 15.0
            })
        
        return {
            "title": f"The Story of {topic}",
            "segments": segments,
            "summary": f"An educational story about {topic}{metaphor_text} for {audience}-olds."
        }
    
    async def generate_narration(
        self,
        topic: str,
        key_points: List[str],
        tone: str = "engaging",
        style: str = "storytelling"
    ) -> str:
        """
        Generate narrative text for a story segment.
        
        Args:
            topic: Topic being covered
            key_points: Key information to include
            tone: Emotional tone (engaging, mysterious, exciting, etc.)
            style: Narrative style (storytelling, educational, etc.)
            
        Returns:
            Engaging narrative text
        """
        # If model is not available, return mock data
        if not self.model:
            return f"Once upon a time, there was a story about {topic}. " + " ".join(key_points[:2]) + " And so the adventure continued..."
        
        prompt = f"""
        Write an engaging {tone} {style} narrative about {topic}.
        
        Include these key points naturally:
        {chr(10).join(f"- {point}" for point in key_points)}
        
        Guidelines:
        - Use simple, accessible language
        - Create vivid imagery
        - Build emotional connection
        - Keep it flowing and natural
        - Length: 2-3 sentences
        """
        
        response = await self.model.generate_content_async(prompt)
        return response.text.strip()
    
    def _create_story_plan_prompt(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str],
        num_segments: int
    ) -> str:
        """Create the prompt for story plan generation"""
        metaphor_section = ""
        if metaphor:
            metaphor_section = f"Use the metaphor of {metaphor} to explain the concepts."
        
        prompt = f"""
        Create an engaging {num_segments}-segment story plan about {topic} for {audience}-olds.
        
        {metaphor_section}
        
        For each segment, provide:
        1. A brief title
        2. Engaging narration text (2-3 sentences)
        3. Visual elements to show (what to illustrate)
        4. Emotional tone for narration
        5. How it transitions to next segment
        
        Structure the response as JSON:
        {{
          "title": "Story Title",
          "segments": [
            {{
              "id": 1,
              "title": "Segment Title",
              "narration": "Engaging narrative text...",
              "visual_elements": ["element1", "element2"],
              "emotion": "warm",
              "transition": "fade to next scene"
            }}
          ],
          "summary": "Brief summary of the story"
        }}
        
        Make it educational, engaging, and appropriate for the age group.
        """
        
        return prompt
    
    def _parse_story_plan(self, response_text: str, num_segments: int) -> Dict[str, Any]:
        """Parse the AI response into a structured story plan"""
        import json
        
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                story_plan = json.loads(json_str)
                
                # Ensure segments exist
                if "segments" not in story_plan:
                    story_plan["segments"] = []
                
                # Add segment IDs if missing
                for i, segment in enumerate(story_plan["segments"]):
                    if "id" not in segment:
                        segment["id"] = i + 1
                    if "duration" not in segment:
                        segment["duration"] = 15.0
                
                return story_plan
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON, falling back to manual parsing")
        
        # Fallback: manually parse the response
        return self._fallback_parse(response_text, num_segments)
    
    def _fallback_parse(self, response_text: str, num_segments: int) -> Dict[str, Any]:
        """Fallback parsing if JSON extraction fails"""
        logger.warning("Using fallback parsing for story plan")
        
        segments = []
        lines = response_text.split("\n")
        
        current_segment = {}
        segment_count = 0
        
        for line in lines:
            line = line.strip()
            
            if "segment" in line.lower() and str(segment_count + 1) in line:
                if current_segment:
                    segments.append(current_segment)
                segment_count += 1
                current_segment = {
                    "id": segment_count,
                    "narration": "",
                    "visual_elements": [],
                    "emotion": "warm",
                    "transition": "fade",
                    "duration": 15.0
                }
            elif "narration" in line.lower():
                current_segment["narration"] = line.split(":", 1)[-1].strip()
            elif "visual" in line.lower():
                elements = line.split(":", 1)[-1].strip()
                current_segment["visual_elements"] = [e.strip() for e in elements.split(",")]
            elif "emotion" in line.lower():
                current_segment["emotion"] = line.split(":", 1)[-1].strip()
        
        if current_segment:
            segments.append(current_segment)
        
        return {
            "title": "Generated Story",
            "segments": segments[:num_segments],
            "summary": "Generated story with multiple segments"
        }
