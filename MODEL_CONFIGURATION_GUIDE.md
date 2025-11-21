# Face Recognition Model Configuration Guide

**IMPORTANT: This configuration applies ONLY to NEW INFERENCE**
**Existing student embeddings and historical data are NOT reprocessed.**

---

## Table of Contents

1. [System Overview](#system-overview)
2. [3-Model Ensemble Architecture](#3-model-ensemble-architecture)
3. [Configuration Parameters Explained](#configuration-parameters-explained)
4. [Consensus Strategies](#consensus-strategies)
5. [Temperature Scaling](#temperature-scaling)
6. [Thresholds & Decision Making](#thresholds--decision-making)
7. [When This Configuration is Used](#when-this-configuration-is-used)
8. [Tuning Guide](#tuning-guide)

---

## System Overview

### What is Multi-Model Verification?

Instead of relying on a single face recognition model, we use **3 independent models** that "vote" on the identity:

```
Input Face Image
    ↓
┌───────────────┬──────────────┬────────────┐
│ MobileFaceNet │  ArcFace     │  AdaFace   │
│   (192D)      │  (512D)      │  (512D)    │
│   Fast        │  Accurate    │  Adaptive  │
└───────┬───────┴──────┬───────┴──────┬─────┘
        ↓              ↓              ↓
    Score: 0.75    Score: 0.82    Score: 0.79
    Student: A     Student: A     Student: A
        └──────────────┴──────────────┘
                    ↓
            CONSENSUS VOTING
                    ↓
        ✅ 3/3 models agree → Student A
           HIGH CONFIDENCE (0.82)
```

---

## 3-Model Ensemble Architecture

### Model Roles

| Model | Size | Dimensions | Strength | Use Case |
|-------|------|------------|----------|----------|
| **MobileFaceNet** | 5MB | 192D | Fast, efficient | Normal lighting, good quality |
| **ArcFace W600K** | 174MB | 512D | High accuracy | Banking-grade verification |
| **AdaFace IR-101** | 250MB | 512D | Quality-adaptive | Varying lighting, blur, occlusion |

**Total Size:** 429MB
**Total Storage Impact:** Models stored in Cloud Run container (not per-student)

### Why 3 Models?

1. **Robustness**: Different models have different strengths
2. **Error Reduction**: Outlier predictions are caught
3. **Varying Conditions**: Each model handles different scenarios well
4. **Confidence**: Higher agreement = higher confidence

---

## Configuration Parameters Explained

### Location: `ml_models/config.py`

### 1. FACE_RECOGNITION_MODELS

**What**: Registry of available models
**Purpose**: Define which models exist in the system

```python
FACE_RECOGNITION_MODELS = {
    "mobilefacenet": {
        "class": "ml_models.face_recognition.inference.mobilefacenet.MobileFaceNet",
        "dimensions": 192,                    # Embedding size
        "enabled": True,                      # Whether to use this model
        "quality_threshold": 0.68,            # Minimum quality score
        "description": "MobileFaceNet - Fast lightweight model"
    },
    # ... other models
}
```

**Key Fields:**
- `enabled`: Set to `False` to disable a model without deleting it
- `quality_threshold`: Minimum confidence score to consider a match
- `dimensions`: Size of the embedding vector (192D or 512D)

---

### 2. MULTI_MODEL_CONFIG

**What**: Controls which models participate in verification
**Purpose**: Define the ensemble composition

```python
MULTI_MODEL_CONFIG = {
    "enabled": True,                          # Enable multi-model verification
    "models_for_verification": [             # Which models to use
        "mobilefacenet",
        "arcface_int8",
        "adaface"
    ],
    "consensus_strategy": "weighted",         # How to combine results
    "minimum_consensus": 2                    # How many must agree
}
```

**consensus_strategy Options:**
- `"voting"`: Simple majority vote (each model gets 1 vote)
- `"weighted"`: Weight votes by model confidence scores
- `"unanimous"`: ALL models must agree (strictest)

**minimum_consensus:**
- `2`: At least 2 models must agree (recommended for 3 models)
- `3`: All 3 models must agree (very strict)
- `1`: Any single model can decide (not recommended)

---

### 3. ENSEMBLE_CONFIG

**What**: Advanced tuning parameters for the ensemble
**Purpose**: Fine-tune how models are combined

#### 3a. Model Weights

```python
"model_weights": {
    "mobilefacenet": 0.35,    # 35% weight
    "arcface_int8": 0.35,     # 35% weight
    "adaface": 0.30           # 30% weight
}
```

**Must sum to 1.0**

**How it works:**
- Higher weight = more influence in final decision
- Used when `consensus_strategy = "weighted"`
- Example: If MobileFaceNet says 0.80 with 35% weight, it contributes 0.28 to final score

**When to adjust:**
- Increase weight for models that perform better in your specific environment
- Decrease weight for models that give false positives

---

#### 3b. Temperature Scaling

**What**: Adjusts the distribution of similarity scores
**Why**: Different models output scores in different ranges

```python
"temperature_scaling": {
    "mobilefacenet": {
        "enabled": False,        # No scaling needed
        "temperature": 1.0,      # No change
        "shift": 0.0            # No shift
    },
    "arcface_int8": {
        "enabled": True,         # Apply scaling
        "temperature": 3.0,      # Spread out scores
        "shift": -0.15          # Center around 0.15
    },
    "adaface": {
        "enabled": False,        # Well-distributed already
        "temperature": 1.0,
        "shift": 0.0
    }
}
```

**How Temperature Scaling Works:**

1. **Shift**: Move scores up or down
   ```python
   score_shifted = score + shift
   ```

2. **Temperature**: Spread or compress the distribution
   ```python
   score_scaled = score_shifted / temperature
   ```

**Example:**
```
ArcFace raw score: 0.15
After shift (-0.15): 0.00
After temperature (3.0): 0.00 / 3.0 = 0.00

ArcFace raw score: 0.30
After shift (-0.15): 0.15
After temperature (3.0): 0.15 / 3.0 = 0.05

ArcFace raw score: 0.75
After shift (-0.15): 0.60
After temperature (3.0): 0.60 / 3.0 = 0.20
```

**When to adjust:**
- If a model's scores are too compressed (all scores similar)
- If a model's scores are in a different range than others
- Temperature > 1.0: Spread out scores (make differences larger)
- Temperature < 1.0: Compress scores (make differences smaller)

---

#### 3c. Per-Model Thresholds

```python
"thresholds": {
    "mobilefacenet": 0.50,    # Lower threshold
    "arcface_int8": 0.25,     # Lower due to compressed range
    "adaface": 0.40           # Medium threshold
}
```

**What**: Minimum score for a model to consider it a match
**Why**: Different models have different score ranges

**Override**: These override `quality_threshold` from `FACE_RECOGNITION_MODELS`

---

#### 3d. Combined Thresholds

```python
"combined_thresholds": {
    "high_confidence": 0.55,      # ≥ 0.55 = HIGH
    "medium_confidence": 0.40,    # ≥ 0.40 = MEDIUM
    "match_threshold": 0.35       # < 0.35 = NO MATCH
}
```

**What**: Thresholds for the final combined score
**How it's used:**

```python
if combined_score >= 0.55:
    confidence = "HIGH"
    status = "VERIFIED"
elif combined_score >= 0.40:
    confidence = "MEDIUM"
    status = "VERIFIED"
elif combined_score >= 0.35:
    confidence = "LOW"
    status = "FLAGGED"  # Manual review
else:
    confidence = "NONE"
    status = "FAILED"  # No match
```

---

#### 3e. Voting Strategy Parameters

```python
"voting": {
    "require_all_agree": False,     # Don't require unanimity
    "minimum_agreeing": 1,          # At least 1 model must agree
    "use_weighted_vote": True       # Use model weights
}
```

**require_all_agree:**
- `False`: 2 out of 3 models agreeing is enough (recommended)
- `True`: All 3 models MUST agree (very strict)

**minimum_agreeing:**
- How many models must predict the SAME student
- Typical: 2 for 3-model ensemble

**use_weighted_vote:**
- `True`: Weight votes by confidence scores and model weights
- `False`: Simple counting (1 vote per model)

---

#### 3f. Score Normalization

```python
"normalization": {
    "clip_min": -1.0,          # Clip scores below -1.0
    "clip_max": 1.0,           # Clip scores above 1.0
    "apply_sigmoid": False     # Don't apply sigmoid
}
```

**What**: Preprocessing applied before temperature scaling
**Why**: Prevent extreme outlier scores

**apply_sigmoid:**
- Converts scores to 0-1 range using sigmoid function
- Usually not needed for cosine similarity (already -1 to 1)

---

## Consensus Strategies

### 1. Simple Voting (`"voting"`)

**How it works:**
1. Each model gets 1 vote for its top prediction
2. Student with most votes wins
3. Tie-breaking: highest confidence score

**Example:**
```
MobileFaceNet: Student A (0.75)
ArcFace:       Student A (0.82)
AdaFace:       Student B (0.79)

Result: Student A (2 votes vs 1 vote)
Confidence: 0.82 (highest from agreeing models)
```

**Pros:**
- Simple to understand
- Fair - all models equal say

**Cons:**
- Ignores confidence scores
- Doesn't account for model reliability

---

### 2. Weighted Voting (`"weighted"`) ⭐ **RECOMMENDED**

**How it works:**
1. Each model's vote is weighted by:
   - Model weight (from config)
   - Confidence score
2. Combined score = Σ(weight × confidence)
3. Student with highest combined score wins

**Example:**
```
MobileFaceNet: Student A, score=0.75, weight=0.35
  → Contribution: 0.75 × 0.35 = 0.2625

ArcFace: Student A, score=0.82, weight=0.35
  → Contribution: 0.82 × 0.35 = 0.2870

AdaFace: Student A, score=0.79, weight=0.30
  → Contribution: 0.79 × 0.30 = 0.2370

Combined Score = 0.2625 + 0.2870 + 0.2370 = 0.7865
```

**Pros:**
- Considers both agreement AND confidence
- Can weight more reliable models higher
- Produces calibrated confidence scores

**Cons:**
- More complex
- Requires tuning model weights

---

### 3. Unanimous (`"unanimous"`)

**How it works:**
1. ALL models must predict the same student
2. If any model disagrees, verification fails

**Example:**
```
MobileFaceNet: Student A (0.75)
ArcFace:       Student A (0.82)
AdaFace:       Student B (0.79)

Result: FAILED (not unanimous)
Status: FLAGGED for manual review
```

**Pros:**
- Extremely conservative
- Lowest false positive rate

**Cons:**
- High false negative rate
- May reject valid matches

---

## Temperature Scaling

### Why Do We Need It?

**Problem:** Different models output scores in different ranges:

```
MobileFaceNet: 0.60 - 0.95 (well distributed)
ArcFace W600K: 0.01 - 0.39 (compressed!)
AdaFace:       0.50 - 0.98 (well distributed)
```

**Solution:** Temperature scaling normalizes these ranges

### The Math

```python
def apply_temperature_scaling(score, shift, temperature):
    # Step 1: Shift
    score_shifted = score + shift

    # Step 2: Scale by temperature
    score_scaled = score_shifted / temperature

    return score_scaled
```

### Visual Example

**Before Scaling:**
```
ArcFace scores:
[0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
      ↑ Compressed range (0.10 - 0.35)
```

**After Scaling (shift=-0.15, temp=3.0):**
```
Step 1 (shift by -0.15):
[-0.05, 0.00, 0.05, 0.10, 0.15, 0.20]

Step 2 (divide by 3.0):
[-0.017, 0.00, 0.017, 0.033, 0.050, 0.067]
      ↑ Now comparable to other models
```

---

## Thresholds & Decision Making

### Decision Flow

```
Input Face → 3 Models → Consensus → Combined Score → Decision
                                          ↓
                                   Compare to thresholds:

  ≥ 0.55  →  HIGH confidence  →  ✅ VERIFIED
  ≥ 0.40  →  MEDIUM confidence →  ✅ VERIFIED
  ≥ 0.35  →  LOW confidence   →  🟡 FLAGGED (manual review)
  < 0.35  →  NO MATCH         →  ❌ FAILED
```

### Tuning Thresholds

**Too many false positives?**
- Increase `match_threshold` (e.g., 0.35 → 0.40)
- Increase `high_confidence` (e.g., 0.55 → 0.60)

**Too many false negatives?**
- Decrease `match_threshold` (e.g., 0.35 → 0.30)
- Decrease per-model thresholds

**Too many manual reviews?**
- Increase `medium_confidence` to reduce FLAGGED cases
- Or decrease to catch more edge cases

---

## When This Configuration is Used

### ✅ Used For (NEW INFERENCE ONLY):

1. **Real-time Verification** (Bus Kiosk)
   - When a student taps in at the kiosk
   - Kiosk uses MobileFaceNet (fast)
   - Backend uses ALL 3 models for verification

2. **New Student Enrollment**
   - When parent uploads photos
   - System generates embeddings using all enabled models

3. **Manual Verification Requests**
   - Admin triggers re-verification
   - Uses current configuration

---

### ❌ NOT Used For:

1. **Existing Student Embeddings**
   - Already stored in database
   - NOT regenerated automatically
   - Only regenerated if you explicitly request it

2. **Historical Boarding Events**
   - Past verifications remain unchanged
   - Confidence scores stay the same

3. **Legacy Data**
   - Old embeddings from previous model versions
   - Would need manual migration

---

## Tuning Guide

### Scenario 1: Too Many False Matches

**Symptoms:**
- Backend says "Student A" but it's actually "Student B"
- Different student IDs between kiosk and backend

**Solutions:**
1. Increase `minimum_consensus` from 2 to 3 (require unanimous)
2. Increase `match_threshold` from 0.35 to 0.45
3. Increase per-model thresholds
4. Set `require_all_agree: True`

---

### Scenario 2: Too Many Rejections

**Symptoms:**
- Valid students marked as "FAILED"
- Backend can't find any match

**Solutions:**
1. Decrease `minimum_consensus` from 2 to 1 (allow single model)
2. Decrease `match_threshold` from 0.35 to 0.25
3. Decrease per-model thresholds
4. Check if AdaFace is helping (it handles difficult conditions)

---

### Scenario 3: Poor Performance in Low Light

**Symptoms:**
- Morning/evening verifications fail
- Works fine at noon

**Solutions:**
1. Increase AdaFace weight from 0.30 to 0.40
2. Decrease MobileFaceNet weight from 0.35 to 0.30
3. Enable AdaFace temperature scaling if needed
4. Lower AdaFace threshold

---

### Scenario 4: Slow Verification

**Symptoms:**
- Backend verification takes >10 seconds
- Timeouts in Cloud Tasks

**Solutions:**
1. Disable AdaFace temporarily (set `enabled: False`)
2. Reduce to 2-model ensemble (remove heaviest model)
3. Increase `embedding_batch_size` in `FACE_RECOGNITION_SERVICE_CONFIG`
4. Check Cloud Run instance resources

---

### Scenario 5: Model Disagrees Too Often

**Symptoms:**
- 3 models predict 3 different students
- Lots of FLAGGED events

**Solutions:**
1. Check temperature scaling settings
2. Review per-model thresholds (may be too different)
3. Normalize model weights (make them closer: 0.33, 0.33, 0.34)
4. Enable temperature scaling for models with compressed ranges

---

## Configuration Change Workflow

### Making Changes

1. **Edit Configuration**
   ```bash
   # Edit ml_models/config.py
   vim backend_easy/ml_models/config.py
   ```

2. **Test Locally** (Optional)
   ```bash
   # Run local tests
   cd backend_easy
   pytest tests/ml_tests/
   ```

3. **Commit & Deploy**
   ```bash
   git add ml_models/config.py
   git commit -m "tune: Adjust ensemble weights for low-light performance"
   git push origin develop
   ```

4. **Monitor Results**
   - Check Django Admin for verification results
   - Look at confidence scores
   - Monitor false positive/negative rates

---

## Key Takeaways

### 🎯 Core Concepts

1. **Multi-model = Robust**: 3 models catch each other's errors
2. **Configuration = Tuning**: Adjust weights, thresholds, and strategies
3. **New Inference Only**: Doesn't affect existing data
4. **Consensus Matters**: Agreement between models = higher confidence

### 🔧 Best Practices

1. **Start Conservative**: Use `minimum_consensus: 2` and `weighted` strategy
2. **Monitor Metrics**: Track false positives, false negatives, and manual reviews
3. **Tune Gradually**: Change one parameter at a time
4. **Document Changes**: Note why you made configuration changes

### ⚠️ Common Mistakes

1. **Model weights don't sum to 1.0** → Will cause errors
2. **Temperature scaling without understanding** → Can make things worse
3. **Changing too many parameters at once** → Can't identify what helped
4. **Not testing after changes** → Deploy broken configuration

---

## Getting Help

### Debugging Steps

1. **Check Logs**
   ```bash
   gcloud run services logs read easypool-backend-dev --limit=50
   ```

2. **Review Admin Panel**
   - Look at "Model Breakdown" section
   - Check individual model scores
   - Review voting results

3. **Test Specific Cases**
   - Identify problematic students
   - Check their embeddings quality
   - Test with different photos

### Contact

For questions or issues with model configuration:
1. Check this guide first
2. Review the code in `ml_models/config.py`
3. Look at `consensus_service.py` for implementation details

---

**Last Updated:** 2025-11-21
**Configuration Version:** 3-Model Ensemble (MobileFaceNet + ArcFace + AdaFace)
**Applies To:** NEW inference only (not historical data)
