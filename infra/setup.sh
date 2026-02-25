#!/bin/bash
# Google Cloud Setup Script for RAWI

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}

echo "🚀 Setting up RAWI project: $PROJECT_ID"
echo "📍 Region: $REGION"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "🔐 Not authenticated. Running gcloud auth login..."
    gcloud auth login
fi

# Set project
echo "📡 Setting project to $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable APIs
echo "🔌 Enabling required APIs..."
gcloud services enable \
    aiplatform.googleapis.com \
    vertexai.googleapis.com \
    storage.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    texttospeech.googleapis.com || echo "⚠️  Some APIs may already be enabled"

# Create service account
echo "🔐 Creating service account..."
SA_NAME="rawi-agent"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe $SA_EMAIL &> /dev/null; then
    echo "✅ Service account $SA_EMAIL already exists"
else
    gcloud iam service-accounts create $SA_NAME \
        --display-name="RAWI Agent Service Account" \
        --description="Service account for RAWI Storyteller Agent" \
        --project=$PROJECT_ID
    
    echo "✅ Created service account: $SA_EMAIL"
fi

# Grant permissions
echo "🔓 Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.user" \
    --condition=None || echo "⚠️  Role may already be assigned"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectAdmin" \
    --condition=None || echo "⚠️  Role may already be assigned"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None || echo "⚠️  Role may already be assigned"

# Create Cloud Storage bucket
echo "📦 Creating storage bucket..."
BUCKET_NAME="${PROJECT_ID}-story-assets"

if gsutil ls gs://$BUCKET_NAME &> /dev/null; then
    echo "✅ Bucket $BUCKET_NAME already exists"
else
    gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME
    echo "✅ Created bucket: gs://$BUCKET_NAME"
fi

# Create folder structure in bucket
echo "📁 Creating folder structure..."
gsutil -m cp -n README.md gs://$BUCKET_NAME/README.txt 2>/dev/null || true
gsutil -m mkdir -p gs://$BUCKET_NAME/storyboards
gsutil -m mkdir -p gs://$BUCKET_NAME/videos
gsutil -m mkdir -p gs://$BUCKET_NAME/voiceovers
gsutil -m mkdir -p gs://$BUCKET_NAME/final
echo "✅ Created folder structure"

# Create Artifact Registry
echo "🏗️  Creating Artifact Registry..."
REPO_NAME="rawi-repo"

if gcloud artifacts repositories describe $REPO_NAME --location=$REGION &> /dev/null; then
    echo "✅ Repository $REPO_NAME already exists"
else
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="RAWI Docker images" \
        --project=$PROJECT_ID
    
    echo "✅ Created repository: $REPO_NAME"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=$REGION
GOOGLE_APPLICATION_CREDENTIALS=

# Storage Configuration
STORAGE_BUCKET_NAME=$BUCKET_NAME

# Media Generation
MAX_VIDEO_DURATION_MINUTES=5
DEFAULT_LANGUAGE=en
DEFAULT_VOICEOVER_EMOTION=warm

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=2

# Agent Configuration
STORY_SEGMENTS_MIN=5
STORY_SEGMENTS_MAX=7
SEGMENT_DURATION_SECONDS=15

# Rate Limiting
MAX_REQUESTS_PER_MINUTE=10
MAX_CONCURRENT_STORIES=5

# Monitoring
ENABLE_METRICS=true
LOG_LEVEL=INFO
EOF
    echo "✅ Created .env file"
    echo "⚠️  Please edit .env and set GOOGLE_APPLICATION_CREDENTIALS if needed"
else
    echo "✅ .env file already exists"
fi

# Summary
echo ""
echo "✨ Setup complete!"
echo ""
echo "📋 Configuration Summary:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Account: $SA_EMAIL"
echo "  Storage Bucket: gs://$BUCKET_NAME"
echo "  Artifact Registry: $REPO_NAME in $REGION"
echo ""
echo "🚀 Next steps:"
echo "  1. Edit .env file to configure your settings"
echo "  2. Run: ./infra/deploy.sh $PROJECT_ID $REGION"
echo "  3. Test: curl https://<SERVICE_URL>/health"
echo ""
