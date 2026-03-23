# 🪟 Smart Window Environment Monitor

**ELEC70126 — Internet of Things and Applications**
Imperial College London · March 2026

An IoT system that monitors environmental conditions near a window at Gloucester Road, London, and investigates the relationship between urban transport activity and local noise/climate data.

---

## Overview

This project deploys a custom sensor node (Heltec ESP32 + BME280 + INMP441) alongside TfL public API data to test the **window hypothesis**: that noise levels at a residential window near Gloucester Road Underground station are strongly driven by train frequency.

**Key finding:** Hourly noise–train correlation **r = 0.8685** (p < 0.001), confirming a strong positive relationship.

### Data Sources (5 time-series)

| # | Source | Type | Interval | Sensor/API |
|---|--------|------|----------|------------|
| 1 | Temperature (°C) | Physical sensor | 30s | BME280 via I2C |
| 2 | Humidity (%) | Physical sensor | 30s | BME280 via I2C |
| 3 | Barometric pressure (hPa) | Physical sensor | 30s | BME280 via I2C |
| 4 | Noise level (dB, relative) | Physical sensor | 30s | INMP441 via I2S |
| 5 | Train arrivals + line status + air quality | Public API | 5 min | TfL Unified API |

### Collection Period

- **Dates:** 9 March – 19 March 2026 (11 days)
- **Sensor data points:** ~30,948
- **TfL data points:** ~2,858
- **Location:** Gloucester Road, London SW7

---

## Repository Structure

```
├── firmware/
│   └── window_monitor.ino      # ESP32 Arduino sketch (sensor collection)
├── collection/
│   ├── tfl_collector.py         # Python TfL API polling script
│   └── requirements.txt         # Python dependencies
├── analysis/
│   └── analyse.py               # Data cleaning, statistics, correlation analysis
├── dashboard/
│   └── index.html               # Interactive web dashboard (single-file, offline)
├── data/
│   └── README.md                # Data format documentation
├── docs/
│   └── architecture.md          # System architecture notes
├── .gitignore
└── README.md                    # This file
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SENSING LAYER                                                  │
│                                                                 │
│  ┌──────────┐  I2C   ┌──────────────────┐  WiFi/HTTPS          │
│  │ BME280   │───────▶│ Heltec ESP32-S3  │──────────┐           │
│  └──────────┘        │ WiFi LoRa 32 V3.2│          │           │
│  ┌──────────┐  I2S   │ + OLED display   │          │           │
│  │ INMP441  │───────▶│                  │          ▼           │
│  └──────────┘        └──────────────────┘  ┌──────────────┐    │
│                                30s         │ InfluxDB     │    │
│  ┌──────────────────┐  HTTPS   5min       │ Cloud        │    │
│  │ TfL Unified API  │────────────────────▶│ (AWS EU)     │    │
│  │ - Arrivals       │                     └──────┬───────┘    │
│  │ - Line Status    │                            │             │
│  │ - Air Quality    │                       CSV Export         │
│  └──────────────────┘                            │             │
│                                                  ▼             │
│  ANALYTICS LAYER                          ┌──────────────┐    │
│                                           │ Python       │    │
│                                           │ Analysis     │    │
│                                           └──────┬───────┘    │
│                                                  │             │
│  PRESENTATION LAYER                              ▼             │
│                                           ┌──────────────┐    │
│                                           │ Web Dashboard│    │
│                                           │ (Chart.js)   │    │
│                                           └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dashboard

The dashboard is a **single HTML file** with all data embedded — no server or internet required. Open `dashboard/index.html` in any modern browser.

**Features:**
- 4 interactive tabs: Live Data, Analytics, Correlations, Transport
- Zoomable/pannable Chart.js charts with scroll-to-zoom
- Statistical summary, distribution histograms, anomaly detection
- Hypothesis testing (Welch's t-test, Cohen's d) for day vs night
- Correlation matrix heatmap and scatter plots with day/night coloring
- TfL line status badges, service summary bars, air quality gauge
- Clickable anomaly table with detail modals

**Tech:** Vanilla JS + Chart.js 4.4.7 + chartjs-plugin-zoom. No build step.

---

## Hardware

| Component | Purpose | Interface | Cost |
|-----------|---------|-----------|------|
| Heltec WiFi LoRa 32 V3.2 | MCU + WiFi + OLED | USB | (provided) |
| BME280 module (presoldered) | Temp / Humidity / Pressure | I2C (GPIO6 SDA, GPIO5 SCL) | £8 |
| INMP441 MEMS microphone | Noise level (relative dB) | I2S (GPIO48 SCK, GPIO47 WS, GPIO7 SD) | (provided) |
| Breadboard + jumper wires | Prototyping | — | £6 |

**Total cost:** ~£14

---

## Quick Start

### Sensor Node
1. Install Arduino IDE + ESP32 board support
2. Install libraries: `Adafruit BME280`, `ESP8266 Influxdb`, `Heltec ESP32 Dev-Boards`
3. Fill credentials in `firmware/window_monitor.ino`
4. Upload to Heltec board

### TfL Collector
```bash
cd collection
pip install -r requirements.txt
# Edit tfl_collector.py with your InfluxDB credentials
python tfl_collector.py
```

### Dashboard
```bash
# Just open in browser — no build needed
open dashboard/index.html
```

---

## Key Results

| Metric | Value |
|--------|-------|
| Noise–trains hourly correlation | r = 0.8685 (p < 0.001) |
| Day vs night noise difference | 75.8 vs 73.1 dB (Cohen's d = 0.44) |
| Anomalies detected | 1,499 (4.8% of readings) |
| Anomaly threshold | 87.03 dB (mean + 2σ) |
| Peak anomaly | 118.48 dB (Mar 12, construction) |
| Weekend vs weekday noise | 76.76 vs 73.94 dB |
| Temp–humidity correlation | r = −0.6465 |

---

## License

Academic coursework — Imperial College London ELEC70126, 2026.
