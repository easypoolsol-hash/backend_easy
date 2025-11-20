#!/bin/bash
# Upload ML Models to Google Cloud Storage
# Run this script to upload models to GCS bucket: gs://easypool-ml-models

set -e

echo "======================================================================="
echo "Uploading ML Models to Google Cloud Storage"
echo "======================================================================="

# Check if models exist
if [ ! -f "mobilefacenet.tflite" ]; then
    echo "[ERROR] mobilefacenet.tflite not found!"
    exit 1
fi

if [ ! -f "arcface_resnet100.onnx" ]; then
    echo "[ERROR] arcface_resnet100.onnx not found!"
    exit 1
fi

if [ ! -f "arcface_w600k_r50.onnx" ]; then
    echo "[ERROR] arcface_w600k_r50.onnx not found!"
    exit 1
fi

echo "[OK] All models found"

# Upload to GCS
echo ""
echo "Uploading models to gs://easypool-ml-models/face-recognition/v1/..."
echo ""

gsutil cp mobilefacenet.tflite gs://easypool-ml-models/face-recognition/v1/mobilefacenet.tflite
echo "[OK] Uploaded: mobilefacenet.tflite (5 MB)"

gsutil cp arcface_resnet100.onnx gs://easypool-ml-models/face-recognition/v1/arcface_resnet100.onnx
echo "[OK] Uploaded: arcface_resnet100.onnx (249 MB)"

gsutil cp arcface_w600k_r50.onnx gs://easypool-ml-models/face-recognition/v1/arcface_w600k_r50.onnx
echo "[OK] Uploaded: arcface_w600k_r50.onnx (167 MB)"

echo ""
echo "======================================================================="
echo "Upload Complete!"
echo "======================================================================="
echo ""
echo "Models available at:"
echo "  - gs://easypool-ml-models/face-recognition/v1/mobilefacenet.tflite"
echo "  - gs://easypool-ml-models/face-recognition/v1/arcface_resnet100.onnx"
echo "  - gs://easypool-ml-models/face-recognition/v1/arcface_w600k_r50.onnx"
echo ""
echo "Total size: 421 MB"
echo "Storage cost: ~$0.01/month"
echo ""
echo "Next steps:"
echo "  1. Cloud Run will download models on startup"
echo "  2. Models cached in container memory (1.5 GB)"
echo "  3. Cold start: ~10 seconds, Warm start: instant"
echo ""
echo "======================================================================="
