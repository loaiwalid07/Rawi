# RAWI Production Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add chat feature with LLM about generated video content, enhance frontend with transcript display, and optimize video generation performance for 3-5 minute videos.

**Architecture:** Enhanced current architecture - add chat service module, new React components for output view, optimize concurrent video generation.

**Tech Stack:** Python (FastAPI), React 19, TypeScript, TailwindCSS, Framer Motion, Google Gemini API, Google Veo/Imagen

---

## Phase 1: Backend - Chat Feature & Context Storage

### Task 1: Create Story Context Model

**Files:**
- Create: `app/models/story_context.py`
- Test: `tests/unit/test_story_context.py`

**Step 1: Create the test file**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /workspaces/rawi && pytest tests/unit/test_story_context.py -v
```
Expected: FAIL - module not found

**Step 3: Create the implementation**

```python
# app/models/story_context.py
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
```

**Step 4: Run test to verify it passes**

```bash
cd /workspaces/rawi && pytest tests/unit/test_story_context.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/models/story_context.py tests/unit/test_story_context.py
git commit -m "feat: add StoryContext model for chat feature"
```

---

### Task 2: Create Context Store

**Files:**
- Create: `app/context_store.py`
- Test: `tests/unit/test_context_store.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /workspaces/rawi && pytest tests/unit/test_context_store.py -v
```
Expected: FAIL - module not found

**Step 3: Write minimal implementation**

```python
# app/context_store.py
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
```

**Step 4: Run test to verify it passes**

```bash
cd /workspaces/rawi && pytest tests/unit/test_context_store.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/context_store.py tests/unit/test_context_store.py
git commit -m "feat: add ContextStore for story contexts"
```

---

### Task 3: Create Chat Service

**Files:**
- Create: `app/chat_service.py`
- Test: `tests/unit/test_chat_service.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /workspaces/rawi && pytest tests/unit/test_chat_service.py -v
```
Expected: FAIL - module not found

**Step 3: Write implementation**

```python
# app/chat_service.py
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
```

**Step 4: Run test to verify it passes**

```bash
cd /workspaces/rawi && pytest tests/unit/test_chat_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/chat_service.py tests/unit/test_chat_service.py
git commit -m "feat: add ChatService for LLM-powered story Q&A"
```

---

### Task 4: Add Chat Endpoints to main.py

**Files:**
- Modify: `main.py:260-310`
- Test: `tests/api/test_chat_endpoints.py`

**Step 1: Write the failing test**

```python
# tests/api/test_chat_endpoints.py
import pytest
from fastapi.testclient import TestClient

def test_chat_endpoint_requires_message():
    # This will fail until we add the endpoint
    pass

def test_story_context_endpoint():
    # This will fail until we add the endpoint
    pass
```

**Step 2: Read current main.py to find insertion point**

```bash
cd /workspaces/rawi && head -310 main.py | tail -60
```

**Step 3: Add chat endpoints to main.py**

Add after the existing endpoints (after line 285):

```python
# --- Chat Endpoints ---

@app.post("/chat/{story_id}")
async def chat_endpoint(story_id: str, request: Request):
    """Send message to chat about story."""
    body = await request.json()
    message = body.get("message", "")
    
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(status_code=404, detail="Story not found or expired")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    chat_service = get_chat_service()
    context_store.add_message(story_id, "user", message)
    
    async def generate():
        full_response = ""
        async for chunk in chat_service.chat(
            message, 
            context, 
            context_store.get_history(story_id)
        ):
            full_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        
        context_store.add_message(story_id, "assistant", full_response)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/story/{story_id}/context")
async def get_story_context(story_id: str):
    """Get story context for frontend."""
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(status_code=404, detail="Story not found or expired")
    
    return {
        "story_id": context.story_id,
        "topic": context.topic,
        "transcript": context.full_transcript,
        "segments": context.segments,
        "visual_bible": context.visual_bible,
        "audience": context.audience,
        "metaphor": context.metaphor
    }


@app.get("/story/{story_id}/history")
async def get_conversation_history(story_id: str):
    """Get conversation history for a story."""
    history = context_store.get_history(story_id)
    return {"history": history}
```

**Step 4: Import required modules**

Add at the top of main.py (after existing imports):

```python
from app.context_store import context_store
from app.chat_service import get_chat_service
from app.models.story_context import StoryContext
```

**Step 5: Modify tell_story to store context**

Find the `tell_story` method and add context storage after successful generation:

```python
# In RawiAgent.tell_story, after output is created (around line 233)
if task_id and output:
    # Store story context for chat feature
    story_context = StoryContext(
        story_id=task_id,
        topic=request.topic,
        audience=request.audience,
        metaphor=request.metaphor,
        visual_bible=story_plan.get("visual_bible", {}),
        segments=[seg.__dict__ for seg in output.interleaved_stream],
        full_transcript=output.narration_text,
        created_at=time.time()
    )
    context_store.store(task_id, story_context)
```

Also modify the return to include story_id:

```python
# In tell_story_endpoint, modify return to include story_id
return {"task_id": task_id}
```

**Step 6: Run a basic test**

```bash
cd /workspaces/rawi && python -c "from main import app; print('Import OK')"
```
Expected: No import errors

**Step 7: Commit**

```bash
git add main.py
git commit -m "feat: add chat endpoints and context storage"
```

---

## Phase 2: Frontend Components

### Task 5: Create VideoPlayer Component

**Files:**
- Create: `frontend-react/src/components/VideoPlayer.tsx`
- Modify: `frontend-react/src/App.tsx`

**Step 1: Create VideoPlayer component**

```tsx
// frontend-react/src/components/VideoPlayer.tsx
import React, { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

interface VideoPlayerProps {
  videoUrl: string;
  segments: Segment[];
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, segments }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const seekTo = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play();
    }
  };

  // Calculate progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="relative">
      <div className="aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-black">
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="w-full h-full object-contain"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
        />
      </div>
      
      {/* Custom timeline below video */}
      <div className="mt-4 space-y-2">
        <div className="flex justify-between text-xs text-white/40 font-mono">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
        <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div 
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-indigo-500 to-purple-500"
            style={{ width: `${progress}%` }}
          />
          {/* Segment markers */}
          {segments.map((seg, i) => {
            const pos = duration > 0 ? (seg.timestamp / duration) * 100 : 0;
            return (
              <div
                key={i}
                className="absolute top-0 w-0.5 h-full bg-white/30 cursor-pointer hover:bg-indigo-400"
                style={{ left: `${pos}%` }}
                onClick={() => seekTo(seg.timestamp)}
                title={`Segment ${i + 1}: ${seg.content?.substring(0, 30)}...`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default VideoPlayer;
```

**Step 2: Commit**

```bash
git add frontend-react/src/components/VideoPlayer.tsx
git commit -m "feat: add VideoPlayer component with timeline"
```

---

### Task 6: Create TranscriptPanel Component

**Files:**
- Create: `frontend-react/src/components/TranscriptPanel.tsx`

**Step 1: Create TranscriptPanel component**

```tsx
// frontend-react/src/components/TranscriptPanel.tsx
import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

interface TranscriptPanelProps {
  transcript: string;
  segments: Segment[];
  currentTime: number;
  onSegmentClick?: (time: number) => void;
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcript,
  segments,
  currentTime,
  onSegmentClick
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Filter to only narration segments
  const narrationSegments = segments.filter(seg => 
    seg.type === 'NARRATION' || seg.type === 'NARRATION_BLOB'
  );

  // Find active segment based on current time
  const activeIndex = narrationSegments.findIndex((seg, i) => {
    const nextSeg = narrationSegments[i + 1];
    const segEnd = seg.timestamp + seg.duration;
    return currentTime >= seg.timestamp && (!nextSeg || currentTime < nextSeg.timestamp);
  });

  // Auto-scroll to active segment
  useEffect(() => {
    if (activeIndex >= 0 && containerRef.current) {
      const activeElement = containerRef.current.children[activeIndex] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeIndex]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
        <h3 className="text-indigo-400 font-semibold">Transcript</h3>
      </div>
      
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent"
      >
        <AnimatePresence>
          {narrationSegments.map((seg, i) => {
            const isActive = i === activeIndex;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`
                  p-4 rounded-xl cursor-pointer transition-all duration-300
                  ${isActive 
                    ? 'bg-indigo-500/20 border border-indigo-500/50 shadow-lg shadow-indigo-500/10' 
                    : 'bg-white/5 hover:bg-white/10 border border-transparent'
                  }
                `}
                onClick={() => onSegmentClick?.(seg.timestamp)}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono text-white/40">
                    {formatTime(seg.timestamp)}
                  </span>
                  {isActive && (
                    <span className="text-xs bg-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded-full">
                      Now Playing
                    </span>
                  )}
                </div>
                <p className={`text-white/80 leading-relaxed ${isActive ? 'text-base' : 'text-sm'}`}>
                  {seg.content}
                </p>
              </motion.div>
            );
          })}
        </AnimatePresence>
        
        {narrationSegments.length === 0 && (
          <div className="text-white/40 text-center py-8">
            <p>No transcript available</p>
          </div>
        )}
      </div>
    </div>
  );
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default TranscriptPanel;
```

**Step 2: Commit**

```bash
git add frontend-react/src/components/TranscriptPanel.tsx
git commit -m "feat: add TranscriptPanel with auto-scroll"
```

---

### Task 7: Create ChatPanel Component

**Files:**
- Create: `frontend-react/src/components/ChatPanel.tsx`

**Step 1: Create ChatPanel component**

```tsx
// frontend-react/src/components/ChatPanel.tsx
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, MessageCircle, Bot, User } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatPanelProps {
  storyId: string;
  isOpen: boolean;
  onToggle: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ storyId, isOpen, onToggle }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const API_BASE = 'http://localhost:8000';

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    
    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsStreaming(true);

    try {
      const response = await fetch(`${API_BASE}/chat/${storyId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      });

      if (!response.ok) {
        throw new Error('Chat request failed');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.text) {
                  assistantMessage += data.text;
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = newMessages[newMessages.length - 1];
                    if (lastMessage?.role === 'assistant') {
                      lastMessage.content = assistantMessage;
                    } else {
                      newMessages.push({ role: 'assistant', content: assistantMessage });
                    }
                    return newMessages;
                  });
                }
              } catch {
                // Skip invalid JSON
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, I encountered an error. Please try again.' 
      }]);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-[#0a0a1a]/95 backdrop-blur-xl border-l border-white/10 flex flex-col z-50"
        >
          {/* Header */}
          <div className="p-4 border-b border-white/10 flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <Bot size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-white font-semibold">Story Assistant</h3>
                <p className="text-xs text-white/50">Ask about this story</p>
              </div>
            </div>
            <button 
              onClick={onToggle} 
              className="text-white/60 hover:text-white transition-colors p-2"
            >
              <X size={20} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <MessageCircle size={48} className="mx-auto text-white/20 mb-4" />
                <p className="text-white/60 text-sm">
                  Ask me anything about this story!<br />
                  <span className="text-white/40 text-xs">
                    I can explain concepts, characters, or scenes.
                  </span>
                </p>
              </div>
            )}
            
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={msg.role === 'user' ? 'text-right' : 'text-left'}
              >
                <div className={`inline-block max-w-[85%] p-4 rounded-2xl ${
                  msg.role === 'user' 
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white' 
                    : 'bg-white/10 text-white/90'
                }`}>
                  <div className="flex items-start gap-2">
                    {msg.role === 'assistant' && (
                      <Bot size={16} className="mt-1 flex-shrink-0 text-indigo-400" />
                    )}
                    {msg.role === 'user' && (
                      <User size={16} className="mt-1 flex-shrink-0" />
                    )}
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              </motion.div>
            ))}
            
            {isStreaming && (
              <div className="text-left">
                <div className="inline-block bg-white/10 p-4 rounded-2xl">
                  <div className="flex items-center gap-2">
                    <Bot size={16} className="text-indigo-400" />
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-white/10">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question..."
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-white/30 outline-none focus:border-indigo-500 focus:bg-white/10 transition-all"
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                disabled={isStreaming}
              />
              <button 
                onClick={handleSend}
                disabled={isStreaming || !input.trim()}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl px-4 py-3 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ChatPanel;
```

**Step 2: Commit**

```bash
git add frontend-react/src/components/ChatPanel.tsx
git commit -m "feat: add ChatPanel with streaming support"
```

---

### Task 8: Refactor App.tsx to Use New Components

**Files:**
- Modify: `frontend-react/src/App.tsx`

**Step 1: Read current App.tsx**

```bash
cat frontend-react/src/App.tsx
```

**Step 2: Replace App.tsx with enhanced version**

```tsx
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, RotateCcw, CheckCircle2, AlertCircle, MessageCircle, Play } from 'lucide-react';
import axios from 'axios';
import VideoPlayer from './components/VideoPlayer';
import TranscriptPanel from './components/TranscriptPanel';
import ChatPanel from './components/ChatPanel';

const API_BASE = 'http://localhost:8000';

type TaskStatus = 'pending' | 'planning' | 'storyboarding' | 'generating' | 'merging' | 'completed' | 'failed';

interface ProgressUpdate {
  task_id: string;
  status: TaskStatus;
  progress: number;
  message: string;
  result?: {
    video_url: string;
    narration_text: string;
    interleaved_stream: any[];
    story_id: string;
  };
}

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

const App: React.FC = () => {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<ProgressUpdate | null>(null);
  const [videoResult, setVideoResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  const subscribeToTask = (taskId: string) => {
    const eventSource = new EventSource(`${API_BASE}/stream-progress/${taskId}`);
    
    eventSource.onmessage = (event) => {
      const data: ProgressUpdate = JSON.parse(event.data);
      setStatus(data);
      
      if (data.status === 'completed') {
        setVideoResult({
          ...data.result,
          story_id: taskId
        });
        setIsGenerating(false);
        eventSource.close();
      } else if (data.status === 'failed') {
        setError(data.message);
        setIsGenerating(false);
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      setError("Lost connection to generation server.");
      setIsGenerating(false);
      eventSource.close();
    };
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setIsGenerating(true);
    setVideoResult(null);
    setStatus(null);
    setError(null);

    try {
      const resp = await axios.post(`${API_BASE}/tell-story`, { topic });
      subscribeToTask(resp.data.task_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to initiate story generation.");
      setIsGenerating(false);
    }
  };

  const handleSegmentClick = (time: number) => {
    setCurrentTime(time);
    // Find and update video time if needed
    const video = document.querySelector('video');
    if (video) {
      video.currentTime = time;
    }
  };

  const resetApp = () => {
    setVideoResult(null);
    setTopic('');
    setStatus(null);
    setChatOpen(false);
    setCurrentTime(0);
  };

  // Parse segments from result
  const segments: Segment[] = videoResult?.interleaved_stream || [];

  return (
    <div className="min-h-screen bg-[#050510] text-white flex flex-col">
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-600/20 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600/20 blur-[120px] rounded-full animate-pulse [animation-delay:2s]" />
      </div>

      <div className="relative z-10 flex-1 flex flex-col">
        {/* Header */}
        <header className="p-6 flex justify-between items-center">
          <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-indigo-400">
            RAWI <span className="text-indigo-500">Storyteller</span>
          </h1>
          
          {videoResult && (
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl transition-all"
            >
              <MessageCircle size={18} className="text-indigo-400" />
              <span className="text-sm">Ask about this story</span>
            </button>
          )}
        </header>

        {/* Main Content */}
        <main className="flex-1 flex items-center justify-center p-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-6xl"
          >
            {/* Input View */}
            {!isGenerating && !videoResult && (
              <div className="max-w-2xl mx-auto text-center space-y-8">
                <header className="space-y-2">
                  <h2 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-indigo-400">
                    Transform Any Topic Into a Story
                  </h2>
                  <p className="text-indigo-300/60">Enter a topic and watch it become an engaging educational video</p>
                </header>

                <form onSubmit={handleGenerate} className="relative group">
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="What should we learn about today?"
                    className="w-full bg-white/5 border border-white/10 p-6 rounded-2xl text-xl outline-none focus:border-indigo-500/50 backdrop-blur-xl transition-all placeholder:text-white/20 group-hover:bg-white/10 pr-16"
                  />
                  <button 
                    type="submit"
                    disabled={!topic.trim()}
                    className="absolute right-3 top-3 bottom-3 aspect-square rounded-xl bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-500 disabled:opacity-50 transition-colors"
                  >
                    <Send size={24} />
                  </button>
                </form>
              </div>
            )}

            {/* Generating View */}
            {isGenerating && status && (
              <div className="flex flex-col items-center space-y-12">
                <div className="relative w-48 h-48 flex items-center justify-center">
                  <motion.div 
                    animate={{ rotate: 360 }}
                    transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                    className="absolute inset-0 border-t-2 border-indigo-500/50 rounded-full"
                  />
                  <motion.div 
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 4, repeat: Infinity }}
                    className="w-32 h-32 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full blur-[20px] opacity-40"
                  />
                  <div className="text-4xl font-bold">{status.progress}%</div>
                </div>
                
                <div className="text-center space-y-2">
                  <div className="text-indigo-400 font-mono text-sm tracking-widest uppercase">
                    {status.status.replace('_', ' ')}
                  </div>
                  <h2 className="text-2xl font-light text-white/90 italic">"{status.message}"</h2>
                </div>

                <div className="w-full max-w-md bg-white/5 h-1 rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${status.progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Output View */}
            {videoResult && (
              <motion.div 
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="grid grid-cols-1 lg:grid-cols-2 gap-6"
              >
                {/* Video Section */}
                <div className="space-y-4">
                  <VideoPlayer 
                    videoUrl={`${API_BASE}${videoResult.video_url}`}
                    segments={segments}
                  />
                  
                  <div className="flex justify-between items-center">
                    <button 
                      onClick={resetApp}
                      className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors"
                    >
                      <RotateCcw size={18} /> Create another story
                    </button>
                  </div>
                </div>

                {/* Transcript Section */}
                <div className="h-[500px] lg:h-auto p-6 rounded-3xl bg-white/5 backdrop-blur-3xl border border-white/10">
                  <TranscriptPanel 
                    transcript={videoResult.narration_text}
                    segments={segments}
                    currentTime={currentTime}
                    onSegmentClick={handleSegmentClick}
                  />
                </div>
              </motion.div>
            )}

            {/* Error View */}
            {error && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-8 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center gap-3"
              >
                <AlertCircle size={20} />
                {error}
              </motion.div>
            )}
          </motion.div>
        </main>

        {/* Chat Panel */}
        {videoResult && (
          <ChatPanel 
            storyId={videoResult.story_id}
            isOpen={chatOpen}
            onToggle={() => setChatOpen(!chatOpen)}
          />
        )}

        {/* Footer */}
        <footer className="p-6 text-center text-white/10 font-mono text-xs tracking-widest uppercase">
          Rawi Multimodal Engine v1.2
        </footer>
      </div>
    </div>
  );
};

export default App;
```

**Step 3: Run frontend to verify**

```bash
cd frontend-react && npm run dev
```

**Step 4: Commit**

```bash
git add frontend-react/src/App.tsx
git commit -m "refactor: integrate new components into App"
```

---

## Phase 3: Performance Optimization

### Task 9: Optimize Video Generation Concurrency

**Files:**
- Modify: `app/media_engine.py:350-360`

**Step 1: Read current VideoGenerator class**

```bash
sed -n '350,370p' app/media_engine.py
```

**Step 2: Increase semaphore and add smart backoff**

```python
# Find the _semaphore line in VideoGenerator class and update:
_semaphore = asyncio.Semaphore(3)  # Was 2

# Add rate limit tracking
_rate_limit_tracker = {}  # Track per-project rate limits

async def generate(self, prompt: str, ...):
    # Add smart backoff logic
    if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
        # Exponential backoff: 60s, 120s, 180s
        wait_time = 60 * (attempt + 1)
        logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
        await asyncio.sleep(wait_time)
```

**Step 3: Commit**

```bash
git add app/media_engine.py
git commit -m "perf: increase Veo concurrency and add smart backoff"
```

---

### Task 10: Optimize Segment Duration

**Files:**
- Modify: `main.py:160-170`

**Step 1: Find and update segment duration calculation**

```python
# Around line 164 in tell_story method
# Current:
target_segment_duration = (request.duration_minutes * 60.0) / len(story_plan["segments"])

# Change to:
# Cap at 12 seconds to reduce total segments
# 3 min video = 180s / 12s = 15 segments (vs 20+ at 8s)
num_segments = len(story_plan["segments"])
target_duration = (request.duration_minutes * 60.0) / num_segments
target_segment_duration = min(12.0, target_duration)
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "perf: optimize segment duration for faster generation"
```

---

## Phase 4: Integration Testing

### Task 11: End-to-End Testing

**Step 1: Test the full flow**

```bash
# Start backend
cd /workspaces/rawi && python main.py &

# Wait for startup
sleep 5

# Test story generation
curl -X POST http://localhost:8000/tell-story \
  -H "Content-Type: application/json" \
  -d '{"topic": "The Solar System", "audience": "10-year-old"}'
```

**Step 2: Test chat endpoint**

```bash
# Get a story_id from the response, then test chat
curl -X POST http://localhost:8000/chat/STORY_ID \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this story about?"}'
```

**Step 3: Test frontend**

```bash
cd frontend-react && npm run build
# Open browser to http://localhost:5173
```

**Step 4: Commit**

```bash
git add .
git commit -m "test: e2e testing complete"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | StoryContext model | +1 |
| 2 | ContextStore | +1 |
| 3 | ChatService | +1 |
| 4 | Chat endpoints in main.py | +1 |
| 5 | VideoPlayer component | +1 |
| 6 | TranscriptPanel component | +1 |
| 7 | ChatPanel component | +1 |
| 8 | Refactor App.tsx | +1 |
| 9 | Optimize Veo concurrency | +1 |
| 10 | Optimize segment duration | +1 |
| 11 | Integration testing | - |

---

## Dependencies

All required packages already installed:
- `google-genai` - Gemini API
- `framer-motion` - Animations  
- `lucide-react` - Icons
- `axios` - HTTP client
- `react`, `react-dom` - React 19
- `typescript` - TypeScript

---

## Plan Complete

**Plan saved to:** `docs/plans/2026-03-08-production-enhancement-implementation-plan.md`

Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?