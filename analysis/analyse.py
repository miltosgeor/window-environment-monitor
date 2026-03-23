"""
Smart Window Environment Monitor — Data Analysis Pipeline
ELEC70126 IoT Coursework — Imperial College London 2026

This script documents the cleaning, analysis, and dashboard data
preparation pipeline. The processed output is embedded as a JSON
blob in dashboard/index.html.

Input:  4 CSV files exported from InfluxDB Cloud
Output: window.__DD JSON object with all analytics

Usage:
  pip install pandas numpy scipy
  python analyse.py

Note: Raw CSVs are not included in the repo (see data/README.md).
      The dashboard already contains the processed results.
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
from datetime import datetime

# ============================================================
#  FILE PATHS (update to match your CSV exports)
# ============================================================
SENSOR_CSV = "../data/environment.csv"
ARRIVALS_CSV = "../data/tfl_train_arrivals.csv"
STATUS_CSV = "../data/tfl_service_status.csv"
AIR_CSV = "../data/tfl_air.csv"

# ============================================================
#  1. DATA LOADING & CLEANING
# ============================================================

def load_and_clean():
    """Load CSVs and apply cleaning rules."""

    # InfluxDB CSVs have 3 header rows — skip them
    sensor = pd.read_csv(SENSOR_CSV, skiprows=3)
    arrivals = pd.read_csv(ARRIVALS_CSV, skiprows=3)
    status = pd.read_csv(STATUS_CSV, skiprows=3)
    air = pd.read_csv(AIR_CSV, skiprows=3)

    # Parse timestamps
    for df in [sensor, arrivals, status, air]:
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values('time', inplace=True)

    # --- Cleaning rules ---

    # 1. Remove indoor testing data (Mar 6-7, first 18 hours)
    cutoff = pd.Timestamp('2026-03-09T00:00:00Z')
    sensor = sensor[sensor['time'] >= cutoff].copy()
    arrivals = arrivals[arrivals['time'] >= cutoff].copy()
    status = status[status['time'] >= cutoff].copy()
    air = air[air['time'] >= cutoff].copy()

    # 2. Force all numeric fields to float (prevents InfluxDB schema conflicts)
    for col in ['temperature', 'humidity', 'pressure', 'noise_db', 'wifi_rssi']:
        if col in sensor.columns:
            sensor[col] = pd.to_numeric(sensor[col], errors='coerce')

    for col in arrivals.select_dtypes(include=[np.number]).columns:
        arrivals[col] = arrivals[col].astype(float)

    # 3. Document the 20.6-hour gap on March 10 (laptop sleep)
    gaps = sensor['time'].diff().dt.total_seconds()
    big_gaps = gaps[gaps > 3600]
    if len(big_gaps) > 0:
        print(f"Data gaps > 1 hour: {len(big_gaps)}")
        for idx in big_gaps.index:
            gap_hrs = big_gaps[idx] / 3600
            print(f"  {sensor.loc[idx, 'time']}: {gap_hrs:.1f}h gap")

    # 4. End date
    end_cutoff = pd.Timestamp('2026-03-19T23:59:59Z')
    sensor = sensor[sensor['time'] <= end_cutoff]
    arrivals = arrivals[arrivals['time'] <= end_cutoff]

    print(f"\nCleaned data:")
    print(f"  Sensor:   {len(sensor)} points")
    print(f"  Arrivals: {len(arrivals)} points")
    print(f"  Status:   {len(status)} points")
    print(f"  Air:      {len(air)} points")

    return sensor, arrivals, status, air


# ============================================================
#  2. STATISTICAL ANALYSIS
# ============================================================

def compute_summary(sensor, arrivals):
    """Compute summary statistics for all variables."""
    summary = {}
    for col, name in [('temperature','temperature'), ('humidity','humidity'),
                      ('pressure','pressure'), ('noise_db','noise_db')]:
        s = sensor[col].dropna()
        summary[name] = {
            'mean': round(s.mean(), 2), 'median': round(s.median(), 2),
            'min': round(s.min(), 2), 'max': round(s.max(), 2),
            'std': round(s.std(), 2),
            'skew': round(s.skew(), 2), 'kurtosis': round(s.kurtosis(), 2)
        }

    if 'total_arrivals' in arrivals.columns:
        a = arrivals['total_arrivals'].dropna()
        summary['total_arrivals'] = {
            'mean': round(a.mean(), 2), 'median': round(a.median(), 2),
            'min': round(a.min(), 2), 'max': round(a.max(), 2),
            'std': round(a.std(), 2)
        }

    return summary


def hypothesis_tests(sensor):
    """Day (07-19) vs Night t-tests with effect sizes."""
    sensor = sensor.copy()
    sensor['hour'] = sensor['time'].dt.hour
    day = sensor[(sensor['hour'] >= 7) & (sensor['hour'] < 19)]
    night = sensor[(sensor['hour'] < 7) | (sensor['hour'] >= 19)]

    results = {}
    for col, key in [('noise_db','noise'), ('temperature','temp'), ('humidity','humid')]:
        t_stat, p_val = stats.ttest_ind(day[col].dropna(), night[col].dropna(), equal_var=False)
        d1, d2 = day[col].dropna(), night[col].dropna()
        pooled_std = np.sqrt((d1.std()**2 + d2.std()**2) / 2)
        cohens_d = (d1.mean() - d2.mean()) / pooled_std if pooled_std > 0 else 0
        results[key] = {
            't': round(t_stat, 2), 'p': f"{p_val:.2e}",
            'cohens_d': round(cohens_d, 2)
        }

    day_night = {
        'day': {
            'noise': round(day['noise_db'].mean(), 2),
            'temp': round(day['temperature'].mean(), 2),
            'humid': round(day['humidity'].mean(), 2),
            'trains': 0, 'count': len(day)
        },
        'night': {
            'noise': round(night['noise_db'].mean(), 2),
            'temp': round(night['temperature'].mean(), 2),
            'humid': round(night['humidity'].mean(), 2),
            'trains': 0, 'count': len(night)
        }
    }

    return results, day_night


def compute_correlations(sensor, arrivals):
    """Pairwise Pearson correlations + noise-trains hourly."""
    corrs = {}
    pairs = [
        ('temperature', 'humidity'), ('temperature', 'noise_db'),
        ('humidity', 'noise_db'), ('pressure', 'noise_db'),
        ('temperature', 'pressure')
    ]
    for a, b in pairs:
        mask = sensor[[a, b]].dropna()
        r, p = stats.pearsonr(mask[a], mask[b])
        slope, intercept = np.polyfit(mask[a], mask[b], 1)
        corrs[f"{a}__{b}"] = {
            'r': round(r, 4), 'p': f"{p:.2e}",
            'slope': round(slope, 4), 'intercept': round(intercept, 4)
        }

    # Hourly noise vs trains correlation
    sensor_h = sensor.copy()
    sensor_h['hour'] = sensor_h['time'].dt.hour
    noise_hourly = sensor_h.groupby('hour')['noise_db'].mean()

    arrivals_h = arrivals.copy()
    arrivals_h['hour'] = arrivals_h['time'].dt.hour
    trains_hourly = arrivals_h.groupby('hour')['total_arrivals'].mean()

    merged = pd.DataFrame({'noise': noise_hourly, 'trains': trains_hourly}).dropna()
    if len(merged) > 2:
        r, p = stats.pearsonr(merged['noise'], merged['trains'])
        corrs['noise__trains_hourly'] = {'r': round(r, 4), 'p': f"{p:.2e}"}

    return corrs


def anomaly_detection(sensor, sigma=2):
    """Detect noise anomalies using mean + n*sigma threshold."""
    noise = sensor['noise_db'].dropna()
    mean_noise = noise.mean()
    std_noise = noise.std()
    threshold = round(mean_noise + sigma * std_noise, 2)

    anomalies = sensor[sensor['noise_db'] > threshold].copy()
    anomalies['sigma'] = round((anomalies['noise_db'] - mean_noise) / std_noise, 1)
    anomalies['hour'] = anomalies['time'].dt.hour

    # Simple cause labelling based on time-of-day heuristics
    def label_cause(row):
        h = row['hour']
        if 9 <= h <= 17 and row['noise_db'] > 100:
            return "Heavy construction"
        elif 9 <= h <= 17:
            return "Peak construction"
        elif 12 <= h <= 14:
            return "Lunchtime activity"
        elif 18 <= h <= 22:
            return "Visitors / social"
        elif 22 <= h or h < 2:
            return "Late night social"
        elif 2 <= h < 6:
            return "Night disturbance"
        elif 6 <= h < 9:
            return "Morning activity"
        else:
            return "Weekend activity"

    anomalies['cause'] = anomalies.apply(label_cause, axis=1)

    stats_out = {
        'mean': round(mean_noise, 2), 'std': round(std_noise, 2),
        'threshold': threshold,
        'count': int(len(anomalies)),
        'pct': round(100 * len(anomalies) / len(noise), 1)
    }

    return anomalies, stats_out


# ============================================================
#  3. MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Window Environment Monitor — Analysis Pipeline")
    print("=" * 60)

    sensor, arrivals, status, air = load_and_clean()

    print("\n--- Summary Statistics ---")
    summary = compute_summary(sensor, arrivals)
    for k, v in summary.items():
        print(f"  {k}: mean={v['mean']}, range=[{v['min']}, {v['max']}]")

    print("\n--- Hypothesis Tests (Day vs Night) ---")
    ttests, day_night = hypothesis_tests(sensor)
    for k, v in ttests.items():
        print(f"  {k}: t={v['t']}, p={v['p']}, d={v['cohens_d']}")

    print("\n--- Correlations ---")
    correlations = compute_correlations(sensor, arrivals)
    for k, v in correlations.items():
        print(f"  {k}: r={v['r']}, p={v['p']}")

    print("\n--- Anomaly Detection ---")
    anomalies, anom_stats = anomaly_detection(sensor)
    print(f"  Threshold: {anom_stats['threshold']} dB")
    print(f"  Anomalies: {anom_stats['count']} ({anom_stats['pct']}%)")

    print("\n✅ Analysis complete. Results ready for dashboard embedding.")
