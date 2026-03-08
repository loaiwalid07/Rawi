# tests/unit/test_chat_service.py
import pytest
from app.chat_service import ChatService
from app.models.story_context import StoryContext

def test_build_context_prompt():
    service = ChatService(project_id="test")
    context = StoryContext(
        story_id="test-123",
        topic="Solar System",
        audience="10-year-old",
        metaphor="playground",
        visual_bible={"characters": [], "setting": "space"},
        segments=[{"id": 1, "narration": "The sun is a star"}],
        full_transcript="The sun is a star. Planets orbit around it.",
        created_at=1234567890.0
    )
    prompt = service._build_context_prompt(
        "What is the sun?",
        context,
        []
    )
    assert "Solar System" in prompt
    assert "What is the sun?" in prompt
    assert "The sun is a star" in prompt
