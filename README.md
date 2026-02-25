# RAWI - The Storyteller

## Project Vision

RAWI (Rawi = "Storyteller" in Arabic) transforms dry curriculum into immersive, multimodal educational stories using Google's AI ecosystem. Built for the Gemini Live Agent Challenge, RAWI moves beyond simple text-in/text-out AI by creating interleaved output streams that combine narration, images, voiceover, and video into a unified storytelling experience.

## The Rawi Story

Rawi is an ancient, wise storyteller who has traveled through time, collecting tales from every corner of human history. When a student asks about a complex topic, Rawi doesn't just explain it—he weaves it into a living story, complete with vivid imagery and emotive voices that bring the subject to life.

Rawi draws upon centuries of wisdom to transform abstract concepts into relatable narratives. Whether explaining the French Revolution through a bustling bakery, or describing the solar system as a cosmic playground, Rawi's stories engage young minds and make learning an adventure.

## Tech Stack

- **Orchestration**: Google Agent Development Kit (ADK) for Python
- **Brain**: Gemini 3 Flash (via Vertex AI)
- **Voices**: Gemini 2.5 Flash-TTS for emotive, character-driven narration
- **Visuals**: Imagen (storyboard illustrations) and Veo (video sequences)
- **Deployment**: Google Cloud Run with Shell Scripts
- **Storage**: Google Cloud Storage for media assets

## Features

- ✨ **Immersive Storytelling**: Transform educational topics into engaging narratives
- 🎬 **Multimodal Output**: Interleaved streams of text, images, voiceover, and video
- 🎨 **Visual Storytelling**: Storyboard-driven video generation with Imagen and Veo
- 🎤 **Emotive Voiceover**: Character-driven narration with Gemini TTS
- 🚀 **Cloud-Native**: Deployed on Google Cloud Run with automated scripts
- 🎯 **Age-Appropriate**: Tailored content for different age groups

## Quick Start (5 minutes)

### Prerequisites

- Python 3.10+
- Google Cloud project with Vertex AI enabled
- Google Cloud SDK (gcloud CLI)
- Docker (for deployment)
- API credentials (Vertex AI, Cloud Storage)

### Installation

```bash
# Clone and setup
git clone <repo>
cd rawi
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Configure Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Environment Variables

Edit `.env` file:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Optional: Customize
STORAGE_BUCKET_NAME=your-project-story-assets
MAX_VIDEO_DURATION_MINUTES=5
DEFAULT_LANGUAGE=en
```

### Local Development

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Run the agent
python main.py
```

### Deploy to Google Cloud

```bash
# One-command setup and deployment
./infra/setup.sh
./infra/deploy.sh
```

## Usage Examples

### Example 1: French Revolution

```python
from main import rawi_agent, StoryRequest

result = await rawi_agent.tell_story(
    StoryRequest(
        topic="French Revolution",
        audience="10-year-old",
        metaphor="a bakery",
        duration_minutes=5
    )
)

print(f"Video URL: {result.video_url}")
print(f"Narration: {result.narration_text}")
```

### Example 2: Solar System

```bash
curl -X POST https://your-app-url/tell-story \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Solar System",
    "audience": "8-year-old",
    "metaphor": "a playground",
    "duration_minutes": 3
  }'
```

### Example 3: Water Cycle

```javascript
// frontend example
const response = await fetch('/tell-story', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    topic: 'Water Cycle',
    audience: '12-year-old',
    metaphor: 'a magical journey'
  })
});

const story = await response.json;
player.loadStory(story);
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture diagrams using Mermaid.js.

## Project Structure

```
rawi/
├── README.md                      # Project documentation
├── ARCHITECTURE.md                # Architecture diagram
├── main.py                        # Entry point with FastAPI app
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── Dockerfile                     # Docker configuration
│
├── app/
│   ├── __init__.py
│   ├── director_agent.py          # ADK main orchestrator
│   ├── story_generator.py         # Gemini 3 Flash story logic
│   ├── media_engine.py            # Imagen/Veo + TTS integration
│   ├── storyboard_agent.py        # Storyboard prompt generation
│   └── video_merger.py            # FFmpeg video merging
│
├── infra/
│   ├── setup.sh                   # Google Cloud project setup
│   ├── deploy.sh                  # Deploy to Cloud Run
│   └── teardown.sh                # Clean up resources
│
├── frontend/
│   ├── index.html                 # Main UI
│   ├── styles.css                 # Styling
│   ├── app.js                     # Frontend logic
│   └── components/
│       ├── story-player.js        # Video + text bubble player
│       └── progress-bar.js        # Story progress indicator
│
└── tests/
    ├── test_story_generator.py
    ├── test_media_engine.py
    └── test_director_agent.py
```

## API Endpoints

### POST /tell-story

Generate a multimodal story for a given topic.

**Request Body:**
```json
{
  "topic": "French Revolution",
  "audience": "10-year-old",
  "metaphor": "a bakery",
  "duration_minutes": 5,
  "language": "en"
}
```

**Response:**
```json
{
  "video_url": "https://storage.googleapis.com/.../final_story.mp4",
  "storyboard_urls": ["https://storage.googleapis.com/.../frame1.png"],
  "narration_text": "Once upon a time...",
  "voiceover_url": "https://storage.googleapis.com/.../voiceover.mp3",
  "segments": [...]
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "agent": "rawi_storyteller"
}
```

## Interleaved Output Format

RAWI produces an interleaved stream that combines multiple media types:

```json
{
  "interleaved_stream": [
    {
      "type": "NARRATION",
      "content": "Once upon a time...",
      "timestamp": 0.0,
      "duration": 3.0,
      "metadata": {"emotion": "warm"}
    },
    {
      "type": "IMAGE_URL",
      "content": "https://storage.googleapis.com/.../frame1.png",
      "timestamp": 0.0,
      "duration": 3.0,
      "metadata": {"style": "illustration"}
    },
    {
      "type": "VOICEOVER_BLOB",
      "content": "https://storage.googleapis.com/.../voiceover1.mp3",
      "timestamp": 0.0,
      "duration": 3.0,
      "metadata": {"format": "mp3"}
    }
  ]
}
```

## How It Works

1. **Input**: User provides a topic, target audience, and optional metaphor
2. **Story Planning**: Director Agent breaks topic into 5-7 story segments
3. **Narration Generation**: Story Generator creates engaging narration for each segment
4. **Storyboard Creation**: Storyboard Agent generates visual descriptions
5. **Media Generation**: 
   - Imagen creates storyboard illustrations
   - Veo generates video segments
   - Gemini TTS creates emotive voiceovers
6. **Video Merging**: VideoMerger combines segments with smooth transitions
7. **Output**: Interleaved stream of text, images, audio, and video

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black app/

# Lint
flake8 app/

# Type check
mypy app/
```

### Adding New Features

1. Create a new agent in `app/`
2. Add tools to `RawiAgent` in `main.py`
3. Update API endpoints if needed
4. Add tests in `tests/`
5. Update documentation

## Deployment

### Google Cloud Run

```bash
# Setup project
./infra/setup.sh <project-id> <region>

# Deploy
./infra/deploy.sh <project-id> <region>

# Clean up
./infra/teardown.sh <project-id>
```

### Manual Deployment

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/PROJECT_ID/rawi-storyteller

# Deploy to Cloud Run
gcloud run deploy rawi-storyteller \
  --image gcr.io/PROJECT_ID/rawi-storyteller \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Troubleshooting

### Common Issues

**Vertex AI API Error**
- Ensure Vertex AI API is enabled: `gcloud services enable aiplatform.googleapis.com`
- Check credentials are correct in `.env`

**Video Generation Timeout**
- Increase timeout in `main.py`: `uvicorn.run(..., timeout=600)`
- Reduce segment count in `story_generator.py`

**Storage Permission Denied**
- Verify service account has `roles/storage.objectAdmin`
- Check bucket exists: `gsutil ls gs://PROJECT_ID-story-assets`

## Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Google Agent Development Kit (ADK)
- Gemini 3 Flash, Imagen, Veo, and Gemini TTS
- Google Cloud Platform

## Contact

For questions or feedback, please open an issue on GitHub.

---

**RAWI - Where Every Lesson Becomes an Adventure** 📖✨
