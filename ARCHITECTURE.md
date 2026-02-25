# RAWI Architecture

## Overview

RAWI is built on Google's AI ecosystem, using the Agent Development Kit (ADK) to orchestrate multiple specialized agents that work together to create immersive, multimodal educational stories.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Frontend Layer (Vanilla HTML/JS)"
        UI[User Interface]
        STREAM[Stream Receiver]
        PLAYER[Story Player<br/>Video + Text Bubbles]
        PROGRESS[Progress Indicator]
    end
    
    subgraph "API Layer (FastAPI)"
        API[REST API / WebSocket]
        ENDPOINTS[/tell-story<br/>/health/]
    end
    
    subgraph "ADK Orchestration Layer"
        RAWI[RawiAgent<br/>Main Orchestrator]
        DIRECTOR[Director Agent<br/>Story Planning]
        NARRATOR[Narrator Agent<br/>Content Creation]
        ARTIST[Artist Agent<br/>Visual Design]
        STORYBOARD[Storyboard Agent<br/>Visual Descriptions]
    end
    
    subgraph "AI Services (Google Vertex AI)"
        GEMINI3[Gemini 3 Flash<br/>Story Generation]
        GEMINITTS[Gemini 2.5 Flash-TTS<br/>Voiceover]
        IMAGEN[Imagen<br/>Storyboard Images]
        VEO[Veo<br/>Video Generation]
    end
    
    subgraph "Media Processing Layer"
        MERGER[Video Merger<br/>FFmpeg + Crossfade]
        ENCODER[Audio Encoder<br/>MP3/AAC]
    end
    
    subgraph "Storage Layer (Google Cloud Storage)"
        GCS[Cloud Storage Bucket<br/>rawi-story-assets/]
        ASSETS[story-assets/<br/>  storyboards/<br/>  videos/<br/>  voiceovers/<br/>  final/]
    end
    
    subgraph "Deployment Layer (Google Cloud Run)"
        CLOUDRUN[Cloud Run Service]
        BUILD[Cloud Build<br/>Docker Build]
        REGISTRY[Artifact Registry]
    end
    
    UI -->|HTTP/WebSocket| API
    API --> ENDPOINTS
    ENDPOINTS --> RAWI
    
    RAWI -->|orchestrates| DIRECTOR
    RAWI -->|orchestrates| NARRATOR
    RAWI -->|orchestrates| ARTIST
    RAWI -->|orchestrates| STORYBOARD
    
    DIRECTOR --> NARRATOR
    DIRECTOR --> STORYBOARD
    
    NARRATOR --> GEMINI3
    STORYBOARD --> GEMINI3
    
    ARTIST --> IMAGEN
    ARTIST --> VEO
    
    IMAGEN -->|uploads| GCS
    VEO -->|uploads| GCS
    GEMINITTS -->|uploads| GCS
    
    MERGER -->|downloads| GCS
    MERGER -->|uploads merged| GCS
    
    GCS --> ASSETS
    
    API -->|streams| STREAM
    STREAM --> PLAYER
    PLAYER --> PROGRESS
    PLAYER --> UI
    
    CLOUDRUN --> RAWI
    BUILD --> REGISTRY
    REGISTRY --> CLOUDRUN
    
    style RAWI fill:#ff6b6b
    style GEMINI3 fill:#4ecdc4
    style VEO fill:#45b7d1
    style UI fill:#96ceb4
    style API fill:#ffe66d
```

## Data Flow

### 1. Story Generation Flow

```mermaid
sequenceDiagram
    participant User as User
    participant UI as Frontend
    participant API as FastAPI
    participant Rawi as RawiAgent
    participant Director as Director Agent
    participant StoryGen as Story Generator
    participant Storyboard as Storyboard Agent
    participant Media as Media Engine
    participant Merger as Video Merger
    participant GCS as Cloud Storage
    
    User->>UI: Request story (topic, audience)
    UI->>API: POST /tell-story
    API->>Rawi: tell_story(request)
    
    Rawi->>Director: plan_story(topic, audience)
    Director->>Director: Break into segments
    Director-->>Rawi: story_plan (5-7 segments)
    
    loop For each segment
        Rawi->>StoryGen: generate_narration(segment)
        StoryGen->>StoryGen: Create engaging text
        StoryGen-->>Rawi: narration_text
        
        Rawi->>Storyboard: generate_storyboard(narration)
        Storyboard->>Storyboard: Create visual description
        Storyboard-->>Rawi: storyboard_prompt
        
        Rawi->>Media: generate_image(prompt)
        Media->>Imagen: Generate image
        Imagen-->>Media: image_url
        Media->>GCS: Upload image
        GCS-->>Media: gs://.../storyboard.png
        Media-->>Rawi: image_url
        
        Rawi->>Media: generate_voiceover(text)
        Media->>GeminiTTS: Generate audio
        GeminiTTS-->>Media: audio_blob
        Media->>GCS: Upload audio
        GCS-->>Media: gs://.../voiceover.mp3
        Media-->>Rawi: audio_url
        
        Rawi->>Media: generate_video(prompt)
        Media->>Veo: Generate video
        Veo-->>Media: video_url
        Media->>GCS: Upload video
        GCS-->>Media: gs://.../segment.mp4
        Media-->>Rawi: video_url
    end
    
    Rawi->>Merger: merge_segments(video_urls)
    Merger->>GCS: Download all segments
    Merger->>Merger: FFmpeg merge with crossfade
    Merger->>GCS: Upload final video
    GCS-->>Merger: gs://.../final_story.mp4
    Merger-->>Rawi: final_video_url
    
    Rawi->>API: Return StoryOutput
    API-->>UI: JSON response with URLs
    UI->>User: Display story
```

### 2. Interleaved Output Stream

```mermaid
graph LR
    subgraph "Input"
        REQ[Story Request]
    end
    
    subgraph "Processing"
        PLAN[Story Plan<br/>5-7 segments]
    end
    
    subgraph "Media Generation"
        TEXT[Text Narration]
        IMG[Storyboard Images]
        AUDIO[Voiceover Audio]
        VID[Video Segments]
    end
    
    subgraph "Interleaving"
        SEQ[Timeline Sequence]
        SYNC[Timestamp Sync]
    end
    
    subgraph "Output Stream"
        S1[Segment 1<br/>0.0-3.0s<br/>NARRATION]
        S2[Segment 2<br/>0.0-3.0s<br/>IMAGE]
        S3[Segment 3<br/>0.0-3.0s<br/>VOICEOVER]
        S4[Segment 4<br/>3.5-7.5s<br/>NARRATION]
        S5[Segment 5<br/>3.5-7.5s<br/>VIDEO]
    end
    
    REQ --> PLAN
    PLAN --> TEXT
    PLAN --> IMG
    PLAN --> AUDIO
    PLAN --> VID
    
    TEXT --> SEQ
    IMG --> SEQ
    AUDIO --> SEQ
    VID --> SEQ
    
    SEQ --> SYNC
    
    SYNC --> S1
    SYNC --> S2
    SYNC --> S3
    SYNC --> S4
    SYNC --> S5
```

## Component Details

### Frontend Layer

**Responsibilities:**
- User interface for story requests
- Real-time streaming and playback
- Video player with synchronized text bubbles
- Progress tracking

**Technologies:**
- Vanilla HTML5, JavaScript, CSS3
- WebSocket/SSE for streaming
- HTML5 Video API
- Canvas API for overlays

### API Layer

**Responsibilities:**
- RESTful API endpoints
- WebSocket for streaming
- Request validation
- Error handling
- CORS management

**Technologies:**
- FastAPI
- WebSocket support
- Pydantic for validation

### ADK Orchestration Layer

**Responsibilities:**
- Agent coordination
- Tool management
- Context management
- Flow control

**Agents:**
- **RawiAgent**: Main orchestrator
- **DirectorAgent**: Story planning and segmentation
- **NarratorAgent**: Content generation
- **ArtistAgent**: Visual content direction
- **StoryboardAgent**: Visual description generation

### AI Services Layer

**Responsibilities:**
- Story content generation
- Image generation
- Video generation
- Text-to-speech

**Services:**
- Gemini 3 Flash: Story generation
- Imagen: Storyboard illustrations
- Veo: Video sequence generation
- Gemini 2.5 Flash-TTS: Emotive voiceover

### Media Processing Layer

**Responsibilities:**
- Video segment merging
- Audio encoding
- Format conversion
- Transition effects

**Technologies:**
- FFmpeg
- Python subprocess
- Async I/O

### Storage Layer

**Responsibilities:**
- Media asset storage
- URL generation
- Access control
- Lifecycle management

**Structure:**
```
gs://<project>-story-assets/
├── storyboards/
│   ├── <story-id>/frame1.png
│   └── <story-id>/frame2.png
├── videos/
│   ├── <story-id>/segment1.mp4
│   └── <story-id>/segment2.mp4
├── voiceovers/
│   ├── <story-id>/voiceover1.mp3
│   └── <story-id>/voiceover2.mp3
└── final/
    └── <story-id>/final_story.mp4
```

### Deployment Layer

**Responsibilities:**
- Container orchestration
- Auto-scaling
- Load balancing
- Health monitoring

**Technologies:**
- Google Cloud Run
- Docker
- Cloud Build
- Artifact Registry

## Key Design Decisions

### 1. Agent-Based Architecture

**Why:** ADK provides structured agent orchestration with tool integration.

**Benefits:**
- Clear separation of concerns
- Reusable agent components
- Built-in context management
- Tool composition

### 2. Interleaved Output Stream

**Why:** Synchronized multimedia provides more engaging storytelling.

**Benefits:**
- Immersive experience
- Flexible media combinations
- Progressive enhancement
- Accessibility support

### 3. Storyboard-Driven Video Generation

**Why:** Veo works best with detailed visual descriptions.

**Benefits:**
- Consistent visual style
- Better video quality
- Easier iteration
- Reusable assets

### 4. Cloud-Native Deployment

**Why:** Google Cloud provides managed services for AI and storage.

**Benefits:**
- Automatic scaling
- Pay-per-use pricing
- Integrated AI services
- Global availability

### 5. Shell Script Deployment

**Why:** Faster setup for hackathon, easier to understand than Terraform.

**Benefits:**
- Quick setup
- Easy debugging
- Transparent operations
- Lower complexity

## Performance Considerations

### Latency Optimization

- Parallel processing of independent segments
- Caching of generated assets
- Streaming responses to frontend
- Pre-warming Cloud Run instances

### Cost Optimization

- Use of Cloud Run (serverless)
- Efficient video merging
- Asset lifecycle policies
- CDN integration for delivery

### Scalability

- Stateless API design
- Horizontal scaling on Cloud Run
- Async processing pipeline
- Queue-based work distribution

## Security Considerations

### Authentication

- Service account authentication
- API key management
- IAM role-based access
- Signed URLs for assets

### Data Privacy

- No user data persistence
- Temporary asset storage
- Encrypted storage at rest
- HTTPS/TLS in transit

## Monitoring & Observability

### Metrics

- Story generation latency
- API response times
- Media generation success rates
- Resource utilization

### Logging

- Structured logs (JSON)
- Stackdriver integration
- Error tracking
- Performance traces

### Alerts

- API health failures
- Generation timeouts
- Storage quota limits
- Error rate thresholds

## Future Enhancements

### Planned Features

- [ ] Real-time voice input
- [ ] Interactive story branches
- [ ] Multi-language support
- [ ] Custom character voices
- [ ] AR/VR integration
- [ ] Offline story viewing
- [ ] Story analytics
- [ ] Collaboration features

### Technical Improvements

- [ ] GraphQL API
- [ ] Redis caching layer
- [ ] Event-driven architecture
- [ ] Kubernetes deployment option
- [ ] Terraform IaC
- [ ] CI/CD pipeline
- [ ] Automated testing
- [ ] Performance profiling

---

**Last Updated**: 2025-02-25
