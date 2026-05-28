#!/bin/bash
# NeuroScale Agents — Cloud Run Deployment
# Deploys the AI orchestrator (not the Streamlit dashboard — that lives on Streamlit Cloud)
#
# Usage:
#   bash deploy/cloud-run.sh <GCP_PROJECT_ID> [REGION]
#
# Required env vars (set before running, or pass inline):
#   GEMINI_API_KEY          — Gemini 2.0 Flash key
#   ARIZE_API_KEY           — Arize Phoenix API key
#   ARIZE_SPACE_ID          — Arize space ID
#   VERTEX_RAG_DATASTORE    — Vertex AI Search serving config path
#                             format: projects/P/locations/L/collections/C/engines/E/servingConfigs/S
#   GCP_SA_EMAIL            — Service account email with Vertex AI + Discovery Engine roles

set -e

PROJECT_ID="${1:-your-gcp-project-id}"
REGION="${2:-us-central1}"
SERVICE_NAME="neuroscale-orchestrator"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 NeuroScale — deploying AI orchestrator to Cloud Run"
echo "   Project : ${PROJECT_ID}"
echo "   Region  : ${REGION}"
echo "   Service : ${SERVICE_NAME}"
echo "   Image   : ${IMAGE}"
echo ""

# ── Build & push using Dockerfile.orchestrator ────────────────────────────────
gcloud builds submit \
  --tag "${IMAGE}" \
  --gcs-log-dir "gs://${PROJECT_ID}-cloudbuild-logs" \
  -f Dockerfile.orchestrator \
  . \
  --project "${PROJECT_ID}"

echo "✅ Image pushed: ${IMAGE}"

# ── Deploy to Cloud Run ───────────────────────────────────────────────────────
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --service-account "${GCP_SA_EMAIL:-}" \
  --set-env-vars "\
DEMO_MODE=false,\
GCP_PROJECT=${PROJECT_ID},\
GEMINI_API_KEY=${GEMINI_API_KEY:-},\
ARIZE_API_KEY=${ARIZE_API_KEY:-},\
ARIZE_SPACE_ID=${ARIZE_SPACE_ID:-},\
VERTEX_RAG_DATASTORE=${VERTEX_RAG_DATASTORE:-}" \
  --project "${PROJECT_ID}"

echo ""
echo "✅ Orchestrator live:"
gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)"

echo ""
echo "📋 Next steps:"
echo "   1. Set CORS origin in orchestrator.py if calling from browser"
echo "   2. Update ORCHESTRATOR_URL in dashboard/app.py to the URL above"
echo "   3. Optionally deploy dashboard: bash deploy/cloud-run-dashboard.sh ${PROJECT_ID}"
