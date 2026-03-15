# RAWI Production Enhancement Design

**Date:** 2026-03-08  
**Status:** Approved  
**Approach:** Enhanced Current Architecture (Option A)

---

## Overview

Enhance RAWI for production readiness with:
1. **Frontend UX**: Progressive disclosure - simple input → rich output with chat
2. **Chat Feature**: LLM-powered conversation about generated content
3. **Video Performance**: 3-5 minute videos with optimized generation
4. **Styling**: Clean, polished React components

---

## Requirements Summary

| Aspect | Decision |
|--------|----------|
| Frontend UX | Progressive Disclosure - simple → advanced controls |
| Chat Feature | Full story context with Gemini |
| Video Length | 3-5 minutes (15-25 segments) |
| Performance | Optimize total generation time |
| Deployment | Google Cloud Run |
| Scale | 1-10 concurrent users |
| Chat LLM | Google Gemini |

---

## Section 1: Frontend UX Flow

### Phase 1: Simple Input (Current - Keep)
- Single topic input field
- Optional: audience, metaphor, duration selectors
- "Generate Story" button
- Progress indicator with status messages

### Phase 2: Output View (New)
After generation completes, display:

1. **VideoPlayer** - Main video with playback controls
2. **TranscriptPanel** - Synchronized scrolling text alongside video
3. **Segment Timeline** - Visual timeline showing 15-25 segments with timestamps
4. **ChatPanel** - Expandable/collapsible chat interface with LLM

### Phase 3: Deep Control (Future - Not Included)
- Segment editing (re-generate specific parts)
- Transcript editing with re-voiceover
- Custom style/character controls

### Component Structure

```
frontend-react/src/
├── App.tsx              # Main app (refactored)
├── index.css            # Global styles (exists)
├── components/
│   ├── VideoPlayer.tsx   # Video playback with controls
│   ├── TranscriptPanel.tsx # Synchronized text display
│   ├── ChatPanel.tsx     # LLM chat interface
│   └── ProgressOverlay.tsx # Generation progress (extract from App)
└── styles/
    └── components.css    # Component-specific styles
```

### UI States

| State | Display |
|-------|---------|
| Input | Topic field, generate button |
| Generating | Progress animation, status messages |
| Output | Video + Transcript side by side |
| Chat Active | Chat panel expands from right |

---

## Section 2: Backend Architecture

### New Components

#### 1. Chat Service (`app/chat_service.py`)

```python
class ChatService:
    """Handles Gemini-based conversational AI for story discussion."""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.model_name = "gemini-3.1-flash-lite-preview"
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    async def chat(
        self, 
        message: str, 
        story_context: StoryContext,
        conversation_history: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses with full story context."""
        prompt = self._build_context_prompt(message, story_context, conversation_history)
        async for chunk in self.genai_client.models.generate_content_stream(...):
            yield chunk.text
    
    def _build_context_prompt(self, message, story_context, history) -> str:
        """Build prompt with story context for educational Q&A."""
        return f"""
        You are an educational assistant discussing a story about {story_context.topic}.
        
        STORY CONTEXT:
        - Topic: {story_context.topic}
        - Audience: {story_context.audience}
        - Visual Theme: {story_context.visual_bible}
        
        FULL TRANSCRIPT:
        {story_context.full_transcript}
        
        SEGMENTS:
        {self._format_segments(story_context.segments)}
        
        CONVERSATION HISTORY:
        {self._format_history(history)}
        
        USER QUESTION: {message}
        
        Provide helpful, educational responses that reference specific parts of the story.
        """
```

#### 2. Story Context Model (`app/models/story_context.py`)

```python
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
    created_at: float
    
    def to_json(self) -> str:
        """Serialize for caching."""
        return json.dumps(self.__dict__)
    
    @classmethod
    def from_story_output(cls, story_id: str, output: StoryOutput, request: StoryRequest) -> 'StoryContext':
        """Create context from story output."""
        return cls(
            story_id=story_id,
            topic=request.topic,
            audience=request.audience,
            metaphor=request.metaphor,
            visual_bible=output.visual_bible,
            segments=[seg.__dict__ for seg in output.interleaved_stream],
            full_transcript=output.narration_text,
            created_at=time.time()
        )
```

#### 3. Context Store (`app/context_store.py`)

```python
class ContextStore:
    """In-memory storage for story contexts (low scale: 1-10 users)."""
    
    def __init__(self, max_age_seconds: int = 3600):
        self.contexts: Dict[str, StoryContext] = {}
        self.conversations: Dict[str, List[Dict]] = {}
        self.max_age = max_age_seconds
    
    def store(self, story_id: str, context: StoryContext):
        self.contexts[story_id] = context
    
    def get(self, story_id: str) -> Optional[StoryContext]:
        return self.contexts.get(story_id)
    
    def add_message(self, story_id: str, role: str, content: str):
        if story_id not in self.conversations:
            self.conversations[story_id] = []
        self.conversations[story_id].append({"role": role, "content": content})
    
    def get_history(self, story_id: str) -> List[Dict]:
        return self.conversations.get(story_id, [])

# Global instance
context_store = ContextStore()
```

### New API Endpoints

```python
# In main.py

@app.post("/chat/{story_id}")
async def chat_endpoint(story_id: str, request: Dict[str, str]):
    """Send message to chat about story."""
    message = request.get("message", "")
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(404, "Story not found or expired")
    
    chat_service = ChatService()
    context_store.add_message(story_id, "user", message)
    
    # Stream response
    async def generate():
        full_response = ""
        async for chunk in chat_service.chat(message, context, context_store.get_history(story_id)):
            full_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        context_store.add_message(story_id, "assistant", full_response)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/story/{story_id}/context")
async def get_story_context(story_id: str):
    """Get story context for frontend."""
    context = context_store.get(story_id)
    if not context:
        raise HTTPException(404, "Story not found")
    return {
        "topic": context.topic,
        "transcript": context.full_transcript,
        "segments": context.segments,
        "visual_bible": context.visual_bible
    }
```

### Data Flow

```
User generates story
    ↓
StoryOutput created
    ↓
StoryContext created & cached (story_id)
    ↓
Frontend receives story_id with video_url
    ↓
User clicks "Ask Question" in ChatPanel
    ↓
POST /chat/{story_id} with message
    ↓
ChatService loads context → Gemini API streaming
    ↓
SSE stream to frontend ChatPanel
    ↓
Conversation history maintained in ContextStore
```

---

## Section 3: Video Performance Optimizations

### Current Bottleneck Analysis

| Component | Current State | Time per Segment |
|-----------|---------------|------------------|
| Story Planning | Sequential | ~2-3s |
| Storyboard Generation | Sequential | ~1-2s |
| Imagen (Image) | Semi-parallel (2 concurrent) | ~5-10s |
| Veo (Video) | Semaphore limited to 2 | ~15-30s |
| TTS (Voice) | Parallel | ~3-5s |
| FFmpeg Merge | Sequential at end | ~10-15s total |

**For 3-5 min video (15-25 segments):**
- Current estimate: 12-50 minutes (unacceptable)

### Optimizations

#### 1. Increase Concurrent Veo Calls

**File:** `app/media_engine.py`

```python
class VideoGenerator:
    # Current: Semaphore(2)
    # New: Semaphore(3) with smart backoff
    _semaphore = asyncio.Semaphore(3)
    _rate_limit_backoff = 60
    
    async def generate(self, prompt: str, ...):
        for attempt in range(max_retries):
            try:
                async with self._semaphore:
                    # ... video generation
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait_time = self._rate_limit_backoff * (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    raise
```

#### 2. Optimize Segment Duration

**File:** `main.py`

```python
# Calculate optimal segment duration for fewer segments
target_segment_duration = min(12, (request.duration_minutes * 60) / num_segments)
# Cap at 12 seconds to reduce total segment count
# 3 min video = 180s / 12s = 15 segments (vs 20+ at 8s)
```

#### 3. Parallel Segment Generation

**Current (main.py):**
```python
gen_tasks = [generate_segment_assets(i, seg, sb) for i, (seg, sb) in enumerate(...)]
generated_data = await asyncio.gather(*gen_tasks)
```

**Keep and optimize:** Already parallel, but increase semaphore limits.

#### 4. Pre-warm Gemini Client

**File:** `app/story_generator.py`

```python
class StoryGenerator:
    def __init__(self, ...):
        # Pre-initialize client to avoid cold start
        self._warmup()
    
    def _warmup(self):
        # Make a small request to warm up the connection
        if self.genai_client:
            try:
                self.genai_client.models.generate_content(
                    model=self.model_name, 
                    contents="Ready"
                )
            except:
                pass
```

### Estimated Performance

| Optimization | Time Saved |
|--------------|------------|
| 3 concurrent Veo (vs 2) | ~30% faster |
| 12s segments (vs 8s) | ~25% fewer segments |
| Pre-warmed connections | ~5-10s cold start saved |

**Result: 3-5 min video in 5-8 minutes**

---

## Section 4: Frontend Styling & Polish

### Current State Analysis

- **File:** `frontend-react/src/App.tsx` (~196 lines)
- **Stack:** React 19, Vite, TailwindCSS, Framer Motion, Lucide icons
- **Theme:** Dark with indigo/purple gradients
- **Design:** Clean, minimal, single-page

### New Component Files

#### VideoPlayer.tsx

```tsx
import React from 'react';
import { motion } from 'framer-motion';

interface VideoPlayerProps {
  videoUrl: string;
  segments: InterleavedSegment[];
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, segments }) => {
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = React.useState(0);

  return (
    <div className="relative aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-black">
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        className="w-full h-full"
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      />
      {/* Timeline overlay showing current segment */}
      <div className="absolute bottom-16 left-4 right-4">
        <SegmentTimeline segments={segments} currentTime={currentTime} />
      </div>
    </div>
  );
};
```

#### TranscriptPanel.tsx

```tsx
import React from 'react';
import { motion } from 'framer-motion';

interface TranscriptPanelProps {
  transcript: string;
  segments: InterleavedSegment[];
  currentTime: number;
  onSegmentClick: (time: number) => void;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcript,
  segments,
  currentTime,
  onSegmentClick
}) => {
  const activeSegmentIndex = segments.findIndex(
    (seg, i) => currentTime >= seg.timestamp && 
              (i === segments.length - 1 || currentTime < segments[i + 1].timestamp)
  );

  return (
    <div className="h-full overflow-y-auto p-6 rounded-3xl bg-white/5 backdrop-blur-xl border border-white/10">
      <h3 className="text-indigo-400 font-semibold mb-4">Transcript</h3>
      <div className="space-y-4">
        {segments
          .filter(seg => seg.type === MediaType.NARRATION)
          .map((seg, i) => (
            <motion.div
              key={i}
              className={`p-4 rounded-xl cursor-pointer transition-all ${
                i === activeSegmentIndex 
                  ? 'bg-indigo-500/20 border border-indigo-500/50' 
                  : 'bg-white/5 hover:bg-white/10'
              }`}
              onClick={() => onSegmentClick(seg.timestamp)}
            >
              <p className="text-white/80 leading-relaxed">{seg.content}</p>
            </motion.div>
          ))}
      </div>
    </div>
  );
};
```

#### ChatPanel.tsx

```tsx
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, MessageCircle } from 'lucide-react';

interface ChatPanelProps {
  storyId: string;
  isOpen: boolean;
  onToggle: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ storyId, isOpen, onToggle }) => {
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    
    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsStreaming(true);

    // SSE streaming
    const eventSource = new EventSource(`/chat/${storyId}?message=${encodeURIComponent(userMessage)}`);
    let assistantMessage = '';
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
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
    };

    eventSource.onerror = () => {
      setIsStreaming(false);
      eventSource.close();
    };
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          className="fixed right-0 top-0 bottom-0 w-96 bg-[#0a0a1a] border-l border-white/10 flex flex-col"
        >
          {/* Header */}
          <div className="p-4 border-b border-white/10 flex justify-between items-center">
            <h3 className="text-white font-semibold">Chat about this story</h3>
            <button onClick={onToggle} className="text-white/60 hover:text-white">
              <X size={20} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'text-right' : 'text-left'}>
                <div className={`inline-block p-3 rounded-xl max-w-[80%] ${
                  msg.role === 'user' 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-white/10 text-white/90'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
          </div>

          {/* Input */}
          <div className="p-4 border-t border-white/10">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about the story..."
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-white outline-none focus:border-indigo-500"
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              />
              <button 
                onClick={handleSend}
                disabled={isStreaming}
                className="bg-indigo-600 rounded-xl px-4 py-2 text-white disabled:opacity-50"
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
```

### Color Scheme (Consistent)

```css
/* TailwindCSS custom colors in index.css */
:root {
  --bg-primary: #050510;
  --bg-secondary: rgba(255,255,255,0.05);
  --accent-primary: #6366f1;  /* indigo-500 */
  --accent-secondary: #a855f7;  /* purple-500 */
  --text-primary: #ffffff;
  --text-secondary: rgba(255,255,255,0.7);
}
```

---

## Implementation Phases

### Phase 1: Backend Enhancement (Priority: High)
1. Create `app/models/story_context.py`
2. Create `app/context_store.py`
3. Create `app/chat_service.py`
4. Add chat endpoints to `main.py`
5. Modify `StoryOutput` to return `story_id`
6. Store context after generation

### Phase 2: Frontend Components (Priority: High)
1. Create `components/` directory structure
2. Create `VideoPlayer.tsx`
3. Create `TranscriptPanel.tsx`
4. Create `ChatPanel.tsx`
5. Refactor `App.tsx` to use new components

### Phase 3: Performance Optimization (Priority: Medium)
1. Increase Veo semaphore to 3 in `media_engine.py`
2. Add smart rate limit backoff
3. Adjust segment duration in `main.py`
4. Add connection warmup in `story_generator.py`

### Phase 4: Polish & Testing (Priority: Medium)
1. Add error handling for chat endpoint
2. Test video generation with 15-25 segments
3. Test chat context persistence
4. E2E testing of full flow

---

## File Changes Summary

### New Files
- `app/models/story_context.py`
- `app/context_store.py`
- `app/chat_service.py`
- `frontend-react/src/components/VideoPlayer.tsx`
- `frontend-react/src/components/TranscriptPanel.tsx`
- `frontend-react/src/components/ChatPanel.tsx`
- `frontend-react/src/components/ProgressOverlay.tsx`
- `frontend-react/src/styles/components.css`

### Modified Files
- `main.py` - Add chat endpoints, store context, return story_id
- `app/media_engine.py` - Increase concurrent limit, add backoff
- `app/story_generator.py` - Add warmup, optimize prompts
- `frontend-react/src/App.tsx` - Refactor to use components
- `frontend-react/src/index.css` - Add custom CSS properties

---

## Success Criteria

1. **Video Generation**: 3-5 minute videos complete in 5-8 minutes
2. **Chat Feature**: Users can ask questions and receive streaming responses
3. **Transcript Display**: Synchronized with video playback
4. **UI Polish**: Clean, consistent styling across all components
5. **Performance**: No degradation in existing functionality

---

## Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| `google-genai` | Gemini API for chat | Already installed |
| `framer-motion` | Animations | Already installed |
| `lucide-react` | Icons | Already installed |
| `axios` | HTTP client | Already installed |

No new dependencies required.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Veo rate limits with 3 concurrent | Medium | Slower generation | Implement exponential backoff |
| Context memory with long chats | Low | Memory pressure | Limit history to last 20 messages |
| Chat context loss on server restart | Medium | User confusion | Document session behavior (acceptable for MVP) |
| Frontend bundle size | Low | Slower load | Code splitting if needed |

---

*Design approved: 2026-03-08*