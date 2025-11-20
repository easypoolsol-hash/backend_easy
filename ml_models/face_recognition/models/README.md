# Face Recognition Models - Deployment Guide

**IMPORTANT: Models are NOT stored in Git** - they are stored in Google Cloud Storage.

## Model Storage Strategy (Production)

### ✅ Google Cloud Storage (Recommended)
```
Cloud Run Container: 50 MB (code only)
    ↓ Downloads on startup
GCS Bucket: gs://easypool-ml-models/
    └── face-recognition/v1/
        ├── mobilefacenet.tflite (5 MB)
        ├── arcface_resnet100.onnx (249 MB)
        └── arcface_w600k_r50.onnx (167 MB)
```

**Benefits:**
- Fast deployments (50 MB vs 471 MB)
- Version models separately from code
- Cold start: ~10 seconds, Warm start: instant
- Cost: ~$1/month

## Production Models

| Model | Format | Size | Dims | Accuracy | Use Case |
|-------|--------|------|------|----------|----------|
| MobileFaceNet | TFLite | 5 MB | 192D | ~90% | Kiosk (fast) |
| ArcFace ResNet100 | ONNX | 249 MB | 512D | 99.82% LFW | Backend (highest) |
| ArcFace ResNet50 | ONNX | 167 MB | 512D | 99.77% LFW | Backend (banking) |

**Total: 421 MB**

### Multi-Model Consensus (Backend Verification)

All 3 models run in consensus for banking-grade accuracy:
- **3 agree** → HIGH confidence (99.9%+)
- **2 agree** → MEDIUM confidence (99%+)
- **No consensus** → FLAGGED for manual review

## Development Setup

### 1. Download Models Locally

```bash
cd ml_models/face_recognition/models
python download_onnx_models.py
```

Downloads from official sources:
- ArcFace ResNet50: Hugging Face (facefusion/models-3.0.0)
- ArcFace ResNet100: OpenVINO Model Zoo
- MobileFaceNet: Already present

### 2. Git Ignore

All model files (*.onnx, *.tflite, *.h5) are in `.gitignore`:
```gitignore
ml_models/face_recognition/models/*.onnx
ml_models/face_recognition/models/*.tflite
ml_models/face_recognition/models/*.h5
```

## Production Deployment

### 1. Upload Models to GCS (One-time setup)

```bash
# Create bucket
gsutil mb -p easypool-backend -l us-central1 gs://easypool-ml-models

# Upload models
gsutil cp mobilefacenet.tflite gs://easypool-ml-models/face-recognition/v1/
gsutil cp arcface_resnet100.onnx gs://easypool-ml-models/face-recognition/v1/
gsutil cp arcface_w600k_r50.onnx gs://easypool-ml-models/face-recognition/v1/

# Grant Cloud Run service account access
gsutil iam ch \
  serviceAccount:easypool-cloud-run-sa@easypool-backend.iam.gserviceaccount.com:objectViewer \
  gs://easypool-ml-models
```

### 2. Cloud Run Startup (Automatic)

Models are downloaded automatically on container startup (see `ml_models/model_loader.py`):

```python
def download_models_from_gcs():
    """Download models from GCS on Cloud Run startup"""
    bucket = storage_client.bucket("easypool-ml-models")

    for model_file in ["mobilefacenet.tflite", "arcface_resnet100.onnx", "arcface_w600k_r50.onnx"]:
        blob = bucket.blob(f"face-recognition/v1/{model_file}")
        blob.download_to_filename(f"ml_models/face_recognition/models/{model_file}")
```

**Performance:**
- Cold start: ~10 seconds (421 MB download)
- Warm start: Instant (models cached in memory)
- Container memory: 1.5 GB (for all 3 models)

### 3. Model Versioning

Update models without code deploy:

```bash
# Upload new version
gsutil cp arcface_resnet100_v2.onnx gs://easypool-ml-models/face-recognition/v2/

# Update Cloud Run environment variable
gcloud run services update backend-service \
  --set-env-vars MODEL_VERSION=v2
```

## Infrastructure Costs

**Google Cloud Storage:**
- Storage: $0.02/GB/month × 0.421 GB = **$0.01/month**
- Download: $0.12/GB × 0.421 GB = **$0.05 per cold start**
- **Total: ~$1/month** (assuming 20 cold starts)

**Cloud Run Memory:**
- Models in RAM: ~1.5 GB
- Minimum instance: 1 GB → 2 GB
- Included in Cloud Run pricing

## Security

- Models stored in **private** GCS bucket
- Only Cloud Run service account has `objectViewer` role
- Downloaded over authenticated HTTPS
- No public access

## Monitoring

Check model downloads in logs:

```bash
gcloud run services logs read backend-service \
  --filter="textPayload:Downloading model" \
  --limit=50
```

## Model Details

### MobileFaceNet (TFLite)
- **Size:** 5 MB
- **Input:** 112x112 RGB, normalized [-1, 1]
- **Output:** 192D embedding
- **Architecture:** MobileNet-based
- **Use:** Fast kiosk verification

### ArcFace ResNet100 (ONNX)
- **Size:** 249 MB
- **Input:** 112x112 RGB, normalized [-1, 1]
- **Output:** 512D embedding
- **Dataset:** MS1MV3
- **Accuracy:** 99.82% LFW (highest)
- **Use:** Backend verification (primary)

### ArcFace ResNet50 (ONNX)
- **Size:** 167 MB
- **Input:** 112x112 BGR, normalized [0, 1]
- **Output:** 512D embedding
- **Dataset:** W600K
- **Accuracy:** 99.77% LFW
- **Use:** Backend verification (secondary)

## Troubleshooting

**Q: Models missing locally?**
```bash
python ml_models/face_recognition/models/download_onnx_models.py
```

**Q: Cloud Run can't download from GCS?**
Check service account permissions:
```bash
gsutil iam get gs://easypool-ml-models
```

**Q: Out of memory on Cloud Run?**
Increase memory to 2 GB:
```bash
gcloud run services update backend-service --memory=2Gi
```
