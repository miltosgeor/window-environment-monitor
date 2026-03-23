/*
 * Smart Window Environment Monitor - Data Collection
 * Board: Heltec WiFi LoRa 32 V3.2
 * ELEC70126 IoT Coursework — Imperial College London 2026
 *
 * Sensors:
 *   1. BME280 (Temp/Humidity/Pressure) via I2C on GPIO6(SDA), GPIO5(SCL)
 *   2. INMP441 (I2S Microphone) on GPIO48(SCK), GPIO47(WS), GPIO7(SD)
 *
 * Data Pipeline:
 *   ESP32 → WiFi → InfluxDB Cloud (HTTPS)
 *   Sampling: every 30 seconds
 *
 * Libraries required:
 *   - Adafruit BME280 (+ dependencies)
 *   - ESP8266 Influxdb by Tobias Schürg
 *   - Heltec ESP32 Dev-Boards
 */

#include <Wire.h>
#include <WiFi.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <InfluxDbClient.h>
#include <InfluxDbCloud.h>
#include "HT_SSD1306Wire.h"
#include <driver/i2s.h>

// ============================================================
//  CREDENTIALS (redacted for submission — fill before use)
// ============================================================
#define WIFI_SSID     "REDACTED"
#define WIFI_PASSWORD "REDACTED"

#define INFLUXDB_URL    "https://eu-central-1-1.aws.cloud2.influxdata.com"
#define INFLUXDB_TOKEN  "REDACTED"
#define INFLUXDB_ORG    "REDACTED"
#define INFLUXDB_BUCKET "window_monitor"

#define TZ_INFO "GMT0BST,M3.5.0/1,M10.5.0"

// ========== OLED ==========
SSD1306Wire oled(0x3c, 500000, SDA_OLED, SCL_OLED, GEOMETRY_128_64, RST_OLED);

// ========== BME280 ==========
#define BME_SDA 6
#define BME_SCL 5
TwoWire BME_I2C = TwoWire(1);
Adafruit_BME280 bme;
bool bmeFound = false;

// ========== INMP441 I2S ==========
#define I2S_SCK  48
#define I2S_WS   47
#define I2S_SD    7
#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000
#define SAMPLE_BITS 32
#define SAMPLES 1024

// ========== InfluxDB ==========
InfluxDBClient influxClient(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN, InfluxDbCloud2CACert);
Point sensorData("environment");

// ========== State ==========
float temperature = 0, humidity = 0, pressure = 0, noiseLevel = 0;
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 30000; // 30 seconds
unsigned long totalSent = 0, totalFailed = 0;

// ========== I2S Init ==========
void setupI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)SAMPLE_BITS,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = SAMPLES
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT);
}

// ========== Noise Measurement ==========
float readNoiseLevel() {
  int32_t samples[SAMPLES];
  size_t bytesRead;
  i2s_read(I2S_PORT, &samples, sizeof(samples), &bytesRead, portMAX_DELAY);
  int count = bytesRead / sizeof(int32_t);
  if (count == 0) return -1;

  double sumSq = 0;
  for (int i = 0; i < count; i++) {
    double sample = (double)(samples[i] >> 8); // 24-bit effective
    sumSq += sample * sample;
  }
  double rms = sqrt(sumSq / count);
  if (rms < 1) rms = 1;

  // Convert to relative dB (uncalibrated)
  float dB = 20.0 * log10(rms);
  return constrain(dB, 0, 130);
}

// ========== WiFi ==========
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  oled.clear();
  oled.drawString(0, 0, "Connecting WiFi...");
  oled.display();

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected: " + WiFi.localIP().toString());
  }
}

// ========== OLED Display ==========
void updateDisplay() {
  oled.clear();
  oled.setFont(ArialMT_Plain_10);

  oled.drawString(0, 0, "Window Monitor");
  oled.drawString(80, 0, "TX:" + String(totalSent));

  if (bmeFound) {
    oled.drawString(0, 14, "T:" + String(temperature, 1) + "C");
    oled.drawString(64, 14, "H:" + String(humidity, 1) + "%");
    oled.drawString(0, 28, "P:" + String(pressure, 0) + "hPa");
  }
  oled.drawString(0, 42, "Noise:" + String(noiseLevel, 1) + "dB");
  oled.drawString(0, 54, "RSSI:" + String(WiFi.RSSI()) + "dBm");
  oled.display();
}

// ========== Setup ==========
void setup() {
  Serial.begin(115200);

  // OLED
  oled.init();
  oled.setFont(ArialMT_Plain_10);

  // BME280
  BME_I2C.begin(BME_SDA, BME_SCL);
  bmeFound = bme.begin(0x76, &BME_I2C);
  if (!bmeFound) bmeFound = bme.begin(0x77, &BME_I2C);
  Serial.println(bmeFound ? "BME280 found" : "BME280 NOT found");

  // I2S Mic
  setupI2S();

  // WiFi
  connectWiFi();

  // Time sync (required for InfluxDB Cloud TLS)
  timeSync(TZ_INFO, "pool.ntp.org", "time.nis.gov");

  // Verify InfluxDB
  if (influxClient.validateConnection()) {
    Serial.println("InfluxDB connected: " + String(influxClient.getServerUrl()));
  } else {
    Serial.println("InfluxDB FAILED: " + String(influxClient.getLastErrorMessage()));
  }

  // Tags
  sensorData.addTag("device", "heltec_v3");
  sensorData.addTag("location", "window");
}

// ========== Loop ==========
void loop() {
  // Reconnect WiFi if needed
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  // Read sensors
  if (bmeFound) {
    temperature = bme.readTemperature();
    humidity = bme.readHumidity();
    pressure = bme.readPressure() / 100.0F;
  }
  noiseLevel = readNoiseLevel();

  updateDisplay();

  // Send to InfluxDB every 30s
  if (millis() - lastSendTime >= sendInterval) {
    lastSendTime = millis();

    sensorData.clearFields();
    sensorData.addField("temperature", (float)temperature);
    sensorData.addField("humidity", (float)humidity);
    sensorData.addField("pressure", (float)pressure);
    sensorData.addField("noise_db", (float)noiseLevel);
    sensorData.addField("wifi_rssi", (float)WiFi.RSSI());

    if (influxClient.writePoint(sensorData)) {
      totalSent++;
      Serial.println("TX #" + String(totalSent) + " OK");
    } else {
      totalFailed++;
      Serial.println("TX FAIL: " + String(influxClient.getLastErrorMessage()));
    }
  }

  delay(2000);
}
