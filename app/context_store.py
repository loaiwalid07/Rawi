"""In-memory storage for story contexts and chat conversations."""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.models.story_context import StoryContext


@dataclass
class ContextStore:
    """In-memory storage for story contexts (low scale: 1-10 users)."""
    
    contexts: Dict[str, StoryContext] = field(default_factory=dict)
    conversations: Dict[str, List[Dict]] = field(default_factory=dict)
    max_age_seconds: int = 3600
    
    def store(self, story_id: str, context: StoryContext):
        """Store a story context."""
        self.contexts[story_id] = context
    
    def get(self, story_id: str) -> Optional[StoryContext]:
        """Get a story context by ID."""
        context = self.contexts.get(story_id)
        if context and context.is_expired(self.max_age_seconds):
            del self.contexts[story_id]
            return None
        return context
    
    def add_message(self, story_id: str, role: str, content: str):
        """Add a message to the conversation history."""
        if story_id not in self.conversations:
            self.conversations[story_id] = []
        self.conversations[story_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    def get_history(self, story_id: str) -> List[Dict]:
        """Get conversation history for a story."""
        return self.conversations.get(story_id, [])
    
    def clear_expired(self):
        """Clear expired contexts."""
        expired = [
            sid for sid, ctx in self.contexts.items()
            if ctx.is_expired(self.max_age_seconds)
        ]
        for sid in expired:
            del self.contexts[sid]
            if sid in self.conversations:
                del self.conversations[sid]


# Global instance
context_store = ContextStore()
