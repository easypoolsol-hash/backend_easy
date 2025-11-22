# AdaFace Integration Guide

## Status: Pending ONNX Conversion

AdaFace is a quality-adaptive face recognition model that excels in poor lighting and challenging conditions. It's critical for achieving banking-grade accuracy (99.8%+).

## Available Models

### Hugging Face (PyTorch)
- **Model**: `minchul/cvlface_adaface_ir50_ms1mv2`
- **URL**: https://huggingface.co/minchul/cvlface_adaface_ir50_ms1mv2
- **Architecture**: IResNet-50
- **Dataset**: MS1MV2 (5.8M images)
- **Embedding**: 512 dimensions
- **Accuracy**: 99.4%+ LFW
- **License**: MIT (requires citation)

### Alternative: IR101 WebFace4M
- **Model**: `minchul/cvlface_adaface_ir101_webface4m`
- **Architecture**: IResNet-101
- **Dataset**: WebFace4M (4M images)
- **Accuracy**: Higher than IR50
- **Note**: WebFace models cannot be used for commercial purposes

## Conversion to ONNX (Required)

### Option 1: PyTorch to ONNX Export

```python
import torch
from huggingface_hub import hf_hub_download

# Download PyTorch model
model_path = hf_hub_download(
    repo_id="minchul/cvlface_adaface_ir50_ms1mv2",
    filename="model.safetensors"
)

# Load model
from safetensors import safe_open
tensors = {}
with safe_open(model_path, framework="pt", device="cpu") as f:
    for key in f.keys():
        tensors[key] = f.get_tensor(key)

# TODO: Initialize AdaFace model architecture
# model = AdaFaceIResNet50()
# model.load_state_dict(tensors)

# Export to ONNX
dummy_input = torch.randn(1, 3, 112, 112)
torch.onnx.export(
    model,
    dummy_input,
    "adaface_ir50_ms1mv2.onnx",
    export_params=True,
    opset_version=11,
    do_constant_folding=True,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
)
```

### Option 2: Use Keras_insightface

The repository `leondgarse/Keras_insightface` has ported AdaFace models and supports TFLite conversion:

```bash
git clone https://github.com/leondgarse/Keras_insightface.git
cd Keras_insightface

# Convert to TFLite
python convert_to_tflite.py --model adaface_r100_4m
```

### Option 3: Use Pre-converted ONNX (If Available)

Check these repositories for pre-converted models:
- https://github.com/Shohruh72/FaceID
- https://github.com/songhieng/face-recognition-models

## Integration Steps (After Conversion)

### 1. Upload to GCS

```bash
gsutil cp adaface_ir50_ms1mv2.onnx gs://easypool-ml-models/face_recognition/models/
```

### 2. Create Model Wrapper

File: `backend_easy/ml_models/adaface_model.py`

```python
class AdaFaceModel:
    def __init__(self):
        self.model_path = "ml_models/face_recognition/models/adaface_ir50_ms1mv2.onnx"
        # Load ONNX model using onnxruntime
        import onnxruntime as ort
        self.session = ort.InferenceSession(self.model_path)

    def generate_embedding(self, face_image):
        # Preprocess, run inference, return 512D embedding
        pass
```

### 3. Update Config

File: `backend_easy/ml_models/config.py`

```python
FACE_RECOGNITION_MODELS = {
    # ... existing models
    "adaface": {
        "enabled": True,  # CHANGE FROM False
        "class": "ml_models.adaface_model.AdaFaceModel",
        "quality_threshold": 0.40,
    },
}
```

### 4. Update Database Config

Create new ML config version with 3-model weights:
- MobileFaceNet: 30%
- ArcFace INT8: 40%
- AdaFace: 30%

## Expected Performance

With AdaFace enabled (3-model ensemble):
- **Accuracy**: 99.5% → 99.8%+
- **FAR**: < 0.1% (banking-grade)
- **FRR**: < 1%
- **Edge Cases**: Better handling of poor lighting, angles, occlusions

## Citation

```
@inproceedings{kim2022adaface,
  title={AdaFace: Quality Adaptive Margin for Face Recognition},
  author={Kim, Minchul and Jain, Anil K and Liu, Xiaoming},
  booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
  year={2022}
}
```
