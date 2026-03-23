"""
Smart Window Environment Monitor — TfL Data Collector
ELEC70126 IoT Coursework — Imperial College London 2026

Polls TfL APIs every 5 minutes and sends data to InfluxDB Cloud.

APIs:
  1. StopPoint Arrivals — train arrivals at Gloucester Road
  2. Line Status — service disruptions (Circle, District, Piccadilly)
  3. Air Quality — London-wide air quality index

Setup:
  pip install influxdb-client requests

Usage:
  python tfl_collector.py
  (runs continuously — use screen/tmux or keep terminal open)
"""

import requests
import time
import json
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ============================================================
#  CREDENTIALS (redacted — fill before use)
# ============================================================
INFLUXDB_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "REDACTED"
INFLUXDB_ORG = "REDACTED"
INFLUXDB_BUCKET = "window_monitor"

TFL_APP_KEY = ""  # Optional — works without key at lower rate limit

# Gloucester Road station
STATION_NAPTAN = "940GZZLUGTR"
STATION_NAME = "Gloucester Road"
LINES = ["circle", "district", "piccadilly"]
POLL_INTERVAL = 300  # 5 minutes


def get_tfl_url(endpoint):
    base = f"https://api.tfl.gov.uk/{endpoint}"
    if TFL_APP_KEY:
        sep = "&" if "?" in base else "?"
        base += f"{sep}app_key={TFL_APP_KEY}"
    return base


def fetch_arrivals():
    try:
        url = get_tfl_url(f"StopPoint/{STATION_NAPTAN}/Arrivals")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result = {"total_arrivals": float(len(data))}
        for line in LINES:
            count = len([a for a in data if a.get("lineName", "").lower() == line])
            result[f"arrivals_{line}"] = float(count)

        if data:
            waits = [a.get("timeToStation", 0) for a in data if a.get("timeToStation")]
            result["avg_wait_seconds"] = float(sum(waits) / len(waits)) if waits else 0.0

        return result
    except Exception as e:
        print(f"  [ERROR] Arrivals: {e}")
        return None


def fetch_line_status():
    try:
        lines_str = ",".join(LINES)
        url = get_tfl_url(f"Line/{lines_str}/Status")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result = {}
        for line_data in data:
            name = line_data["id"].lower()
            statuses = line_data.get("lineStatuses", [])
            if statuses:
                result[f"status_{name}"] = float(statuses[0].get("statusSeverity", -1))
                result[f"status_{name}_text"] = statuses[0].get("statusSeverityDescription", "Unknown")
        return result
    except Exception as e:
        print(f"  [ERROR] Line status: {e}")
        return None


def fetch_air_quality():
    try:
        url = get_tfl_url("AirQuality")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        forecasts = data.get("currentForecast", [])
        if forecasts:
            band = forecasts[0].get("forecastBand", "")
            band_map = {"Low": 1.0, "Moderate": 2.0, "High": 3.0, "Very High": 4.0}
            return {
                "air_quality_band": band_map.get(band, 0.0),
                "air_quality_text": band
            }
        return {"air_quality_band": 0.0}
    except Exception as e:
        print(f"  [ERROR] Air quality: {e}")
        return None


def send_to_influxdb(write_api, data_dict, measurement):
    try:
        point = Point(measurement)
        point.tag("station", STATION_NAME)
        point.tag("source", "tfl_api")
        for key, value in data_dict.items():
            if isinstance(value, str):
                point.tag(key, value)
            elif isinstance(value, (int, float)):
                point.field(key, float(value))  # Force float to avoid schema conflicts
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        return True
    except Exception as e:
        print(f"  [ERROR] InfluxDB write: {e}")
        return False


def main():
    print("=" * 55)
    print("  Window Monitor — TfL Data Collector")
    print("=" * 55)
    print(f"  Station: {STATION_NAME} ({STATION_NAPTAN})")
    print(f"  Lines:   {', '.join(LINES)}")
    print(f"  Poll:    every {POLL_INTERVAL}s")
    print("=" * 55)

    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        health = client.health()
        print(f"\n[OK] InfluxDB: {health.status}\n")
    except Exception as e:
        print(f"\n[FAIL] InfluxDB: {e}\n")

    poll_count = 0

    while True:
        poll_count += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Poll #{poll_count}")
        sent = 0

        arrivals = fetch_arrivals()
        if arrivals and send_to_influxdb(write_api, arrivals, "tfl_train_arrivals"):
            sent += 1

        status = fetch_line_status()
        if status and send_to_influxdb(write_api, status, "tfl_service_status"):
            sent += 1

        air = fetch_air_quality()
        if air and send_to_influxdb(write_api, air, "tfl_air"):
            sent += 1

        print(f"  >> Sent {sent}/3 to InfluxDB")
        print(f"  >> Next poll in {POLL_INTERVAL}s\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
