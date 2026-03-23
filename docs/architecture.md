# System Architecture

## Overview

The Smart Window Environment Monitor uses a three-layer architecture:

1. **Sensing Layer** — Physical sensors (BME280, INMP441) on an ESP32 MCU, plus TfL API polling from a laptop
2. **Storage Layer** — InfluxDB Cloud (AWS EU Frankfurt) time-series database
3. **Presentation Layer** — Single-file HTML dashboard with embedded analytics

## Data Flow

```
BME280 ──I2C──┐
              ├── ESP32 ──WiFi/HTTPS──┐
INMP441 ─I2S──┘     (30s)            │
                                      ├── InfluxDB Cloud ── CSV Export ── Python Analysis ── Dashboard
TfL APIs ────HTTPS────────────────────┘
  - Arrivals       (5min)
  - Line Status
  - Air Quality
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | InfluxDB Cloud | Purpose-built for time-series; remote access; free tier sufficient |
| Protocol | Direct HTTPS | Single-node system; MQTT unnecessary without broker |
| Sampling | 30s sensor, 5min API | Balances granularity with storage and API rate limits |
| Dashboard | Single HTML file | Zero-dependency; marker can open without setup |
| Noise metric | Relative dB (uncalibrated) | No calibration source; sufficient for correlation analysis |
| Redundancy | Dual laptop collection | Mitigates sleep/crash risk for TfL polling |

## Pin Mapping (Heltec WiFi LoRa 32 V3.2)

| Sensor | Pin | GPIO |
|--------|-----|------|
| BME280 SDA | I2C Data | GPIO 6 |
| BME280 SCL | I2C Clock | GPIO 5 |
| INMP441 SCK | I2S Clock | GPIO 48 |
| INMP441 WS | I2S Word Select | GPIO 47 |
| INMP441 SD | I2S Data | GPIO 7 |
| OLED SDA | Display Data | SDA_OLED (built-in) |
| OLED SCL | Display Clock | SCL_OLED (built-in) |
