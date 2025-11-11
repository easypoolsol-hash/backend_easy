# Face Recognition Models

This directory contains the production face recognition models used in the system.

## Production Models (Tracked in Git)

### Face Embedding Model
- **mobilefacenet.tflite**: Lightweight face embedding model for mobile/edge deployment
  - Input: 112x112 RGB face image
  - Output: 192-dimensional face embedding vector
  - Used for face verification and identification

### Face Detection Models (OpenCV DNN)
- **deploy.prototxt**: OpenCV DNN model architecture for face detection
- **res10_300x300_ssd_iter_140000.caffemodel**: Pre-trained weights for face detection
  - Input: 300x300 RGB image
  - Output: Bounding boxes and confidence scores for detected faces
  - Based on ResNet-10 SSD architecture

## Ignored Files (Not in Git)

The following model files and scripts exist locally but are NOT tracked in git:

### Non-Production Models (Ignored)
- `GhostFaceNet_W1.3_S1_ArcFace.h5`: Alternative face recognition model (not used in production)
- `openface_weights.h5`: OpenFace model weights (not used in production)

### Conversion Scripts (Ignored)
- `build_and_convert_openface.py`
- `convert_ghostface*.py`
- `convert_openface*.py`
- `extract_openface_architecture.py`
- `load_openface_full.py`
- `verify_openface.py`

### Build Artifacts (Ignored)
- `.convert_venv/`: Virtual environment for model conversion

## Model Download

If the OpenCV detection models are missing, download them from:
https://github.com/opencv/opencv/tree/master/samples/dnn/face_detector

## Git Ignore Rules

The `.gitignore` is configured to:
- ✅ Track only production models (MobileFaceNet + OpenCV detection)
- ❌ Ignore all other models (GhostFace, ArcFace, OpenFace)
- ❌ Ignore conversion scripts and build artifacts
- ❌ Ignore .h5 model files
- ❌ Ignore conversion virtual environments

This keeps the repository size manageable while ensuring production models are available for CI/CD.
