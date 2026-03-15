"""
Story Generator - Uses Gemini 3 Flash to create engaging story narratives
"""

import os
import json
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
        self.genai_client = None
        
        # Try Google AI API key first
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and GENAI_AVAILABLE:
            try:
                self.genai_client = genai.Client(api_key=api_key)
                self.model_name = "gemini-3.1-flash-lite-preview"
                logger.info("Initialized StoryGenerator with Google AI API", model=self.model_name)
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Google AI: {e}")
        
        # Fall back to Vertex AI
        if VERTEXAI_AVAILABLE and GenerativeModel:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel("gemini-3.1-flash-lite-preview")
                logger.info("Initialized StoryGenerator with Vertex AI", project=project_id, location=location)
            except Exception as e:
                logger.warning(f"Failed to initialize Vertex AI: {e}, using mock mode")
                self.model = None
        else:
            logger.warning("No AI backend available, using mock responses")
    
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
        # If no AI backend available, return mock data
        if not self.model and not self.genai_client:
            logger.warning("No AI backend available, using mock story plan")
            return self._get_mock_story_plan(topic, audience, metaphor, num_segments)
        
        try:
            prompt = self._create_story_plan_prompt(topic, audience, metaphor, num_segments)
            
            # Use Google AI API if available
            if self.genai_client:
                response = self.genai_client.models.generate_content(model=self.model_name, contents=prompt)
                story_plan = self._parse_story_plan(response.text, num_segments)
            else:
                # Use Vertex AI
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
            logger.error(f"AI generation failed: {e}, using mock story plan")
            return self._get_mock_story_plan(topic, audience, metaphor, num_segments)
    
    def _get_mock_story_plan(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str],
        num_segments: int
    ) -> Dict[str, Any]:
        """Return mock story plan for development when AI is not available"""
        analogy_text = f" (using the analogy of {metaphor})" if metaphor else ""
        
        segments = []
        for i in range(1, num_segments + 1):
            segments.append({
                "id": i,
                "title": f"Part {i}: Understanding {topic}",
                "narration": f"In this section, we explore a key aspect of {topic}{analogy_text}. This is segment {i}, where we break down important concepts and explain them clearly.",
                "key_points": [f"Key fact about {topic} #{i}", f"Important detail #{i}"],
                "visual_description": f"Infographic diagram illustrating concept {i} of {topic}",
                "visual_elements": ["diagram", "labels", "data"],
                "emotion": "informative",
                "transition": "fade" if i < num_segments else "end",
                "duration": 15.0
            })
        
        return {
            "title": f"Understanding {topic}",
            "visual_bible": {
                "style": "clean infographic and diagram-based visuals",
                "color_palette": "professional blue and white",
                "typography": "modern, sans-serif labels"
            },
            "segments": segments,
            "summary": f"An educational explainer about {topic}{analogy_text} for {audience} audience."
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
        
        if self.genai_client:
            response = self.genai_client.models.generate_content(model=self.model_name, contents=prompt)
            return response.text.strip()
        else:
            response = await self.model.generate_content_async(prompt)
            return response.text.strip()
    
    def _create_story_plan_prompt(
        self,
        topic: str,
        audience: str,
        metaphor: Optional[str],
        num_segments: int
    ) -> str:
        """Create the prompt for educational story plan generation"""
        metaphor_section = ""
        if metaphor:
            metaphor_section = f"Use the analogy of {metaphor} to make concepts more relatable."
        
        prompt = f"""
        Create a {num_segments}-segment **educational explainer video script** about "{topic}" for a {audience} audience.
        
        {metaphor_section}
        
        # CONTENT STYLE:
        - This is a professional educational video, NOT a fairy tale or story.
        - Narration should be clear, explanatory, and informative — like a documentary or educational YouTube video.
        - Each segment should teach a specific concept, fact, or process related to the topic.
        - Include concrete data, examples, and explanations — not vague storytelling.
        
        # VISUAL STYLE:
        Define a "visual_bible" that ensures visual consistency across segments:
        - Color Theme: A clean, professional palette suited to the topic
        - Visual Style: Infographics, diagrams, charts, process flows, annotated figures
        - Typography: Clean, modern fonts with clear labels
        
        # SEGMENTS:
        For each segment, provide:
        1. A clear, descriptive title (e.g., "How Photosynthesis Converts Light to Energy")
        2. Narration text (2-4 sentences of clear, educational explanation)
        3. key_points: 2-3 short bullet points of the most important facts (these will appear as text overlays in the video)
        4. visual_description: What educational visual to show (diagram, chart, process flow, labeled figure, comparison, timeline, etc.)
        5. tone: The appropriate tone (informative, analytical, enthusiastic, etc.)
        
        # RESPONSE FORMAT:
        Structure the response as JSON:
        {{
          "title": "Educational Video Title",
          "visual_bible": {{
            "style": "clean infographic and diagram-based visuals",
            "color_palette": "specific professional color theme",
            "typography": "modern, sans-serif labels and annotations"
          }},
          "segments": [
            {{
              "id": 1,
              "title": "Segment Title",
              "narration": "Clear educational explanation...",
              "key_points": ["Key fact 1", "Key fact 2"],
              "visual_description": "Labeled diagram showing...",
              "visual_elements": ["diagram", "labels", "arrows"],
              "emotion": "informative",
              "transition": "fade to next topic"
            }}
          ],
          "summary": "Brief summary of the educational content covered"
        }}
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
