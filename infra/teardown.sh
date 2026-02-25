#!/bin/bash
# Teardown Script for RAWI - Remove all Google Cloud resources

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
SERVICE_NAME="rawi-storyteller"
BUCKET_NAME="${PROJECT_ID}-story-assets"
SA_EMAIL="rawi-agent@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🗑️  Tearing down RAWI resources..."
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"

read -p "⚠️  This will delete all RAWI resources. Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Teardown cancelled"
    exit 0
fi

# Delete Cloud Run service
echo "🌐 Deleting Cloud Run service..."
gcloud run services delete $SERVICE_NAME \
    --region=$REGION \
    --quiet || echo "⚠️  Cloud Run service may not exist"

# Delete storage bucket
echo "📦 Deleting storage bucket..."
gsutil -m rm -r gs://$BUCKET_NAME || echo "⚠️  Bucket may not exist or is already empty"

# Delete service account
echo "🔐 Deleting service account..."
gcloud iam service-accounts delete $SA_EMAIL \
    --project=$PROJECT_ID \
    --quiet || echo "⚠️  Service account may not exist"

# Delete Artifact Registry (optional - commented out by default)
# echo "🏗️  Deleting Artifact Registry..."
# gcloud artifacts repositories delete rawi-repo \
#     --location=$REGION \
#     --quiet || echo "⚠️  Repository may not exist"

echo ""
echo "✅ Teardown complete!"
echo "⚠️  Note: API services are still enabled. Disable them manually if needed:"
echo "  gcloud services disable aiplatform.googleapis.com"
echo "  gcloud services disable vertexai.googleapis.com"
echo "  gcloud services disable storage.googleapis.com"
echo ""
