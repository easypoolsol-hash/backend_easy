# Looker Studio Dashboards Setup Guide

## Overview

Banking-grade face recognition requires comprehensive analytics to monitor model performance, detect drift, and optimize configurations. This guide sets up 4 Looker Studio dashboards connected to BigQuery.

## Prerequisites

1. **BigQuery Export Running**: The `export_to_bigquery` command should be running daily
2. **BigQuery Dataset**: `ml_analytics` dataset with `boarding_events` table
3. **Looker Studio Access**: Access to https://lookerstudio.google.com

## Dashboard 1: Model Performance Dashboard

### Purpose
Track banking-grade accuracy metrics: FAR, FRR, accuracy per model, ROC curves

### Data Source
- **BigQuery Table**: `easypool-backend.ml_analytics.boarding_events`
- **Time Range**: Last 30 days

### Key Metrics

#### 1. False Accept Rate (FAR)
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(verification_status = 'verified' AND student_id != COALESCE(
    (SELECT predicted_student_id FROM UNNEST(model_results) WHERE model_name = 'arcface_int8')
  , '')) / COUNTIF(verification_status = 'verified') * 100 as far_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Line chart
- **X-axis**: Date
- **Y-axis**: FAR %
- **Target Line**: 0.1% (banking standard)
- **Alert**: Red if > 0.1%

#### 2. False Rejection Rate (FRR)
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(verification_status = 'failed' OR verification_status = 'flagged') / COUNT(*) * 100 as frr_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Line chart
- **X-axis**: Date
- **Y-axis**: FRR %
- **Target Line**: 1% (banking standard)
- **Alert**: Orange if > 1%

#### 3. Per-Model Accuracy
**SQL Query:**
```sql
SELECT
  model.model_name,
  DATE(timestamp) as date,
  COUNTIF(model.predicted_student_id = student_id) / COUNT(*) * 100 as accuracy_percent
FROM `easypool-backend.ml_analytics.boarding_events`,
  UNNEST(model_results) as model
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND student_id IS NOT NULL
GROUP BY model_name, date
ORDER BY model_name, date DESC
```

**Visualization**: Multi-line chart
- **X-axis**: Date
- **Series**: One line per model (MobileFaceNet, ArcFace, AdaFace)
- **Y-axis**: Accuracy %
- **Target**: 99.5%+

#### 4. Confidence Score Distribution
**SQL Query:**
```sql
SELECT
  ROUND(confidence_score, 1) as score_bucket,
  COUNT(*) as count
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND confidence_score IS NOT NULL
GROUP BY score_bucket
ORDER BY score_bucket
```

**Visualization**: Histogram
- **X-axis**: Confidence score (0.0 - 1.0)
- **Y-axis**: Count
- **Expected**: Most scores > 0.6 (high confidence threshold)

---

## Dashboard 2: Top-K Analysis Dashboard

### Purpose
Analyze gap distributions, detect ambiguous cases (Lalit vs ADVIK), confusion matrix

### Key Metrics

#### 1. Top-K Gap Distribution
**SQL Query:**
```sql
SELECT
  model.model_name,
  ROUND(model.top_k_gap, 2) as gap_bucket,
  COUNT(*) as count,
  COUNTIF(model.is_ambiguous) as ambiguous_count
FROM `easypool-backend.ml_analytics.boarding_events`,
  UNNEST(model_results) as model
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND model.top_k_gap IS NOT NULL
GROUP BY model_name, gap_bucket
ORDER BY model_name, gap_bucket
```

**Visualization**: Stacked histogram
- **X-axis**: Gap value (0.0 - 1.0)
- **Y-axis**: Count
- **Red zone**: Gap < 0.12 (ambiguous threshold)
- **Series**: Per model

#### 2. Ambiguous Case Rate
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(model_results) WHERE is_ambiguous = TRUE
  )) / COUNT(*) * 100 as ambiguous_rate_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Line chart
- **X-axis**: Date
- **Y-axis**: % of events with ambiguous results
- **Insight**: Should be < 5% with banking-grade models

#### 3. Top-5 Confusion Matrix
**SQL Query:**
```sql
SELECT
  actual_student_id,
  predicted_student_id,
  COUNT(*) as confusion_count
FROM (
  SELECT
    student_id as actual_student_id,
    model.predicted_student_id
  FROM `easypool-backend.ml_analytics.boarding_events`,
    UNNEST(model_results) as model
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    AND student_id IS NOT NULL
    AND model.model_name = 'arcface_int8'  -- Use most accurate model
)
GROUP BY actual_student_id, predicted_student_id
HAVING confusion_count > 5  -- Only show frequent confusions
ORDER BY confusion_count DESC
LIMIT 20
```

**Visualization**: Heatmap
- **Rows**: Actual student
- **Columns**: Predicted student
- **Color**: Darker = more confusions
- **Highlight**: Off-diagonal (errors)

---

## Dashboard 3: Drift Detection Dashboard

### Purpose
Monitor score distributions over time, detect model drift using statistical tests

### Key Metrics

#### 1. Weekly Score Distribution Comparison
**SQL Query:**
```sql
WITH weekly_scores AS (
  SELECT
    DATE_TRUNC(timestamp, WEEK) as week,
    model.model_name,
    model.confidence_score
  FROM `easypool-backend.ml_analytics.boarding_events`,
    UNNEST(model_results) as model
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 12 WEEK)
    AND model.confidence_score IS NOT NULL
)
SELECT
  week,
  model_name,
  APPROX_QUANTILES(confidence_score, 100)[OFFSET(50)] as p50_median,
  APPROX_QUANTILES(confidence_score, 100)[OFFSET(25)] as p25,
  APPROX_QUANTILES(confidence_score, 100)[OFFSET(75)] as p75,
  AVG(confidence_score) as mean_score,
  STDDEV(confidence_score) as stddev_score
FROM weekly_scores
GROUP BY week, model_name
ORDER BY model_name, week DESC
```

**Visualization**: Box plot per week
- **X-axis**: Week
- **Series**: Per model
- **Box plot**: p25, median, p75
- **Alert**: If distribution shifts significantly

#### 2. Model Agreement Rate Over Time
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(consensus_count >= 2) / COUNT(*) * 100 as agreement_rate_percent,
  AVG(consensus_count) as avg_consensus
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND verification_status = 'verified'
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Line chart
- **X-axis**: Date
- **Y-axis**: % models agreeing
- **Expected**: 80%+ (2+ models agree)

#### 3. Cascading Fast Path Usage
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(used_fast_path = TRUE) / COUNT(*) * 100 as fast_path_percent,
  COUNTIF(escalated_to_ensemble = TRUE) / COUNT(*) * 100 as ensemble_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Stacked area chart
- **X-axis**: Date
- **Series**: Fast path vs ensemble
- **Expected**: 80% fast path, 20% ensemble

---

## Dashboard 4: Business Metrics Dashboard

### Purpose
Track business KPIs: boarding time, manual review rate, parent complaints

### Key Metrics

#### 1. Daily Boarding Volume
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNT(*) as total_boardings,
  COUNTIF(verification_status = 'verified') as verified_count,
  COUNTIF(verification_status = 'flagged') as flagged_count,
  COUNTIF(verification_status = 'failed') as failed_count
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Stacked bar chart
- **X-axis**: Date
- **Series**: Verified (green), Flagged (orange), Failed (red)

#### 2. Manual Review Rate
**SQL Query:**
```sql
SELECT
  DATE(timestamp) as date,
  COUNTIF(verification_status = 'flagged') / COUNT(*) * 100 as manual_review_rate_percent
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC
```

**Visualization**: Line chart
- **X-axis**: Date
- **Y-axis**: % flagged for review
- **Target**: < 5% (banking efficiency)

#### 3. Per-Kiosk Performance
**SQL Query:**
```sql
SELECT
  kiosk_name,
  COUNT(*) as total_events,
  COUNTIF(verification_status = 'verified') / COUNT(*) * 100 as success_rate_percent,
  AVG(confidence_score) as avg_confidence
FROM `easypool-backend.ml_analytics.boarding_events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND kiosk_name IS NOT NULL
GROUP BY kiosk_name
ORDER BY total_events DESC
```

**Visualization**: Table
- **Columns**: Kiosk name, total events, success rate %, avg confidence
- **Highlight**: Red if success rate < 95%

---

## Setup Instructions

### Step 1: Create Data Source

1. Go to https://lookerstudio.google.com
2. Click **Create** → **Data Source**
3. Select **BigQuery**
4. Navigate to: `easypool-backend` → `ml_analytics` → `boarding_events`
5. Click **CONNECT**
6. Name it: "ML Analytics - Boarding Events"

### Step 2: Create Dashboard 1 (Model Performance)

1. Click **Create** → **Report**
2. Select the "ML Analytics - Boarding Events" data source
3. Add charts using the SQL queries above
4. Set refresh to: **Daily at 2:00 AM**
5. Share with: ML team, operations team

### Step 3: Repeat for Dashboards 2-4

Create separate reports for each dashboard following the same pattern.

### Step 4: Set Up Alerts

For critical metrics:
1. **FAR > 0.1%**: Email alert to ML team
2. **FRR > 1%**: Email alert to ML team
3. **Manual review rate > 5%**: Email alert to operations
4. **Drift detected**: Email alert to ML team

---

## Expected Results

With banking-grade dashboards:
- **Real-time visibility** into model performance
- **Early drift detection** before accuracy degrades
- **Operational insights** for kiosk management
- **Compliance reporting** for banking-standard audits

## Maintenance

- **Daily**: Review dashboards for anomalies
- **Weekly**: Check drift metrics
- **Monthly**: Tune thresholds based on trends
- **Quarterly**: Re-calibrate temperature scaling if needed
