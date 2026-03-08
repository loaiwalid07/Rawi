"""Chat service for conversational AI about generated stories."""
import os
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

# Try Google AI SDK
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

import structlog
from app.models.story_context import StoryContext

logger = structlog.get_logger(__name__)


class ChatService:
    """Handles Gemini-based conversational AI for story discussion."""
    
    def __init__(self, project_id: str = None, location: str = "us-central1"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "demo")
        self.location = location
        self.model_name = "gemini-3.1-flash-lite-preview"
        self.genai_client = None
        self.max_history_messages = 20
        
        # Try to initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and GENAI_AVAILABLE:
            try:
                self.genai_client = genai.Client(api_key=api_key)
                logger.info("Initialized ChatService with Gemini API")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
    
    async def chat(
        self, 
        message: str, 
        story_context: StoryContext,
        conversation_history: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses with full story context."""
        if not self.genai_client:
            # Return mock response if no client
            yield "Chat feature requires Gemini API key. Please configure GEMINI_API_KEY."
            return
        
        prompt = self._build_context_prompt(message, story_context, conversation_history)
        
        try:
            # Use streaming for real-time responses
            response = self.genai_client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("Chat generation failed", error=str(e))
            yield f"I apologize, but I encountered an error: {str(e)}"
    
    def _build_context_prompt(
        self, 
        message: str, 
        story_context: StoryContext,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Build prompt with story context for educational Q&A."""
        
        history_section = ""
        if conversation_history:
            formatted_history = []
            for msg in conversation_history[-self.max_history_messages:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                formatted_history.append(f"{role}: {msg['content']}")
            history_section = "\n".join(formatted_history) + "\n\n"
        
        segments_text = ""
        if story_context.segments:
            for seg in story_context.segments:
                if isinstance(seg, dict) and "narration" in seg:
                    segments_text += f"- {seg['narration']}\n"
                elif isinstance(seg, dict) and "content" in seg:
                    segments_text += f"- {seg['content']}\n"
        
        prompt = f"""You are an educational assistant discussing a story about {story_context.topic}.

Your role is to help users understand the content better by answering their questions about the story.

STORY CONTEXT:
- Topic: {story_context.topic}
- Target Audience: {story_context.audience}
{f"- Metaphor: {story_context.metaphor}" if story_context.metaphor else ""}
- Visual Theme: {story_context.visual_bible.get('setting', 'Default')}

STORY TRANSCRIPT:
{story_context.full_transcript}

STORY SEGMENTS:
{segments_text}

CONVERSATION HISTORY:
{history_section}User: {message}

Provide helpful, educational responses that reference specific parts of the story.
Be conversational but informative. If the user asks something not related to the story, gently redirect them.
Keep responses concise but thorough."""
        
        return prompt
    
    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for prompt."""
        if not history:
            return "No previous conversation."
        
        formatted = []
        for msg in history[-self.max_history_messages:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {msg['content']}")
        
        return "\n".join(formatted)


# Singleton instance
_chat_service = None

def get_chat_service() -> ChatService:
    """Get or create chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
