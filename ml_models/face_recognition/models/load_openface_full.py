"""
Load OpenFace model from deepface and save as full Keras model
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from pathlib import Path

print("=" * 70)
print("LOADING OPENFACE MODEL FROM DEEPFACE")
print("=" * 70)

# Try to import deepface and load OpenFace
try:
    from deepface.models.FacialRecognition import build_model

    print("\nBuilding OpenFace model...")
    model = build_model("OpenFace")

    print("Model loaded successfully!")
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")

    # Save as full Keras model
    output_path = Path(__file__).parent / "openface_full_model.h5"
    print(f"\nSaving full model to: {output_path}")

    model.save(str(output_path))

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Model saved: {size_mb:.2f} MB")

    print("\n" + "=" * 70)
    print("SUCCESS - READY FOR TFLITE CONVERSION")
    print("=" * 70)

except Exception as e:
    print(f"Error: {e}")
    print("\nTrying alternative approach...")

    # Alternative: manually build OpenFace architecture
    try:
        from tensorflow.keras import layers

        print("Building OpenFace architecture manually...")

        # OpenFace uses Inception ResNet v1 architecture
        # Input: 96x96x3
        inputs = layers.Input(shape=(96, 96, 3))

        # This is a simplified version - we need the actual architecture
        # For now, let's try to use the weights file directly
        print("Error: Need proper OpenFace architecture definition")
        print("\nPlease use the deepface library to build the model")

    except Exception as e2:
        print(f"Alternative approach also failed: {e2}")
