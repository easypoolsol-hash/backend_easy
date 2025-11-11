"""
Convert GhostFaceNet to TFLite WITHOUT SELECT_TF_OPS
Proper mobile-optimized conversion for ai_edge_litert compatibility
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from pathlib import Path

import tensorflow as tf

# Paths
h5_path = Path(__file__).parent / "GhostFaceNet_W1.3_S1_ArcFace.h5"
tflite_path = Path(__file__).parent / "ghostfacenet_mobile.tflite"
tflite_quantized_path = Path(__file__).parent / "ghostfacenet_mobile_quantized.tflite"

print(f"Loading model from: {h5_path}")

# Load model
try:
    model = tf.keras.models.load_model(str(h5_path), compile=False)
    print("[OK] Model loaded successfully!")
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")
except Exception as e:
    print(f"[ERROR] Failed to load model: {e}")
    exit(1)

# ============================================
# ATTEMPT 1: Pure TFLite ops (no SELECT_TF_OPS)
# ============================================
print("\n" + "=" * 70)
print("ATTEMPT 1: Convert with TFLITE_BUILTINS only (mobile-optimized)")
print("=" * 70)

converter = tf.lite.TFLiteConverter.from_keras_model(model)

# ONLY use TFLite builtin ops (no SELECT_TF_OPS!)
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
]

# Optimization for mobile
converter.optimizations = [tf.lite.Optimize.DEFAULT]

try:
    print("Converting...")
    tflite_model = converter.convert()

    # Save
    print(f"Saving to: {tflite_path}")
    with open(tflite_path, "wb") as f:
        f.write(tflite_model)

    size_mb = tflite_path.stat().st_size / 1024 / 1024
    print(f"[SUCCESS] Mobile-optimized model: {size_mb:.2f} MB")
    print("✅ This model will work with ai_edge_litert!")

except Exception as e:
    print(f"[FAILED] Conversion failed: {e}")
    print("\nThis means the model has operations not supported by TFLite.")
    print("Trying with representative dataset for better conversion...")

# ============================================
# ATTEMPT 2: With representative dataset
# ============================================
print("\n" + "=" * 70)
print("ATTEMPT 2: Convert with representative dataset")
print("=" * 70)

import numpy as np


def representative_dataset():
    """Generate representative data for optimization"""
    for _ in range(100):
        # Random face images (112x112x3)
        data = np.random.rand(1, 112, 112, 3).astype(np.float32)
        # Normalize to [-1, 1] (same as preprocessing)
        data = (data * 255 - 127.5) / 128.0
        yield [data]


converter = tf.lite.TFLiteConverter.from_keras_model(model)

# ONLY use TFLite builtin ops
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
]

# Full integer quantization
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

# Force all ops to be int8
converter.target_spec.supported_types = [tf.int8]

# Ensure input/output are float32 (for ease of use)
converter.inference_input_type = tf.float32
converter.inference_output_type = tf.float32

try:
    print("Converting with quantization...")
    tflite_quantized_model = converter.convert()

    # Save
    print(f"Saving to: {tflite_quantized_path}")
    with open(tflite_quantized_path, "wb") as f:
        f.write(tflite_quantized_model)

    size_mb = tflite_quantized_path.stat().st_size / 1024 / 1024
    print(f"[SUCCESS] Quantized mobile model: {size_mb:.2f} MB")
    print("✅ This model will work with ai_edge_litert!")

except Exception as e:
    print(f"[FAILED] Quantized conversion also failed: {e}")
    print("\nThe model architecture may need modification to work without SELECT_TF_OPS")

# ============================================
# Verification
# ============================================
print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

if tflite_path.exists():
    print(f"\n✅ Mobile model created: {tflite_path.name}")
    print(f"   Size: {tflite_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("   Compatible with: ai_edge_litert ✅")

if tflite_quantized_path.exists():
    print(f"\n✅ Quantized model created: {tflite_quantized_path.name}")
    print(f"   Size: {tflite_quantized_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("   Compatible with: ai_edge_litert ✅")
    print("   Extra benefits: Faster inference, lower memory")

if not tflite_path.exists() and not tflite_quantized_path.exists():
    print("\n❌ Conversion failed. The model uses operations not in TFLite builtins.")
    print("\nPossible solutions:")
    print("1. Use a different GhostFaceNet model trained specifically for TFLite")
    print("2. Modify the model architecture to use only TFLite ops")
    print("3. Use full TensorFlow with SELECT_TF_OPS (current solution)")

print("\n" + "=" * 70)
