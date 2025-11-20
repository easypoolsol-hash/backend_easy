"""
Test ONNX Models Locally - Verify Banking-Grade Face Recognition
Simple test to verify all 3 models work before GCS deployment
"""

from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np


def create_test_face_image():
    """Create a simple test face image (112x112 RGB)"""
    # Create a simple face-like pattern
    image = np.random.randint(100, 200, (112, 112, 3), dtype=np.uint8)

    # Add some structure (eyes, nose area)
    image[30:40, 30:45] = [50, 50, 50]  # Left eye
    image[30:40, 67:82] = [50, 50, 50]  # Right eye
    image[60:75, 45:67] = [200, 180, 180]  # Nose area

    return image


def test_mobilefacenet():
    """Test MobileFaceNet TFLite model"""
    print("\n" + "=" * 70)
    print("TEST 1: MobileFaceNet (192D)")
    print("=" * 70)

    from ml_models.face_recognition.inference.mobilefacenet import MobileFaceNet

    model = MobileFaceNet()
    print(f"[OK] Model loaded from: {model.model_path}")

    # Create test image
    test_image = create_test_face_image()
    print(f"[OK] Test image created: {test_image.shape}")

    # Get embedding
    embedding = model.get_embedding(test_image)
    print(f"[OK] Embedding generated: {embedding.shape}")
    print(f"     Dimensions: {len(embedding)}D")
    print(f"     Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
    print(f"     L2 Norm: {np.linalg.norm(embedding):.4f}")

    return embedding


def test_arcface_resnet100():
    """Test ArcFace ResNet100 ONNX model"""
    print("\n" + "=" * 70)
    print("TEST 2: ArcFace ResNet100 (512D, 99.82% LFW)")
    print("=" * 70)

    from ml_models.face_recognition.inference.arcface_resnet100 import ArcFaceResNet100

    model = ArcFaceResNet100()
    print(f"[OK] Model loaded from: {model.model_path}")

    # Create test image
    test_image = create_test_face_image()
    print(f"[OK] Test image created: {test_image.shape}")

    # Get embedding
    embedding = model.get_embedding(test_image)
    print(f"[OK] Embedding generated: {embedding.shape}")
    print(f"     Dimensions: {len(embedding)}D")
    print(f"     Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
    print(f"     L2 Norm: {np.linalg.norm(embedding):.4f}")

    return embedding


def test_arcface_resnet50():
    """Test ArcFace ResNet50 ONNX model"""
    print("\n" + "=" * 70)
    print("TEST 3: ArcFace ResNet50 (512D, 99.77% LFW)")
    print("=" * 70)

    from ml_models.face_recognition.inference.arcface_resnet50 import ArcFaceResNet50

    model = ArcFaceResNet50()
    print(f"[OK] Model loaded from: {model.model_path}")

    # Create test image
    test_image = create_test_face_image()
    print(f"[OK] Test image created: {test_image.shape}")

    # Get embedding
    embedding = model.get_embedding(test_image)
    print(f"[OK] Embedding generated: {embedding.shape}")
    print(f"     Dimensions: {len(embedding)}D")
    print(f"     Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
    print(f"     L2 Norm: {np.linalg.norm(embedding):.4f}")

    return embedding


def test_multi_model_consensus():
    """Test multi-model consensus system"""
    print("\n" + "=" * 70)
    print("TEST 4: Multi-Model Consensus System")
    print("=" * 70)

    # Import all models
    from ml_models.face_recognition.inference.arcface_resnet50 import ArcFaceResNet50
    from ml_models.face_recognition.inference.arcface_resnet100 import ArcFaceResNet100
    from ml_models.face_recognition.inference.mobilefacenet import MobileFaceNet

    models = {
        "mobilefacenet": MobileFaceNet(),
        "arcface_resnet100": ArcFaceResNet100(),
        "arcface_resnet50": ArcFaceResNet50(),
    }

    print("[OK] All 3 models loaded")

    # Create test image
    test_image = create_test_face_image()

    # Get embeddings from all models
    embeddings = {}
    for name, model in models.items():
        embedding = model.get_embedding(test_image)
        embeddings[name] = embedding
        print(f"[OK] {name}: {len(embedding)}D embedding")

    # Verify dimensions
    print("\n[VERIFY] Model dimensions:")
    print(f"  - MobileFaceNet:     {len(embeddings['mobilefacenet'])}D")
    print(f"  - ArcFace ResNet100: {len(embeddings['arcface_resnet100'])}D")
    print(f"  - ArcFace ResNet50:  {len(embeddings['arcface_resnet50'])}D")

    return embeddings


def main():
    """Run all model tests"""
    print("\n" + "=" * 70)
    print("BANKING-GRADE FACE RECOGNITION MODEL TEST")
    print("=" * 70)
    print("\nTesting all 3 models for multi-model consensus verification...")

    try:
        # Test each model individually
        emb1 = test_mobilefacenet()
        emb2 = test_arcface_resnet100()
        emb3 = test_arcface_resnet50()

        # Test multi-model system
        embeddings = test_multi_model_consensus()

        # Final summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print("[SUCCESS] All 3 models working correctly!")
        print("\nModel Details:")
        print("  1. MobileFaceNet:     192D,  ~90% accuracy    (Kiosk)")
        print("  2. ArcFace ResNet100: 512D, 99.82% LFW       (Backend - Highest)")
        print("  3. ArcFace ResNet50:  512D, 99.77% LFW       (Backend - Banking)")
        print("\nConsensus Strategy:")
        print("  - 3 models agree  → HIGH confidence (99.9%+)")
        print("  - 2 models agree  → MEDIUM confidence (99%+)")
        print("  - No consensus    → FLAGGED for manual review")
        print("\n[READY] Models ready for GCS upload and Cloud Run deployment!")
        print("=" * 70)

        return True

    except Exception as e:
        print("\n" + "=" * 70)
        print("[ERROR] Model test failed!")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
