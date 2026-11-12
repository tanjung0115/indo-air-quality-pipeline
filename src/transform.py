"""
src/transform.py
Mengubah JSON mentah dari Open-Meteo menjadi tabel Star Schema (dim_cities & fact_air_quality),
mendeteksi anomali sensor IoT ke Dead-Letter Quarantine (rejected_sensor_readings.csv),
dan mengklasifikasikan indeks polusi udara (AQI).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

RAW_INPUT_PATH = BASE_DIR / "data" / "raw_weather_air_quality.json"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
QUARANTINE_DIR = BASE_DIR / "data" / "quarantine"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def classify_aqi(aqi_val: float) -> str:
    """Mengelompokkan angka US AQI menjadi kategori kesehatan udara."""
    if aqi_val <= 50:
        return "Baik (Good)"
    elif aqi_val <= 100:
        return "Sedang (Moderate)"
    elif aqi_val <= 150:
        return "Tidak Sehat bagi Sensitif"
    elif aqi_val <= 200:
        return "Tidak Sehat (Unhealthy)"
    else:
        return "Sangat Tidak Sehat"


def inject_simulated_sensor_glitches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menyuntikkan 4 baris simulasi gangguan sensor IoT (overheat, negatif PM2.5,
    missing AQI, dan duplikat webhook) untuk menguji sistem Dead-Letter Quarantine.
    """
    glitches = pd.DataFrame(
        [
            {
                "city_id": 1,
                "observed_at": "2026-11-11T12:00",
                "temperature_c": 88.5,  # Sensor overheat (> 45°C)
                "humidity_pct": 70,
                "precipitation_mm": 0.0,
                "wind_speed_kmh": 10.0,
                "pm10": 45.0,
                "pm2_5": 30.0,
                "co_ugm3": 400.0,
                "us_aqi": 90,
            },
            {
                "city_id": 2,
                "observed_at": "2026-11-11T13:00",
                "temperature_c": 30.0,
                "humidity_pct": 65,
                "precipitation_mm": 0.0,
                "wind_speed_kmh": 12.0,
                "pm10": 20.0,
                "pm2_5": -15.4,  # Glitch sensor PM2.5 negatif (< 0)
                "co_ugm3": 300.0,
                "us_aqi": 60,
            },
            {
                "city_id": 3,
                "observed_at": "2026-11-11T14:00",
                "temperature_c": 24.5,
                "humidity_pct": 80,
                "precipitation_mm": 2.1,
                "wind_speed_kmh": 8.0,
                "pm10": None,
                "pm2_5": None,  # Sensor mati / nilai NULL
                "co_ugm3": 250.0,
                "us_aqi": None,
            },
            # Duplikat persis dari baris pertama
            df.iloc[0].to_dict(),
        ]
    )
    return pd.concat([df, glitches], ignore_index=True)


def transform_weather_and_air_quality() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Membaca file JSON mentah, memisahkan sensor korup ke Quarantine, dan menyimpan CSV bersih."""
    if not RAW_INPUT_PATH.exists():
        raise FileNotFoundError(f"File mentah belum ada: {RAW_INPUT_PATH}. Jalankan extract.py dulu!")

    with open(RAW_INPUT_PATH, "r", encoding="utf-8") as f:
        raw_payloads = json.load(f)

    city_rows = []
    fact_dfs = []

    for item in raw_payloads:
        c = item["city_info"]
        city_rows.append(
            {
                "city_id": int(c["city_id"]),
                "city_name": c["city_name"].strip(),
                "province": c["province"].strip(),
                "latitude": float(c["latitude"]),
                "longitude": float(c["longitude"]),
            }
        )

        w_df = pd.DataFrame(item["weather_hourly"])
        aq_df = pd.DataFrame(item["air_quality_hourly"])
        merged = pd.merge(w_df, aq_df, on="time", how="inner")
        merged["city_id"] = int(c["city_id"])
        fact_dfs.append(merged)

    dim_cities = pd.DataFrame(city_rows).drop_duplicates(subset=["city_id"])

    fact_df = pd.concat(fact_dfs, ignore_index=True)
    fact_df = fact_df.rename(
        columns={
            "time": "observed_at",
            "temperature_2m": "temperature_c",
            "relative_humidity_2m": "humidity_pct",
            "precipitation": "precipitation_mm",
            "wind_speed_10m": "wind_speed_kmh",
            "carbon_monoxide": "co_ugm3",
        }
    )

    # Suntikkan 4 anomali sensor untuk menguji ketangguhan Quarantine
    fact_df = inject_simulated_sensor_glitches(fact_df)
    raw_count = len(fact_df)

    # Standarisasi format waktu terlebih dahulu agar deteksi duplikat akurat
    obs_dt = pd.to_datetime(fact_df["observed_at"])
    fact_df["observed_at"] = obs_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    fact_df["date_key"] = obs_dt.dt.strftime("%Y%m%d").astype(int)
    fact_df["hour_of_day"] = obs_dt.dt.hour

    # Evaluasi setiap baris untuk mendeteksi duplikat atau kerusakan sensor
    is_dup = fact_df.duplicated(subset=["city_id", "observed_at"], keep="first")
    reasons = []
    for idx, row in fact_df.iterrows():
        r = []
        if is_dup.iloc[idx]:
            r.append("DUPLICATE_CITY_TIMESTAMP")
        if pd.isna(row["temperature_c"]) or pd.isna(row["us_aqi"]) or pd.isna(row["pm2_5"]):
            r.append("NULL_CRITICAL_SENSOR")
        else:
            if not (8.0 <= float(row["temperature_c"]) <= 45.0):
                r.append("SENSOR_OVERHEAT_OR_INVALID_TEMP")
            if float(row["pm2_5"]) < 0.0:
                r.append("NEGATIVE_PM25_GLITCH")
            if not (0 <= float(row["us_aqi"]) <= 500):
                r.append("INVALID_AQI_RANGE")
        reasons.append("|".join(r))

    fact_df["rejection_reason"] = reasons

    # Pisahkan data rusak ke Quarantine & data bersih ke Warehouse
    quarantined_df = fact_df[fact_df["rejection_reason"] != ""].copy()
    clean_df = fact_df[fact_df["rejection_reason"] == ""].copy()

    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    quarantined_df.to_csv(QUARANTINE_DIR / "rejected_sensor_readings.csv", index=False)

    # Format tipe data pada baris yang sudah bersih
    clean_df["temperature_c"] = clean_df["temperature_c"].astype(float).round(2)
    clean_df["humidity_pct"] = clean_df["humidity_pct"].fillna(0).astype(int)
    clean_df["precipitation_mm"] = clean_df["precipitation_mm"].fillna(0.0).astype(float).round(2)
    clean_df["wind_speed_kmh"] = clean_df["wind_speed_kmh"].fillna(0.0).astype(float).round(2)
    clean_df["pm2_5"] = clean_df["pm2_5"].astype(float).round(2)
    clean_df["pm10"] = clean_df["pm10"].fillna(0.0).astype(float).round(2)
    clean_df["co_ugm3"] = clean_df["co_ugm3"].fillna(0.0).astype(float).round(2)
    clean_df["us_aqi"] = clean_df["us_aqi"].astype(int)

    clean_df["aqi_category"] = clean_df["us_aqi"].apply(classify_aqi)
    clean_df["is_polluted"] = (clean_df["us_aqi"] > 100) | (clean_df["pm2_5"] > 35.0)

    fact_cols = [
        "city_id",
        "observed_at",
        "date_key",
        "hour_of_day",
        "temperature_c",
        "humidity_pct",
        "precipitation_mm",
        "wind_speed_kmh",
        "pm2_5",
        "pm10",
        "co_ugm3",
        "us_aqi",
        "aqi_category",
        "is_polluted",
    ]
    clean_df = clean_df[fact_cols].sort_values(["city_id", "observed_at"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dim_cities.to_csv(PROCESSED_DIR / "dim_cities.csv", index=False)
    clean_df.to_csv(PROCESSED_DIR / "fact_air_quality.csv", index=False)

    logger.info(
        "Transformasi selesai! Raw=%d -> Clean=%d | Dikarantina=%d baris (lihat data/quarantine/rejected_sensor_readings.csv)",
        raw_count,
        len(clean_df),
        len(quarantined_df),
    )
    return dim_cities, clean_df


if __name__ == "__main__":
    transform_weather_and_air_quality()