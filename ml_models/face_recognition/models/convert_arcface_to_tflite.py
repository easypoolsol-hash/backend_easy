"""
Convert ArcFace H5 model to TensorFlow Lite

Converts GhostFaceNet_W1.3_S1_ArcFace.h5 to TFLite format for production deployment.
"""

from pathlib import Path

import numpy as np
import tensorflow as tf


def convert_h5_to_tflite(h5_path: str, tflite_path: str, input_shape=(112, 112, 3), optimize=True):
    """
    Convert Keras H5 model to TensorFlow Lite

    Args:
        h5_path: Path to input .h5 model
        tflite_path: Path to output .tflite model
        input_shape: Model input shape (H, W, C)
        optimize: Whether to apply optimization
    """
    print(f"Loading model from {h5_path}...")

    try:
        # Load the Keras model
        model = tf.keras.models.load_model(h5_path, compile=False)
        print("Model loaded successfully!")
        print(f"Model input shape: {model.input_shape}")
        print(f"Model output shape: {model.output_shape}")

        # Convert to TFLite
        converter = tf.lite.TFLiteConverter.from_keras_model(model)

        if optimize:
            # Enable optimization
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            print("Optimization enabled")

        # Convert
        print("Converting to TFLite...")
        tflite_model = converter.convert()

        # Save
        print(f"Saving to {tflite_path}...")
        with open(tflite_path, "wb") as f:
            f.write(tflite_model)

        # Verify
        print("Verifying model...")
        interpreter = tf.lite.Interpreter(model_path=tflite_path)
        interpreter.allocate_tensors()

        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        print("\n=== TFLite Model Info ===")
        print(f"Input shape: {input_details[0]['shape']}")
        print(f"Input dtype: {input_details[0]['dtype']}")
        print(f"Output shape: {output_details[0]['shape']}")
        print(f"Output dtype: {output_details[0]['dtype']}")

        # Test inference
        print("\nTesting inference...")
        test_input = np.random.randn(1, *input_shape).astype(np.float32)
        interpreter.set_tensor(input_details[0]["index"], test_input)
        interpreter.invoke()
        test_output = interpreter.get_tensor(output_details[0]["index"])

        print(f"Test output shape: {test_output.shape}")
        print(f"Test output range: [{test_output.min():.4f}, {test_output.max():.4f}]")

        # File size
        original_size = Path(h5_path).stat().st_size / (1024 * 1024)
        tflite_size = Path(tflite_path).stat().st_size / (1024 * 1024)
        compression = (1 - tflite_size / original_size) * 100

        print("\n=== Conversion Summary ===")
        print(f"Original size: {original_size:.2f} MB")
        print(f"TFLite size: {tflite_size:.2f} MB")
        print(f"Compression: {compression:.1f}%")
        print("✅ Conversion successful!")

    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert ArcFace H5 to TFLite")
    parser.add_argument("--input", default="GhostFaceNet_W1.3_S1_ArcFace.h5", help="Input H5 model path")
    parser.add_argument("--output", default="arcface_ghostfacenet.tflite", help="Output TFLite model path")
    parser.add_argument("--no-optimize", action="store_true", help="Disable optimization")

    args = parser.parse_args()

    convert_h5_to_tflite(h5_path=args.input, tflite_path=args.output, optimize=not args.no_optimize)
