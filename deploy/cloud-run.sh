#!/bin/bash
# Deploy NeuroScale Agents dashboard to Google Cloud Run
# Usage: bash deploy/cloud-run.sh <YOUR_GCP_PROJECT_ID>

set -e

PROJECT_ID="${1:-your-gcp-project-id}"
REGION="us-central1"
SERVICE_NAME="neuroscale-agents"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Building and deploying NeuroScale Agents to Cloud Run..."
echo "   Project: ${PROJECT_ID}"
echo "   Region:  ${REGION}"
echo "   Image:   ${IMAGE}"

# Build and push
gcloud builds submit --tag "${IMAGE}" .

# Deploy to Cloud Run
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8501 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars DEMO_MODE=true \
  --project "${PROJECT_ID}"

echo ""
echo "✅ Deployed! Dashboard URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)"
