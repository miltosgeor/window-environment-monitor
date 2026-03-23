# Data

## Processed Data (included)

**`processed_data.json`** — Complete analysis output used by the dashboard. Contains:
- Downsampled sensor readings (5-min intervals, ~3,161 points)
- Train arrival counts by line (~2,858 points)
- Hourly and daily aggregations
- Summary statistics (mean, median, std, skew, kurtosis)
- Welch's t-test results (day vs night)
- Pearson correlation matrix and pairwise correlations
- Anomaly detection results (mean + 2σ threshold, top 100 anomalies)
- TfL service status summary and air quality breakdown
- Weekday vs weekend comparisons

This JSON is also embedded in `dashboard/index.html` as `window.__DD`.

## Raw CSVs (included)

Exported from InfluxDB Cloud, covering 9–19 March 2026:

| File | Measurement | Source | Interval | Points |
|------|------------|--------|----------|--------|
| `environment.csv` | `environment` | ESP32 + BME280 + INMP441 | 30s | ~30,948 |
| `tfl_train_arrivals.csv` | `tfl_train_arrivals` | TfL Arrivals API | 5 min | ~2,858 |
| `tfl_service_status.csv` | `tfl_service_status` | TfL Line Status API | 5 min | ~2,858 |
| `tfl_air.csv` | `tfl_air` | TfL Air Quality API | 5 min | ~2,858 |

### Reproducing the Export

1. Go to InfluxDB Cloud → Data Explorer
2. Select bucket `window_monitor`
3. Select measurement
4. Set time range to `2026-03-09` to `2026-03-19`
5. Click **CSV** download
