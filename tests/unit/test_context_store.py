# tests/unit/test_context_store.py
import pytest
from app.context_store import ContextStore
from app.models.story_context import StoryContext

def test_context_store_set_and_get():
    store = ContextStore()
    context = StoryContext(
        story_id="test-123",
        topic="Solar System",
        audience="10-year-old",
        metaphor="playground",
        visual_bible={"characters": []},
        segments=[],
        full_transcript="Test"
    )
    store.store("test-123", context)
    retrieved = store.get("test-123")
    assert retrieved is not None
    assert retrieved.topic == "Solar System"

def test_context_store_add_message():
    store = ContextStore()
    store.add_message("test-123", "user", "Hello")
    store.add_message("test-123", "assistant", "Hi there")
    history = store.get_history("test-123")
    assert len(history) == 2
    assert history[0]["role"] == "user"
