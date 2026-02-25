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

# Build Docker image
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/rawi-repo/${SERVICE_NAME}:latest"

echo "🐳 Building Docker image..."
docker build -t $IMAGE_NAME .

# Authenticate with Artifact Registry
echo "🔐 Authenticating with Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Push to Artifact Registry
echo "⬆️  Pushing to Artifact Registry..."
docker push $IMAGE_NAME

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
    --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
    --set-env-vars=GOOGLE_CLOUD_LOCATION=$REGION \
    --set-env-vars=STORAGE_BUCKET_NAME=${PROJECT_ID}-story-assets \
    --set-env-vars=LOG_LEVEL=INFO

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --format='value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo "📚 API Docs: $SERVICE_URL/docs"
echo "🏥 Health Check: $SERVICE_URL/health"
echo ""
echo "🧪 Test the service:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "📖 Example request:"
echo "  curl -X POST $SERVICE_URL/tell-story \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"topic\": \"French Revolution\", \"audience\": \"10-year-old\", \"metaphor\": \"a bakery\"}'"
echo ""
