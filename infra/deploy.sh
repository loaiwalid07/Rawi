#!/bin/bash
# Deployment Script for RAWI to Google Cloud Run

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
SERVICE_NAME="rawi-storyteller"

echo "🚀 Deploying RAWI to Cloud Run..."
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please run ./infra/setup.sh first."
    exit 1
fi

# Load GEMINI_API_KEY from .env if set
GEMINI_KEY=$(grep GEMINI_API_KEY .env | cut -d '=' -f2)

# Build Docker image (multi-stage: frontend + backend)
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/rawi-repo/${SERVICE_NAME}:latest"

echo "🐳 Building Docker image (frontend + backend)..."
docker build -t $IMAGE_NAME .

# Authenticate with Artifact Registry
echo "🔐 Authenticating with Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Push to Artifact Registry
echo "⬆️  Pushing to Artifact Registry..."
docker push $IMAGE_NAME

# Build env vars string
ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_LOCATION=$REGION"
ENV_VARS="$ENV_VARS,STORAGE_BUCKET_NAME=${PROJECT_ID}-story-assets"
ENV_VARS="$ENV_VARS,LOG_LEVEL=INFO"

if [ -n "$GEMINI_KEY" ]; then
    ENV_VARS="$ENV_VARS,GEMINI_API_KEY=$GEMINI_KEY"
fi

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image=$IMAGE_NAME \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=3600 \
    --min-instances=0 \
    --max-instances=10 \
    --set-env-vars="$ENV_VARS"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --format='value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "🌐 App URL: $SERVICE_URL"
echo "📡 API: $SERVICE_URL/tell-story"
echo "🏥 Health: $SERVICE_URL/health"
echo ""
echo "🧪 Test the service:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "📖 Generate a video:"
echo "  curl -X POST $SERVICE_URL/tell-story \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"topic\": \"How photosynthesis works\", \"duration_minutes\": 2}'"
echo ""
