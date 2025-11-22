# A/B Testing Guide: Finding the Optimal Face Recognition Configuration

## Overview

We have a **config versioning system** + **BigQuery analytics** that lets us test different model combinations WITHOUT overwhelming the backend. Each boarding event stores which config was used, then we analyze results in BigQuery to find the "G-spot" (optimal configuration).

## Architecture: Separation of Concerns

```
┌──────────────────────────────────────────┐
│  Production Backend (Cloud Run)          │
│  - Processes boarding events             │
│  - Uses ACTIVE config only               │
│  - Lightweight, fast                     │
└──────────────────────────────────────────┘
                ↓ Daily export
┌──────────────────────────────────────────┐
│  BigQuery (Analytics Infrastructure)     │
│  - Stores ALL boarding events            │
│  - Compare configs side-by-side         │
│  - 1M+ events/day capacity              │
│  - No impact on backend performance!    │
└──────────────────────────────────────────┘
```

## How Config Versioning Works

Every boarding event stores:
- `backend_config_version`: Which ML config was used (V1, V2, V3...)
- `model_consensus_data`: Full model results (scores, top-K gaps, etc.)
- Old events stay unchanged (immutable history)

## A/B Testing Strategies

### Strategy 1: Time-Based Testing (SAFEST)

**Day 1: Baseline (Current 2-model)**
```python
python manage.py shell
>>> from ml_config.models import BackendModelConfiguration
>>> config_v1 = BackendModelConfiguration.objects.create(
    name="V1: 2-Model Baseline",
    description="Current production: MobileFaceNet + ArcFace",
    is_active=True,
    mobilefacenet_weight=0.50,
    arcface_weight=0.50,
    adaface_weight=0.0,
    high_confidence_threshold=0.60,
    medium_confidence_threshold=0.45,
    minimum_consensus=2,
)
```

**Day 2: Equal 3-Model**
```python
>>> config_v2 = BackendModelConfiguration.objects.create(
    name="V2: 3-Model Equal Weight",
    description="Testing AdaFace with equal weights",
    is_active=True,  # Auto-deactivates V1
    mobilefacenet_weight=0.33,
    arcface_weight=0.34,
    adaface_weight=0.33,
    minimum_consensus=2,
)
```

**Day 3: Weighted 3-Model (Banking Priorities)**
```python
>>> config_v3 = BackendModelConfiguration.objects.create(
    name="V3: 3-Model Weighted (ArcFace Priority)",
    description="Prioritize most accurate model (ArcFace)",
    is_active=True,
    mobilefacenet_weight=0.30,
    arcface_weight=0.40,  # Highest weight
    adaface_weight=0.30,
    minimum_consensus=2,
)
```

**Day 4: Stricter Thresholds**
```python
>>> config_v4 = BackendModelConfiguration.objects.create(
    name="V4: Banking-Grade Strict Thresholds",
    description="Stricter thresholds for lower FAR",
    is_active=True,
    mobilefacenet_weight=0.30,
    arcface_weight=0.40,
    adaface_weight=0.30,
    high_confidence_threshold=0.70,  # Raised from 0.60
    medium_confidence_threshold=0.55,  # Raised from 0.45
    minimum_consensus=3,  # All models must agree
)
```

### Strategy 2: Traffic Splitting (ADVANCED)

**80% Safe + 20% Experimental**
```python
# Modify boarding event processing to randomly assign config:
import random

def get_config_for_event():
    if random.random() < 0.8:
        return get_safe_config()  # V1
    else:
        return get_experimental_config()  # V2
```

**Benefits:**
- Real-time comparison
- Lower risk (80% still use proven config)
- Faster results (both configs tested simultaneously)

## Finding the G-Spot: BigQuery Analysis

### Query 1: Compare FAR Across Configs

```sql
-- Which config has lowest False Accept Rate?
SELECT
  config_version,
  COUNT(*) as total_events,
  COUNTIF(verification_status = 'verified'
    AND student_id != (SELECT predicted_student_id
      FROM UNNEST(model_results)
      WHERE model_name = 'arcface_int8'))
    / COUNTIF(verification_status = 'verified') * 100 as FAR_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY config_version
ORDER BY FAR_percent ASC
```

**Expected Output:**
```
config_version | total_events | FAR_percent
---------------|--------------|-------------
3              | 1250         | 0.08%   ← BEST (lowest FAR)
1              | 2500         | 0.12%
2              | 1500         | 0.15%
4              | 800          | 0.10%
```

### Query 2: Compare Accuracy Per Model

```sql
-- Which config gives best per-model accuracy?
SELECT
  config_version,
  model.model_name,
  COUNTIF(model.predicted_student_id = student_id)
    / COUNT(*) * 100 as accuracy_percent
FROM `easypool-backend.ml_analytics.boarding_events`,
  UNNEST(model_results) as model
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND student_id IS NOT NULL
GROUP BY config_version, model_name
ORDER BY config_version, accuracy_percent DESC
```

### Query 3: Compare Consensus Performance

```sql
-- How often do models agree? (Higher = better calibration)
SELECT
  config_version,
  COUNTIF(consensus_count >= 2) / COUNT(*) * 100 as agreement_rate_pct,
  AVG(confidence_score) as avg_confidence,
  COUNTIF(verification_status = 'flagged') / COUNT(*) * 100 as manual_review_pct
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY config_version
ORDER BY agreement_rate_pct DESC
```

### Query 4: Cost-Benefit Analysis (Cascading)

```sql
-- Which config uses fast path most often? (Lower inference cost)
SELECT
  config_version,
  COUNTIF(used_fast_path = TRUE) / COUNT(*) * 100 as fast_path_pct,
  AVG(confidence_score) as avg_score,
  COUNTIF(verification_status = 'verified') / COUNT(*) * 100 as verified_pct
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY config_version
```

**Optimal Config Should Have:**
- Fast path: 75-85% (lower inference cost)
- Verified rate: 95%+ (not too strict)
- FAR < 0.1% (banking standard)

## Decision Matrix: Finding the G-Spot

| Metric | Weight | V1 | V2 | V3 | V4 |
|--------|--------|----|----|----|----|
| FAR (lower better) | 40% | 0.12% | 0.15% | **0.08%** | 0.10% |
| Accuracy | 30% | 99.5% | **99.6%** | 99.6% | 99.4% |
| Fast path % | 15% | **82%** | 75% | 76% | 70% |
| Manual review % | 15% | 3.5% | 4.2% | **2.8%** | 5.1% |
| **TOTAL SCORE** | 100% | 87.2 | 84.5 | **91.4** | 85.7 |

**Winner: Config V3** (3-model weighted with ArcFace priority)

## Implementation: Switching Configs

### Manual Switch (Django Admin)
1. Go to Django Admin → Backend Model Configurations
2. Click on desired config
3. Check "is_active" → Save
4. All other configs auto-deactivate

### Automated Switch (After A/B Test)
```python
# After analyzing BigQuery results, activate winning config
python manage.py shell
>>> from ml_config.models import BackendModelConfiguration
>>> winner = BackendModelConfiguration.objects.get(version=3)
>>> winner.is_active = True
>>> winner.save()  # Auto-deactivates others
```

## Looker Studio Dashboard: Real-Time A/B Testing

Create dashboard with:

**Panel 1: Config Comparison Table**
```sql
SELECT
  config_version,
  name,
  COUNT(*) as events,
  AVG(confidence_score) as avg_score,
  FAR, FRR, accuracy, manual_review_rate
FROM ml_analytics.config_comparison_view
GROUP BY config_version, name
```

**Panel 2: FAR Over Time (Per Config)**
- Line chart with one line per config_version
- X-axis: Date
- Y-axis: FAR %
- Target line: 0.1%

**Panel 3: Cost Analysis**
- Fast path usage per config
- Inference time estimates
- Cloud Run costs

## Best Practices

1. **Run each config for minimum 1 day** (get enough data)
2. **Minimum 500 events per config** (statistical significance)
3. **Don't change multiple parameters at once** (isolate variables)
4. **Keep V1 as baseline** (always compare against proven config)
5. **Monitor in production** (BigQuery alerts on FAR spikes)

## Safety Guardrails

```python
# In BigQuery scheduled query: Alert if FAR exceeds threshold
IF FAR > 0.15% THEN
    SEND_EMAIL("ML Team", "Config V{} exceeds FAR threshold!")
    AUTO_ROLLBACK_TO_V1()
END IF
```

## Next Steps

1. Export today's events to BigQuery: `python manage.py export_to_bigquery`
2. Create baseline config (V1)
3. Wait 1 day, analyze results
4. Create experimental config (V2)
5. Compare in BigQuery after 1 day
6. Repeat with V3, V4... until you find the G-spot

**Expected timeline: 5-7 days to find optimal configuration**
