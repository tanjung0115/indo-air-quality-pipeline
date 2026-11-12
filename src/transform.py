"""
src/transform.py
Mengubah JSON mentah dari Open-Meteo menjadi tabel Star Schema (dim_cities & fact_air_quality),
membersihkan nilai kosong/duplikat, dan mengklasifikasikan indeks polusi udara (AQI).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

RAW_INPUT_PATH = BASE_DIR / "data" / "raw_weather_air_quality.json"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

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


def transform_weather_and_air_quality() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Membaca file JSON mentah dan menghasilkan DataFrame dim_cities & fact_air_quality."""
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

        # Ubah JSON hourly cuaca menjadi DataFrame
        w_df = pd.DataFrame(item["weather_hourly"])
        # Ubah JSON hourly polusi udara menjadi DataFrame
        aq_df = pd.DataFrame(item["air_quality_hourly"])

        # Gabungkan (JOIN) berdasarkan waktu ('time')
        merged = pd.merge(w_df, aq_df, on="time", how="inner")
        merged["city_id"] = int(c["city_id"])
        fact_dfs.append(merged)

    # 1. Buat Tabel Dimensi Kota (dim_cities)
    dim_cities = pd.DataFrame(city_rows).drop_duplicates(subset=["city_id"])

    # 2. Gabungkan seluruh data pengamatan kota menjadi Tabel Fakta (fact_air_quality)
    fact_df = pd.concat(fact_dfs, ignore_index=True)
    raw_count = len(fact_df)

    # Ganti nama kolom agar sesuai standar Data Warehouse
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

    # 3. Data Cleaning: Hapus duplikat & baris yang sensor utamanya NULL
    fact_df = fact_df.drop_duplicates(subset=["city_id", "observed_at"], keep="first")
    fact_df = fact_df.dropna(subset=["temperature_c", "us_aqi", "pm2_5"]).copy()
    cleaned_count = len(fact_df)

    # 4. Standarisasi Tipe Data & Waktu
    obs_dt = pd.to_datetime(fact_df["observed_at"])
    fact_df["observed_at"] = obs_dt.dt.strftime("%Y-%m-%d %H:%M:%S")
    fact_df["date_key"] = obs_dt.dt.strftime("%Y%m%d").astype(int)
    fact_df["hour_of_day"] = obs_dt.dt.hour

    fact_df["temperature_c"] = fact_df["temperature_c"].astype(float).round(2)
    fact_df["humidity_pct"] = fact_df["humidity_pct"].fillna(0).astype(int)
    fact_df["precipitation_mm"] = fact_df["precipitation_mm"].fillna(0.0).astype(float).round(2)
    fact_df["wind_speed_kmh"] = fact_df["wind_speed_kmh"].fillna(0.0).astype(float).round(2)
    fact_df["pm2_5"] = fact_df["pm2_5"].astype(float).round(2)
    fact_df["pm10"] = fact_df["pm10"].fillna(0.0).astype(float).round(2)
    fact_df["co_ugm3"] = fact_df["co_ugm3"].fillna(0.0).astype(float).round(2)
    fact_df["us_aqi"] = fact_df["us_aqi"].astype(int)

    # 5. Klasifikasi Kategori Udara & Flag Polusi Tinggi
    fact_df["aqi_category"] = fact_df["us_aqi"].apply(classify_aqi)
    fact_df["is_polluted"] = (fact_df["us_aqi"] > 100) | (fact_df["pm2_5"] > 35.0)

    # Susun urutan kolom Tabel Fakta
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
    fact_df = fact_df[fact_cols].sort_values(["city_id", "observed_at"]).reset_index(drop=True)

    # Simpan hasil bersih ke data/processed/
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dim_cities.to_csv(PROCESSED_DIR / "dim_cities.csv", index=False)
    fact_df.to_csv(PROCESSED_DIR / "fact_air_quality.csv", index=False)

    logger.info(
        "Transformasi selesai! Baris mentah=%d -> Baris bersih=%d (Dibuang=%d baris NULL/duplikat)",
        raw_count,
        cleaned_count,
        raw_count - cleaned_count,
    )
    logger.info("File CSV bersih disimpan di folder: %s", PROCESSED_DIR)
    return dim_cities, fact_df


if __name__ == "__main__":
    transform_weather_and_air_quality()