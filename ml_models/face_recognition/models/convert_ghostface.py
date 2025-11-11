"""
Convert GhostFaceNet .h5 model to TFLite format
Simple approach without tf_keras
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # Suppress TF warnings

from pathlib import Path

import tensorflow as tf

# Paths
h5_path = Path(__file__).parent / "GhostFaceNet_W1.3_S1_ArcFace.h5"
tflite_path = Path(__file__).parent / "ghostfacenet.tflite"
tflite_quantized_path = Path(__file__).parent / "ghostfacenet_quantized.tflite"

print(f"Loading model from: {h5_path}")

# Load your .h5 model
try:
    model = tf.keras.models.load_model(str(h5_path))
    print("[OK] Model loaded successfully!")
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")
except Exception as e:
    print(f"[ERROR] Failed to load model: {e}")
    print("\nTrying without compilation...")
    model = tf.keras.models.load_model(str(h5_path), compile=False)
    print("[OK] Model loaded successfully (without compilation)!")
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")

# Convert to TFLite (unquantized)
print("\n--- Converting to TFLite (full precision) ---")
converter = tf.lite.TFLiteConverter.from_keras_model(model)

# Allow experimental ops and select TF ops
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,  # enable TensorFlow Lite ops
    tf.lite.OpsSet.SELECT_TF_OPS,  # enable TensorFlow ops (needed for custom layers)
]
converter._experimental_lower_tensor_list_ops = False

# Convert (full precision)
tflite_model = converter.convert()

# Save full precision model
print(f"Saving TFLite model to: {tflite_path}")
with open(tflite_path, "wb") as f:
    f.write(tflite_model)

print(f"[OK] Full precision model: {tflite_path.stat().st_size / 1024 / 1024:.2f} MB")

# Convert to TFLite (quantized)
print("\n--- Converting to TFLite (int8 quantized) ---")
converter = tf.lite.TFLiteConverter.from_keras_model(model)

# THIS IS THE MAGIC - Tell the converter to use 8-bit quantization
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# Allow experimental ops and select TF ops
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,  # enable TensorFlow Lite ops
    tf.lite.OpsSet.SELECT_TF_OPS,  # enable TensorFlow ops (needed for custom layers)
]
converter._experimental_lower_tensor_list_ops = False

# Convert (quantized)
tflite_quantized_model = converter.convert()

# Save quantized model
print(f"Saving quantized TFLite model to: {tflite_quantized_path}")
with open(tflite_quantized_path, "wb") as f:
    f.write(tflite_quantized_model)

print(f"[OK] Quantized model: {tflite_quantized_path.stat().st_size / 1024 / 1024:.2f} MB")

print("\n[SUCCESS] Conversion complete!")
print(f"Original .h5 size: {h5_path.stat().st_size / 1024 / 1024:.2f} MB")
print(f"Full precision TFLite: {tflite_path.stat().st_size / 1024 / 1024:.2f} MB")
print(f"Quantized TFLite: {tflite_quantized_path.stat().st_size / 1024 / 1024:.2f} MB")
print("\n[TIP] Use 'ghostfacenet_quantized.tflite' for mobile (smaller, faster)")
