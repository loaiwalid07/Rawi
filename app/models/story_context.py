"""Story context model for chat feature."""
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class StoryContext:
    """Stores complete story data for chat context."""
    story_id: str
    topic: str
    audience: str
    metaphor: Optional[str]
    visual_bible: Dict[str, Any]
    segments: List[Dict[str, Any]]
    full_transcript: str
    created_at: float = field(default_factory=time.time)
    
    def to_json(self) -> str:
        """Serialize for caching."""
        return json.dumps({
            "story_id": self.story_id,
            "topic": self.topic,
            "audience": self.audience,
            "metaphor": self.metaphor,
            "visual_bible": self.visual_bible,
            "segments": self.segments,
            "full_transcript": self.full_transcript,
            "created_at": self.created_at
        })
    
    @classmethod
    def from_json(cls, data: str) -> 'StoryContext':
        """Deserialize from JSON."""
        d = json.loads(data)
        return cls(**d)
    
    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """Check if context has expired."""
        return (time.time() - self.created_at) > max_age_seconds
