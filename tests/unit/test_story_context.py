# tests/unit/test_story_context.py
import pytest
from app.models.story_context import StoryContext

def test_story_context_creation():
    context = StoryContext(
        story_id="test-123",
        topic="Solar System",
        audience="10-year-old",
        metaphor="playground",
        visual_bible={"characters": [], "setting": "space"},
        segments=[{"id": 1, "narration": "Test narration"}],
        full_transcript="Test transcript",
        created_at=1234567890.0
    )
    assert context.story_id == "test-123"
    assert context.topic == "Solar System"
