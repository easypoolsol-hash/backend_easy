# Multi-Model Backend Face Verification Implementation

## Overview
Implement banking-grade face verification using 3-model consensus on backend to verify kiosk boarding events asynchronously.

## Architecture

```
Kiosk (Real-time)
└─> MobileFaceNet (192D) → Boarding Event Created
    └─> Backend (Async via Cloud Tasks)
        ├─> ArcFace (512D) - 99.82% LFW accuracy
        ├─> AdaFace (512D) - Low-quality robust
        └─> MobileFaceNet (192D) - Verification
            └─> Consensus Voting
                ├─> All 3 agree → VERIFIED (high confidence)
                ├─> 2 agree → VERIFIED (medium confidence)
                └─> No consensus → FLAGGED (manual review)
```

## Models Selected (Based on 2025 Research)

### 1. ArcFace (GhostFaceNet backbone)
- **Accuracy**: 99.82% on LFW dataset
- **Embedding**: 512D
- **Best for**: High-accuracy recognition in controlled environments
- **File**: `GhostFaceNet_W1.3_S1_ArcFace.h5` (needs TFLite conversion)
- **Source**: InsightFace project
- **Status**: ✅ File available, needs conversion

### 2. AdaFace (Quality-Adaptive)
- **Accuracy**: Outperforms ArcFace on low-quality images
- **Embedding**: 512D
- **Best for**: Variable lighting, blur, distance (kiosk scenarios)
- **Advantage**: Reduces false positives vs ArcFace
- **Source**: https://github.com/mk-minchul/AdaFace
- **Status**: ⏳ Need to download/convert

### 3. MobileFaceNet (Current)
- **Accuracy**: ~85-90% (lightweight)
- **Embedding**: 192D
- **Best for**: Fast inference, verification layer
- **File**: `mobilefacenet.tflite`
- **Status**: ✅ Already implemented

## Implementation Steps

### Step 1: Model Preparation ✅ IN PROGRESS

#### ArcFace Conversion
```bash
cd backend_easy/ml_models/face_recognition/models

# Convert H5 to TFLite
python convert_arcface_to_tflite.py \
    --input GhostFaceNet_W1.3_S1_ArcFace.h5 \
    --output arcface_ghostfacenet.tflite \
    --optimize
```

#### AdaFace Download
```bash
# Option 1: Download from GitHub
wget https://github.com/mk-minchul/AdaFace/releases/download/v1.0/adaface_ir50_ms1mv2.ckpt

# Option 2: Use pre-converted TFLite (if available)
wget <url>/adaface_ir50.tflite
```

### Step 2: Create Inference Classes

#### File: `ml_models/face_recognition/inference/arcface.py`
```python
from .base import BaseFaceRecognitionModel
import ai_edge_litert.interpreter as tflite
import numpy as np

class ArcFace(BaseFaceRecognitionModel):
    """ArcFace with GhostFaceNet backbone - Banking grade accuracy"""

    def __init__(self, model_path):
        self.interpreter = tflite.Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

    def preprocess(self, image):
        # ArcFace preprocessing
        # Input: 112x112 RGB
        # Normalize: (pixel - 127.5) / 128.0
        image = cv2.resize(image, (112, 112))
        image = (image - 127.5) / 128.0
        return image.astype(np.float32)

    def predict(self, image):
        preprocessed = self.preprocess(image)
        self.interpreter.set_tensor(self.input_details[0]['index'], [preprocessed])
        self.interpreter.invoke()
        embedding = self.interpreter.get_tensor(self.output_details[0]['index'])[0]

        # L2 normalization
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
```

#### File: `ml_models/face_recognition/inference/adaface.py`
```python
from .base import BaseFaceRecognitionModel
import ai_edge_litert.interpreter as tflite
import numpy as np

class AdaFace(BaseFaceRecognitionModel):
    """AdaFace - Quality-adaptive, robust to low-quality images"""

    def __init__(self, model_path):
        self.interpreter = tflite.Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

    def preprocess(self, image):
        # AdaFace preprocessing (similar to ArcFace)
        image = cv2.resize(image, (112, 112))
        image = (image - 127.5) / 128.0
        return image.astype(np.float32)

    def predict(self, image):
        preprocessed = self.preprocess(image)
        self.interpreter.set_tensor(self.input_details[0]['index'], [preprocessed])
        self.interpreter.invoke()
        embedding = self.interpreter.get_tensor(self.output_details[0]['index'])[0]

        # L2 normalization
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
```

### Step 3: Update Configuration

#### File: `ml_models/config.py`
```python
# ArcFace Configuration
ARCFACE_CONFIG = {
    "model_path": FACE_MODELS_DIR / "arcface_ghostfacenet.tflite",
    "input_shape": (112, 112, 3),
    "output_dims": 512,
    "input_range": (-1.0, 1.0),
    "mean": [127.5, 127.5, 127.5],
    "std": [128.0, 128.0, 128.0],
}

# AdaFace Configuration
ADAFACE_CONFIG = {
    "model_path": FACE_MODELS_DIR / "adaface_ir50.tflite",
    "input_shape": (112, 112, 3),
    "output_dims": 512,
    "input_range": (-1.0, 1.0),
    "mean": [127.5, 127.5, 127.5],
    "std": [128.0, 128.0, 128.0],
}

# Model Registry
FACE_RECOGNITION_MODELS = {
    "mobilefacenet": {
        "class": "ml_models.face_recognition.inference.mobilefacenet.MobileFaceNet",
        "dimensions": 192,
        "enabled": True,
        "quality_threshold": 0.68,
        "description": "MobileFaceNet - Fast verification",
    },
    "arcface": {
        "class": "ml_models.face_recognition.inference.arcface.ArcFace",
        "dimensions": 512,
        "enabled": True,
        "quality_threshold": 0.75,
        "description": "ArcFace GhostFaceNet - Banking grade (99.82% LFW)",
    },
    "adaface": {
        "class": "ml_models.face_recognition.inference.adaface.AdaFace",
        "dimensions": 512,
        "enabled": True,
        "quality_threshold": 0.72,
        "description": "AdaFace - Quality adaptive, robust to low-quality",
    },
}
```

### Step 4: Implement Multi-Model Consensus Service

#### File: `app/face_verification/__init__.py`
```python
default_app_config = 'app.face_verification.apps.FaceVerificationConfig'
```

#### File: `app/face_verification/apps.py`
```python
from django.apps import AppConfig

class FaceVerificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.face_verification'
    verbose_name = 'Face Verification'
```

#### File: `app/face_verification/services/consensus_service.py`
```python
"""
Multi-Model Consensus Service
Implements banking-grade verification using 3-model voting.
"""

from typing import Dict, List, Tuple
import numpy as np
from ml_models.config import FACE_RECOGNITION_MODELS

class ConsensusService:
    """Handles multi-model consensus voting for face verification"""

    CONFIDENCE_LEVELS = {
        3: "high",     # All 3 models agree
        2: "medium",   # 2 models agree
        1: "low",      # No consensus
        0: "failed",   # No matches
    }

    def __init__(self):
        self.models = self._load_models()
        self.thresholds = {
            name: config["quality_threshold"]
            for name, config in FACE_RECOGNITION_MODELS.items()
            if config["enabled"]
        }

    def _load_models(self):
        """Lazy load all enabled models"""
        from app.students.services.face_recognition_service import FaceRecognitionService
        service = FaceRecognitionService()
        return service.get_models()

    def verify_face(
        self,
        face_image: np.ndarray,
        student_embeddings: Dict[str, List[np.ndarray]]
    ) -> Dict:
        """
        Run multi-model verification with consensus voting.

        Args:
            face_image: Face image (preprocessed)
            student_embeddings: Dict of {model_name: [embeddings]} for all students

        Returns:
            {
                'student_id': int,
                'confidence_level': 'high' | 'medium' | 'low' | 'failed',
                'consensus_count': int (how many models agreed),
                'model_results': {
                    'arcface': {'student_id': 123, 'score': 0.82},
                    'adaface': {'student_id': 123, 'score': 0.79},
                    'mobilefacenet': {'student_id': 123, 'score': 0.71}
                }
            }
        """
        model_results = {}

        # Run all models
        for model_name, model in self.models.items():
            embedding = model.predict(face_image)
            threshold = self.thresholds[model_name]

            # Find best match
            best_student = None
            best_score = 0.0

            for student_id, embeddings_list in student_embeddings[model_name].items():
                for stored_embedding in embeddings_list:
                    similarity = self._cosine_similarity(embedding, stored_embedding)
                    if similarity > best_score and similarity >= threshold:
                        best_score = similarity
                        best_student = student_id

            model_results[model_name] = {
                'student_id': best_student,
                'score': float(best_score)
            }

        # Consensus voting
        votes = {}
        for model_name, result in model_results.items():
            student_id = result['student_id']
            if student_id is not None:
                votes[student_id] = votes.get(student_id, 0) + 1

        # Determine consensus
        if not votes:
            return {
                'student_id': None,
                'confidence_level': 'failed',
                'consensus_count': 0,
                'model_results': model_results
            }

        # Get student with most votes
        winning_student = max(votes.items(), key=lambda x: x[1])
        student_id, consensus_count = winning_student

        return {
            'student_id': student_id,
            'confidence_level': self.CONFIDENCE_LEVELS[consensus_count],
            'consensus_count': consensus_count,
            'model_results': model_results
        }

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### Step 5: Database Schema Updates

#### File: `app/boarding_events/migrations/0XXX_add_backend_verification.py`
```python
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('boarding_events', '0XXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='boardingevent',
            name='backend_verification_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Pending Verification'),
                    ('verified', 'Verified'),
                    ('flagged', 'Flagged for Review'),
                    ('failed', 'Verification Failed'),
                ],
                default='pending',
            ),
        ),
        migrations.AddField(
            model_name='boardingevent',
            name='backend_verification_confidence',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('high', 'High Confidence'),
                    ('medium', 'Medium Confidence'),
                    ('low', 'Low Confidence'),
                ],
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name='boardingevent',
            name='backend_student_id',
            field=models.ForeignKey(
                to='students.Student',
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='backend_verified_events',
                help_text='Student identified by backend models',
            ),
        ),
        migrations.AddField(
            model_name='boardingevent',
            name='model_consensus_data',
            field=models.JSONField(
                default=dict,
                help_text='Detailed results from all models',
            ),
        ),
    ]
```

### Step 6: Cloud Tasks Integration

#### File: `app/face_verification/tasks.py`
```python
"""
Cloud Tasks handlers for async face verification
"""

from google.cloud import tasks_v2
from django.conf import settings
import json

def create_verification_task(boarding_event_id: int, image_url: str):
    """
    Create Cloud Task for async face verification

    Args:
        boarding_event_id: ID of boarding event to verify
        image_url: URL of face image in Cloud Storage
    """
    client = tasks_v2.CloudTasksClient()

    project = settings.GCP_PROJECT
    location = settings.GCP_LOCATION
    queue = 'face-verification-queue'

    parent = client.queue_path(project, location, queue)

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f'{settings.BACKEND_URL}/api/v1/face-verification/verify/',
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({
                'boarding_event_id': boarding_event_id,
                'image_url': image_url,
            }).encode(),
        }
    }

    response = client.create_task(request={'parent': parent, 'task': task})
    return response.name
```

## Testing Plan

### Unit Tests
```python
def test_arcface_inference():
    """Test ArcFace model loads and predicts"""
    pass

def test_adaface_inference():
    """Test AdaFace model loads and predicts"""
    pass

def test_consensus_all_agree():
    """Test when all 3 models agree - should be high confidence"""
    pass

def test_consensus_two_agree():
    """Test when 2 models agree - should be medium confidence"""
    pass

def test_consensus_no_agreement():
    """Test when no models agree - should be flagged"""
    pass
```

### Integration Tests
- Test full verification flow from kiosk → backend → database
- Test Cloud Tasks queue processing
- Test admin dashboard flagged events view

## Deployment Checklist

- [ ] ArcFace model converted to TFLite
- [ ] AdaFace model downloaded and converted
- [ ] Inference classes implemented and tested
- [ ] Config updated with new models
- [ ] Consensus service implemented
- [ ] Database migrations created and applied
- [ ] Cloud Tasks queue created in GCP
- [ ] Admin dashboard updated
- [ ] Integration tests passing
- [ ] Deployed to staging
- [ ] Smoke tested with real data
- [ ] Deployed to production

## Expected Results

**Current System (Kiosk Only)**:
- MobileFaceNet: ~85-90% accuracy
- No backend verification
- False positives not caught

**New System (Multi-Model Consensus)**:
- ArcFace: 99.82% accuracy
- AdaFace: Better on low-quality
- MobileFaceNet: Verification layer
- **Combined: 99%+ accuracy with consensus**
- False positives flagged for manual review

## Cost Impact

- Cloud Tasks: Free (under 1M/month)
- Increased Celery resources: +$10/month
- Storage for verification data: +$2/month
- **Total: ~$12-15/month increase**

## Timeline

- Model preparation: 1 day
- Implementation: 2 days
- Testing: 1 day
- **Total: 3-4 days**
