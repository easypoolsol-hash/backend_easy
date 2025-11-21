# AdaFace Model Setup Instructions

## Quick Start

AdaFace is configured but the model file needs to be downloaded manually.

### Step 1: Download AdaFace Model

**Option A: From Google Drive (Recommended)**
```bash
# Download from https://drive.google.com/drive/folders/1IaSwSLbWgc_SWyH6OnK3pjqIqZw-Ln7_
# File: adaface_ir101_webface12m.onnx (250MB)
```

**Option B: From Hugging Face**
```bash
# Visit: https://huggingface.co/BOVIFOCR/AdaFace/tree/main
# Download: adaface_ir101_webface12m.onnx
```

**Option C: From Official Repo**
```bash
# Clone the repo and download from releases
git clone https://github.com/mk-minchul/AdaFace.git
cd AdaFace
# Check releases for the model file
```

### Step 2: Upload to GCS

```bash
# Upload to your GCS bucket
gsutil cp adaface_ir101_webface12m.onnx gs://easypool-ml-models/face-recognition/v1/

# Verify upload
gsutil ls -lh gs://easypool-ml-models/face-recognition/v1/adaface_ir101_webface12m.onnx
```

### Step 3: Verify Configuration

AdaFace is already configured in `ml_models/config.py`:

```python
"adaface": {
    "class": "ml_models.face_recognition.inference.adaface.AdaFace",
    "dimensions": 512,
    "enabled": True,  # ✅ Enabled
    "quality_threshold": 0.65,
    "description": "AdaFace IR-101 - Quality-adaptive for varying conditions"
}
```

### Step 4: Deploy

```bash
# Commit and push
cd backend_easy
git add .
git commit -m "feat: Add AdaFace for quality-adaptive face recognition"
git push origin develop

# Deploy will automatically download AdaFace from GCS
```

### Step 5: Test

After deployment, check the logs:

```bash
gcloud run services logs read easypool-backend-dev --limit=100 | grep -i adaface
```

You should see:
```
✅ Loaded model: adaface
Initialized ConsensusService with 3 models: ['mobilefacenet', 'arcface_int8', 'adaface']
```

---

## Model Details

**Model:** AdaFace IR-101 WebFace12M
**Size:** ~250MB
**Accuracy:** 99.4%+ on LFW
**Dimensions:** 512D
**Special Feature:** Quality-adaptive (automatically adjusts to image quality)

**Best For:**
- Varying lighting conditions (morning, evening, shadows)
- Motion blur from moving subjects
- Partial occlusions (masks, hands)
- Low-quality images
- Real-world "in-the-wild" scenarios

---

## Alternative: Run Without AdaFace

If you can't download AdaFace yet, you can disable it temporarily:

```python
# In ml_models/config.py
"adaface": {
    "enabled": False,  # ❌ Disabled temporarily
    # ... rest of config
}

# Also update model_weights to sum to 1.0
"model_weights": {
    "mobilefacenet": 0.5,  # 50%
    "arcface_int8": 0.5,   # 50%
    "adaface": 0.0         # 0% (disabled)
}

# And update models_for_verification
"models_for_verification": ["mobilefacenet", "arcface_int8"]  # Remove adaface
```

This will run with 2 models instead of 3.

---

## Troubleshooting

### Error: "AdaFace model not found"

**Cause:** Model file not in GCS or not downloaded to Cloud Run

**Fix:**
1. Verify file exists in GCS:
   ```bash
   gsutil ls gs://easypool-ml-models/face-recognition/v1/
   ```

2. Check file size (should be ~250MB):
   ```bash
   gsutil ls -lh gs://easypool-ml-models/face-recognition/v1/adaface_ir101_webface12m.onnx
   ```

3. Check Cloud Run logs for download errors

### AdaFace Scores Always 0.0000

**Cause:** Model failed to load or ONNX runtime issue

**Fix:**
1. Check model format (must be ONNX)
2. Verify input/output shapes match expected (1, 3, 112, 112) → (1, 512)
3. Test model locally first

---

## Download Locations

**Primary:**
- Google Drive: https://drive.google.com/drive/folders/1IaSwSLbWgc_SWyH6OnK3pjqIqZw-Ln7_
- Hugging Face: https://huggingface.co/BOVIFOCR/AdaFace/tree/main

**Official Repo:**
- GitHub: https://github.com/mk-minchul/AdaFace
- Paper: https://arxiv.org/abs/2204.00964

**Verify Hash (Optional):**
```bash
# After download, verify file integrity
md5sum adaface_ir101_webface12m.onnx
# Expected: (check with official repo)
```
