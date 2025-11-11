"""
Extract OpenFace model architecture from deepface and save it
"""

import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from pathlib import Path
import sys

print("=" * 70)
print("EXTRACTING OPENFACE ARCHITECTURE FROM DEEPFACE")
print("=" * 70)

try:
    # Import the OpenFace model building code from deepface
    import inspect

    # Try different import paths
    try:
        from deepface.models.facial_recognition import OpenFace

        print("\nImported from deepface.models.facial_recognition.OpenFace")
        model_module = OpenFace
    except:
        try:
            from deepface.models import OpenFace

            print("\nImported from deepface.models.OpenFace")
            model_module = OpenFace
        except:
            print("\nCannot import OpenFace module directly")
            print("Trying alternative approach...")

            # Try to get the source code location
            import deepface

            deepface_path = Path(deepface.__file__).parent
            print(f"Deepface location: {deepface_path}")

            # List models directory
            models_dir = deepface_path / "models"
            if models_dir.exists():
                print("\nModels directory contents:")
                for item in models_dir.iterdir():
                    print(f"  {item.name}")

                # Look for OpenFace
                for item in models_dir.rglob("*OpenFace*"):
                    print(f"\nFound OpenFace file: {item}")

                    # Read and display the source
                    if item.suffix == ".py":
                        print("\nReading OpenFace source code...")
                        source = item.read_text()

                        # Save to a new file
                        output_path = Path(__file__).parent / "openface_architecture_source.py"
                        output_path.write_text(source)
                        print(f"Saved source to: {output_path}")
            else:
                print(f"Models directory not found at: {models_dir}")

            sys.exit(0)

    # Get the source code of the load_model function
    if hasattr(model_module, "load_model"):
        source_code = inspect.getsource(model_module.load_model)
        print("\nExtracted load_model function source:")
        print("=" * 70)
        print(source_code)

        # Save to file
        output_path = Path(__file__).parent / "openface_load_model_source.py"
        output_path.write_text(source_code)
        print("\n" + "=" * 70)
        print(f"Saved to: {output_path}")
    else:
        print("No load_model function found")

        # Try to get the class source
        if hasattr(model_module, "OpenFaceClient"):
            class_source = inspect.getsource(model_module.OpenFaceClient)
            print("\nExtracted OpenFaceClient class source:")
            print("=" * 70)
            print(class_source[:500])  # First 500 chars

            # Save to file
            output_path = Path(__file__).parent / "openface_class_source.py"
            output_path.write_text(class_source)
            print(f"\nSaved to: {output_path}")

except Exception as e:
    print(f"\nError: {e}")
    import traceback

    traceback.print_exc()

    print("\n" + "=" * 70)
    print("FALLBACK: MANUAL ARCHITECTURE DEFINITION")
    print("=" * 70)
    print("\nSince automatic extraction failed, we need to manually define")
    print("the OpenFace architecture based on the Inception ResNet v1 structure.")
