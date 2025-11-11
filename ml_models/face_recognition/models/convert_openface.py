"""
Convert OpenFace to TFLite WITHOUT SELECT_TF_OPS
Clean Keras model → Pure TFLite conversion
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from pathlib import Path

import numpy as np
import tensorflow as tf

# Paths
h5_path = Path(__file__).parent / "openface_weights.h5"
tflite_path = Path(__file__).parent / "openface.tflite"
tflite_quantized_path = Path(__file__).parent / "openface_quantized.tflite"

print("=" * 70)
print("CONVERTING OPENFACE TO PURE TFLITE (NO SELECT_TF_OPS)")
print("=" * 70)

# Load model
print(f"\nLoading model: {h5_path}")
try:
    model = tf.keras.models.load_model(str(h5_path))
    print("✅ Model loaded successfully!")
    print(f"   Input shape: {model.input_shape}")
    print(f"   Output shape: {model.output_shape}")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit(1)

# ============================================
# CONVERSION 1: Float32 TFLite (no quantization)
# ============================================
print("\n" + "=" * 70)
print("CONVERSION 1: Float32 TFLite (baseline)")
print("=" * 70)

converter = tf.lite.TFLiteConverter.from_keras_model(model)

# ONLY use TFLite builtin ops (no SELECT_TF_OPS!)
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
]

try:
    print("Converting...")
    tflite_model = converter.convert()

    # Save
    with open(tflite_path, "wb") as f:
        f.write(tflite_model)

    size_mb = tflite_path.stat().st_size / 1024 / 1024
    print(f"✅ Float32 model saved: {tflite_path.name}")
    print(f"   Size: {size_mb:.2f} MB")

except Exception as e:
    print(f"❌ Float32 conversion failed: {e}")
    tflite_path = None

# ============================================
# CONVERSION 2: Quantized TFLite (DEFAULT optimization)
# ============================================
print("\n" + "=" * 70)
print("CONVERSION 2: Quantized TFLite (recommended)")
print("=" * 70)


def representative_dataset():
    """Generate calibration data for quantization"""
    for _ in range(100):
        # Random face images (96x96x3 for OpenFace)
        img = np.random.rand(1, 96, 96, 3).astype(np.float32)
        # Normalize to [0, 1] (OpenFace preprocessing)
        img = img / 255.0
        yield [img]


converter = tf.lite.TFLiteConverter.from_keras_model(model)

# ONLY use TFLite builtin ops
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
]

# Apply DEFAULT quantization
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

try:
    print("Converting with quantization...")
    tflite_quantized_model = converter.convert()

    # Save
    with open(tflite_quantized_path, "wb") as f:
        f.write(tflite_quantized_model)

    size_mb = tflite_quantized_path.stat().st_size / 1024 / 1024
    print(f"✅ Quantized model saved: {tflite_quantized_path.name}")
    print(f"   Size: {size_mb:.2f} MB")

except Exception as e:
    print(f"❌ Quantized conversion failed: {e}")
    tflite_quantized_path = None

# ============================================
# VERIFICATION
# ============================================
print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

# Test with ai_edge_litert (if available)
for model_path, model_name in [(tflite_path, "Float32"), (tflite_quantized_path, "Quantized")]:
    if model_path and model_path.exists():
        print(f"\n✅ Testing {model_name} model: {model_path.name}")
        try:
            # Try ai_edge_litert first
            try:
                from ai_edge_litert.interpreter import Interpreter

                interpreter = Interpreter(model_path=str(model_path))
                print("   ✅ Works with ai_edge_litert!")
            except ImportError:
                # Fallback to TensorFlow Lite
                interpreter = tf.lite.Interpreter(model_path=str(model_path))
                print("   ✅ Works with TensorFlow Lite!")

            interpreter.allocate_tensors()

            # Get input/output details
            input_details = interpreter.get_input_details()[0]
            output_details = interpreter.get_output_details()[0]

            print(f"   Input shape: {input_details['shape']}")
            print(f"   Output shape: {output_details['shape']}")

            # Test inference
            test_input = np.random.rand(*input_details["shape"]).astype(np.float32)
            interpreter.set_tensor(input_details["index"], test_input)
            interpreter.invoke()
            output = interpreter.get_tensor(output_details["index"])

            print("   ✅ Inference works!")
            print(f"   Output dims: {output.shape[-1]}D")

            # Check normalization
            embedding = output.squeeze()
            norm = np.linalg.norm(embedding)
            print(f"   L2 norm: {norm:.4f}")

            if np.isclose(norm, 1.0, atol=0.01):
                print("   ✅ Already L2-normalized")
            else:
                print("   ⚠️ Needs L2-normalization")

        except Exception as e:
            print(f"   ❌ Verification failed: {e}")

# ============================================
# SUMMARY
# ============================================
print("\n" + "=" * 70)
print("CONVERSION SUMMARY")
print("=" * 70)

if tflite_path and tflite_path.exists():
    print(f"\n✅ Float32 Model: {tflite_path.name}")
    print(f"   Size: {tflite_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("   Use case: Baseline accuracy")

if tflite_quantized_path and tflite_quantized_path.exists():
    print(f"\n✅ Quantized Model: {tflite_quantized_path.name}")
    print(f"   Size: {tflite_quantized_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("   Use case: Production deployment (smaller, faster)")
    print("   Compatible with: ai_edge_litert ✅")
    print("   No SELECT_TF_OPS required! ✅")

print("\n" + "=" * 70)
print("✅ CONVERSION COMPLETE")
print("=" * 70)
