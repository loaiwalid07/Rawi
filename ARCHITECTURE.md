# RAWI Architecture

> Last Updated: 2026-03-15

## System Overview

RAWI is an AI-powered educational video generator built on Google's AI ecosystem. It uses a multi-agent pipeline to transform any topic into a professional explainer video with voiceover, motion graphics, and text overlays.

---

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Frontend["Frontend — React + Vite + Tailwind"]
        UI["Topic Input"]
        SSE["SSE Progress Stream"]
        VP["Video Player"]
        TP["Transcript Panel"]
        CP["AI Chat Panel"]
    end

    subgraph Backend["Backend — FastAPI (Python)"]
        API["FastAPI Server\nmain.py"]
        TS["TaskStore\n(SSE Progress)"]
        CS["ChatService\n(AI Q&A)"]

        subgraph Pipeline["Multi-Agent Pipeline"]
            DA["DirectorAgent\nOrchestrator"]
            SG["StoryGenerator\nGemini 2.5 Flash"]
            SB["StoryboardAgent\nGemini 2.5 Flash"]
        end

        subgraph MediaEng["Media Engine"]
            IG["ImageGenerator\nImagen 3.0 Fast"]
            VG["VideoGenerator\nVeo 2"]
            TTS["VoiceGenerator\nGemini TTS"]
        end

        VM["VideoMerger\nFFmpeg"]
    end

    subgraph GCP["Google Cloud Platform"]
        VAI["Vertex AI APIs\n(Gemini / Imagen / Veo)"]
        GCS["Cloud Storage\n(Media Assets)"]
        CR["Cloud Run\n(Container Hosting)"]
    end

    UI -->|"POST /tell-story"| API
    API --> TS
    TS -->|"SSE events"| SSE

    API --> DA
    DA -->|"1. Plan script"| SG
    SG -->|"Educational script\n+ key_points\n+ visual_description"| DA
    DA -->|"2. Generate visuals"| SB
    SB -->|"Diagram/infographic\nprompts"| DA

    DA -->|"3. Create media\n(parallel)"| IG
    DA --> VG
    DA --> TTS

    IG -->|"Upload"| GCS
    VG -->|"Upload"| GCS
    TTS -->|"Upload"| GCS

    GCS -->|"Download segments"| VM
    VM -->|"Merge + subtitles\n+ voiceover"| GCS

    GCS -->|"Video URL"| VP
    API -->|"Narration text"| TP
    CS -->|"Streaming chat"| CP

    SG -.->|"API call"| VAI
    SB -.->|"API call"| VAI
    IG -.->|"API call"| VAI
    VG -.->|"API call"| VAI
    TTS -.->|"API call"| VAI
    Backend -.->|"Deployed on"| CR

    style Frontend fill:#0f172a,stroke:#3b82f6,color:#e2e8f0
    style Backend fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style GCP fill:#0f172a,stroke:#22c55e,color:#e2e8f0
    style Pipeline fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style MediaEng fill:#172554,stroke:#60a5fa,color:#e2e8f0
```

---

## Data Flow — Video Generation

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React Frontend
    participant API as FastAPI
    participant DA as DirectorAgent
    participant SG as StoryGenerator
    participant SB as StoryboardAgent
    participant ME as MediaEngine
    participant VM as VideoMerger
    participant GCS as Cloud Storage

    U->>FE: Enter topic
    FE->>API: POST /tell-story {topic}
    API-->>FE: {task_id}
    FE->>API: GET /stream-progress/{task_id} (SSE)

    Note over API: Status: PLANNING (10%)
    API->>DA: plan_story(topic, audience)
    DA->>SG: Generate educational script
    SG-->>DA: {segments[], visual_bible}
    Note right of SG: Each segment has:<br/>narration, key_points,<br/>visual_description

    Note over API: Status: STORYBOARDING (15-35%)
    loop Each segment (parallel)
        DA->>SB: generate_storyboard(narration, visual_bible)
        SB-->>DA: {visual_prompt, camera_angles}
    end

    Note over API: Status: GENERATING (40-80%)
    loop Each segment (parallel)
        DA->>ME: generate_story_media(image, video, voice prompts)
        ME->>GCS: Upload image, video, voiceover
        ME-->>DA: {image_url, video_url, voiceover_url}
    end

    Note over API: Status: MERGING (85%)
    DA->>VM: merge_all_segments(videos, voiceovers, narrations)
    VM->>GCS: Download all segments
    VM->>VM: FFmpeg merge + subtitles + audio
    VM->>GCS: Upload final.mp4
    VM-->>DA: final_video_url

    Note over API: Status: COMPLETED (100%)
    API-->>FE: SSE: {video_url, narration_text, interleaved_stream}
    FE->>U: Display video + transcript
```

---

## Component Details

### Frontend (React + Vite)

| Component | File | Purpose |
|-----------|------|---------|
| App | `App.tsx` | Main layout, SSE progress subscription, state management |
| VideoPlayer | `VideoPlayer.tsx` | HTML5 video playback with time tracking |
| TranscriptPanel | `TranscriptPanel.tsx` | Clickable narration segments synced to video |
| ChatPanel | `ChatPanel.tsx` | AI assistant for Q&A about the generated video |

**Key Features:**
- SSE-based real-time progress updates (planning → storyboarding → generating → merging → done)
- Auto-detects dev vs production API URL
- Collapsible right-side panel with Transcript + AI Chat tabs

---

### Backend Agents

| Agent | File | Model | Purpose |
|-------|------|-------|---------|
| **DirectorAgent** | `director_agent.py` | — | Orchestrates the full pipeline: planning → storyboarding → media → merge |
| **StoryGenerator** | `story_generator.py` | Gemini 2.5 Flash | Generates educational scripts with narration, key_points, visual_description per segment |
| **StoryboardAgent** | `storyboard_agent.py` | Gemini 2.5 Flash | Creates visual prompts for infographics, diagrams, and motion graphics |

**Prompt Engineering Highlights:**
- Story prompts request educational explainer content (not fairy tales)
- Each segment includes `key_points` (used for subtitle overlays) and `visual_description` (used for Imagen/Veo prompts)
- Video prompts include **context from the previous segment** for topical continuity
- Storyboard prompts request diagrams, data visualizations, and labeled figures

---

### Media Engine

| Generator | File | Model | Output |
|-----------|------|-------|--------|
| **ImageGenerator** | `media_engine.py` | Imagen 3.0 Fast | Educational infographic images |
| **VideoGenerator** | `media_engine.py` | Veo 2 | Motion graphics video segments (~5s each) |
| **VoiceGenerator** | `media_engine.py` | Gemini TTS | Voiceover narration audio (MP3) |

All three generators run **in parallel** per segment for speed.

---

### Video Merger

| Feature | Implementation |
|---------|---------------|
| **Segment merging** | FFmpeg crossfade transitions between segments |
| **Subtitles** | SRT file with key_points, styled: Arial Bold 28px, semi-transparent background |
| **Voiceover mixing** | Audio delay-aligned per segment, mixed with `amix` |
| **3-tier fallback** | Full merge with audio → video-only with subtitles → simple concat |

---

### TaskStore (SSE Progress)

The backend uses an in-memory `TaskStore` with `asyncio.Queue` to push real-time progress events to the frontend via Server-Sent Events:

```
PENDING (0%) → PLANNING (10%) → STORYBOARDING (15-35%) → GENERATING (40-80%) → MERGING (85%) → COMPLETED (100%)
```

---

## Deployment

### Multi-Stage Docker Build

```mermaid
flowchart LR
    subgraph Stage1["Stage 1: Node 20"]
        NPM["npm install"]
        BUILD["npm run build"]
        DIST["dist/"]
    end

    subgraph Stage2["Stage 2: Python 3.10"]
        PIP["pip install"]
        COPY["Copy backend + dist/"]
        FFM["Install FFmpeg"]
        RUN["CMD python main.py"]
    end

    NPM --> BUILD --> DIST
    DIST -->|"COPY --from"| COPY
    PIP --> COPY --> FFM --> RUN

    style Stage1 fill:#1e3a5f,stroke:#60a5fa,color:#e2e8f0
    style Stage2 fill:#3b1f5e,stroke:#a78bfa,color:#e2e8f0
```

- **Stage 1**: Node 20 builds the React frontend → outputs `dist/`
- **Stage 2**: Python 3.10-slim with FFmpeg, copies backend code + frontend dist
- FastAPI serves the built frontend as static files from `frontend-react/dist/`

### Cloud Run Deployment

```bash
./infra/setup.sh YOUR_PROJECT_ID us-central1   # Creates GCP resources
./infra/deploy.sh YOUR_PROJECT_ID us-central1  # Builds + deploys
```

**Resources provisioned by `setup.sh`:**
- Service account with Vertex AI + Storage permissions
- Cloud Storage bucket for media assets
- Artifact Registry for Docker images
- Required API enablement

---

## Google Cloud Storage Layout

```
gs://<project>-story-assets/
├── storyboards/          # Imagen-generated infographic images
│   └── <uuid>.png
├── videos/               # Veo-generated video segments
│   └── <uuid>.mp4
├── voiceovers/           # TTS-generated audio narration
│   └── <uuid>.mp3
└── final/                # Merged final videos
    └── <uuid>.mp4
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Multi-agent pipeline** | Separation of concerns: story planning, visual prompting, and media generation are independent skills |
| **Parallel media generation** | Image + Video + Voice generated simultaneously per segment for speed |
| **Context overlap in prompts** | Each video prompt includes previous segment context for visual continuity |
| **Key-points-only subtitles** | Full narration plays as voiceover; subtitles show concise bullet points |
| **3-tier FFmpeg fallback** | Graceful degradation: audio merge → video-only → simple concat |
| **SSE with 1s delay** | Ensures the SSE subscriber connects before progress events fire |
| **Multi-stage Docker** | Single container serves both React frontend and Python backend |
| **Shell-script infra** | Fast setup for hackathon, easier to understand than Terraform |
