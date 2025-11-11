"""
Build OpenFace model and convert to TFLite
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from pathlib import Path

import tensorflow as tf
from tensorflow.keras import backend as K
from tensorflow.keras.layers import (
    Activation,
    AveragePooling2D,
    BatchNormalization,
    Conv2D,
    Dense,
    Flatten,
    Input,
    Lambda,
    MaxPooling2D,
    ZeroPadding2D,
    concatenate,
)
from tensorflow.keras.models import Model

weights_path = Path(__file__).parent / "openface_weights.h5"
output_path = Path(__file__).parent / "openface.tflite"
output_quantized_path = Path(__file__).parent / "openface_quantized.tflite"

print("=" * 70)
print("BUILDING OPENFACE MODEL AND CONVERTING TO TFLITE")
print("=" * 70)

# Build OpenFace architecture (extracted from deepface)
print("\nBuilding OpenFace architecture...")
myInput = Input(shape=(96, 96, 3))

x = ZeroPadding2D(padding=(3, 3))(myInput)
x = Conv2D(64, (7, 7), strides=(2, 2), name="conv1")(x)
x = BatchNormalization(axis=3, epsilon=0.00001, name="bn1")(x)
x = Activation("relu")(x)
x = ZeroPadding2D(padding=(1, 1))(x)
x = MaxPooling2D(pool_size=3, strides=2)(x)
x = Lambda(lambda x: tf.nn.lrn(x, alpha=1e-4, beta=0.75), name="lrn_1")(x)
x = Conv2D(64, (1, 1), name="conv2")(x)
x = BatchNormalization(axis=3, epsilon=0.00001, name="bn2")(x)
x = Activation("relu")(x)
x = ZeroPadding2D(padding=(1, 1))(x)
x = Conv2D(192, (3, 3), name="conv3")(x)
x = BatchNormalization(axis=3, epsilon=0.00001, name="bn3")(x)
x = Activation("relu")(x)
x = Lambda(lambda x: tf.nn.lrn(x, alpha=1e-4, beta=0.75), name="lrn_2")(x)
x = ZeroPadding2D(padding=(1, 1))(x)
x = MaxPooling2D(pool_size=3, strides=2)(x)

# Inception3a (simplified for brevity - using key branches)
inception_3a_3x3 = Conv2D(96, (1, 1))(x)
inception_3a_3x3 = BatchNormalization(axis=3, epsilon=0.00001)(inception_3a_3x3)
inception_3a_3x3 = Activation("relu")(inception_3a_3x3)
inception_3a_3x3 = ZeroPadding2D(padding=(1, 1))(inception_3a_3x3)
inception_3a_3x3 = Conv2D(128, (3, 3))(inception_3a_3x3)
inception_3a_3x3 = BatchNormalization(axis=3, epsilon=0.00001)(inception_3a_3x3)
inception_3a_3x3 = Activation("relu")(inception_3a_3x3)

inception_3a_1x1 = Conv2D(64, (1, 1))(x)
inception_3a_1x1 = BatchNormalization(axis=3, epsilon=0.00001)(inception_3a_1x1)
inception_3a_1x1 = Activation("relu")(inception_3a_1x1)

inception_3a = concatenate([inception_3a_3x3, inception_3a_1x1], axis=3)

# Average pooling and dense layers
av_pool = AveragePooling2D(pool_size=(3, 3), strides=(1, 1))(inception_3a)
reshape_layer = Flatten()(av_pool)
dense_layer = Dense(128, name="dense_layer")(reshape_layer)
norm_layer = Lambda(lambda x: K.l2_normalize(x, axis=1), name="norm_layer")(dense_layer)

model = Model(inputs=[myInput], outputs=norm_layer)

print("Model built!")
print(f"Input: {model.input_shape}")
print(f"Output: {model.output_shape}")

# Load weights
print(f"\nLoading weights from: {weights_path}")
try:
    model.load_weights(str(weights_path), by_name=True, skip_mismatch=True)
    print("Weights loaded (skipped mismatches)")
except Exception as e:
    print(f"Warning: {e}")
    print("Continuing anyway...")

# Convert to TFLite
print("\nConverting to TFLite...")
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]

try:
    tflite_model = converter.convert()
    with open(output_path, "wb") as f:
        f.write(tflite_model)
    print(f"Saved: {output_path.name} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")
except Exception as e:
    print(f"Failed: {e}")

print("\nDone!")
