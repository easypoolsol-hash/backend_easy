# Test Face Images

This directory contains test images for face recognition integration tests.

## Directory Structure

```
tests/fixtures/test_images/
├── README.md              # This file
├── face_frontal.jpg       # Auto-generated synthetic face (400x400)
├── face_small.jpg         # Auto-generated synthetic face (150x150)
├── face_large.jpg         # Auto-generated synthetic face (800x800)
└── real_face_*.jpg        # (Optional) Add your own real face photos here
```

## Using Synthetic Images (Default)

The tests automatically generate synthetic face images if they don't exist. These work for basic testing but may not always pass face detection.

## Adding Real Face Photos (Recommended)

For more realistic testing, add real human face photos:

### 1. Frontal Face (Recommended)
- **Filename**: `real_face_frontal.jpg`
- **Requirements**:
  - Clear, well-lit frontal face
  - Single person only
  - Minimum 200x200 pixels
  - JPEG format
- **Example**: Passport-style photo

### 2. Profile Face (Optional)
- **Filename**: `real_face_profile.jpg`
- **Purpose**: Test face detection with non-frontal angles

### 3. Group Photo (Optional)
- **Filename**: `real_face_group.jpg`
- **Purpose**: Test rejection of multiple faces

### 4. No Face (Optional)
- **Filename**: `no_face.jpg`
- **Purpose**: Test handling of images without faces

## Privacy & Security

⚠️ **IMPORTANT**: Do not commit real personal photos to git!

Add to `.gitignore`:
```
# Ignore real face photos
tests/fixtures/test_images/real_face_*.jpg
tests/fixtures/test_images/*.png
!tests/fixtures/test_images/README.md
```

## Using Your Own Photos

```python
# Update tests to use real photos
@pytest.fixture
def real_face_image():
    image_path = TEST_IMAGES_DIR / "real_face_frontal.jpg"
    if not image_path.exists():
        pytest.skip("Real face photo not available")

    with open(image_path, 'rb') as f:
        return SimpleUploadedFile(
            name='real_face.jpg',
            content=f.read(),
            content_type='image/jpeg'
        )
```

## Sample Photos

You can use:
1. **Your own photo** (safest - don't commit)
2. **Stock photos** from free sources (check license)
3. **Generated faces** from thispersondoesnotexist.com (AI-generated, no privacy issues)

## Test Image Requirements

| Property | Value |
|----------|-------|
| Format | JPEG, PNG |
| Min Size | 150x150px |
| Recommended | 400x400px |
| Max Size | 2000x2000px |
| Faces | Single face, frontal |
| Lighting | Well-lit, no shadows |

## Running Tests

```bash
# Run with synthetic images (fast)
pytest tests/integration/test_face_recognition_real.py -v

# Run with your real photos (more realistic)
# 1. Add real_face_frontal.jpg to this directory
# 2. Run tests
pytest tests/integration/test_face_recognition_real.py -v -k real

# Skip slow integration tests
pytest tests/ -m "not slow"
```
