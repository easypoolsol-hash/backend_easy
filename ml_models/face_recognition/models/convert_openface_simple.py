"""
Simple OpenFace conversion using deepface
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from pathlib import Path

import numpy as np
import tensorflow as tf

print("=" * 70)
print("OPENFACE TFLITE CONVERSION")
print("=" * 70)

# Load model using deepface
print("\nLoading OpenFace model from deepface...")
try:
    from deepface.models.facial_recognition import OpenFace

    model = OpenFace.load_model()
    print("Model loaded!")
    print(f"Input: {model.input_shape}")
    print(f"Output: {model.output_shape}")
except Exception as e:
    print(f"Error: {e}")
    exit(1)

# Convert to TFLite
output_path = Path(__file__).parent / "openface.tflite"

print("\nConverting to TFLite (TFLITE_BUILTINS only)...")
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
converter.optimizations = [tf.lite.Optimize.DEFAULT]


# Representative dataset
def representative_dataset():
    for _ in range(100):
        img = np.random.rand(1, 96, 96, 3).astype(np.float32) / 255.0
        yield [img]


converter.representative_dataset = representative_dataset

try:
    tflite_model = converter.convert()
    with open(output_path, "wb") as f:
        f.write(tflite_model)
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\nSUCCESS! Saved: {output_path.name} ({size_mb:.2f} MB)")
except Exception as e:
    print(f"\nFAILED: {e}")
    print("\nOpenFace uses tf.nn.lrn which may not be in TFLite builtins")
    print("This model likely requires SELECT_TF_OPS like GhostFaceNet")
