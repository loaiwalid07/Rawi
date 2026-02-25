"""
Data models for RAWI story components
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class MediaType(str, Enum):
    NARRATION = "NARRATION"
    IMAGE_URL = "IMAGE_URL"
    VOICEOVER_BLOB = "VOICEOVER_BLOB"
    VIDEO_URL = "VIDEO_URL"


@dataclass
class MediaAsset:
    """Represents a media asset (image, audio, video)"""
    type: MediaType
    content: str
    gcs_url: str
    filename: str
    size_bytes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "gcs_url": self.gcs_url,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata or {}
        }


@dataclass
class InterleavedSegment:
    """Represents a segment in the interleaved output stream"""
    type: MediaType
    content: str
    timestamp: float
    duration: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "metadata": self.metadata
        }


@dataclass
class StoryFrame:
    """Represents a single frame in the story"""
    id: int
    narration: str
    visual_elements: List[str]
    emotion: str
    transition: Optional[str] = None
    duration: float = 15.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "narration": self.narration,
            "visual_elements": self.visual_elements,
            "emotion": self.emotion,
            "transition": self.transition,
            "duration": self.duration
        }


@dataclass
class StoryboardFrame:
    """Represents a storyboard frame with visual description"""
    segment_id: int
    visual_prompt: str
    camera_angles: List[str]
    transitions: str
    color_palette: str
    characters: List[str]
    key_actions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "visual_prompt": self.visual_prompt,
            "camera_angles": self.camera_angles,
            "transitions": self.transitions,
            "color_palette": self.color_palette,
            "characters": self.characters,
            "key_actions": self.key_actions
        }
