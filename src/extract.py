"""
src/extract.py
Mengambil data cuaca & kualitas udara dari Open-Meteo API untuk seluruh 38 Provinsi Indonesia.
Dilengkapi Parallel ThreadPoolExecutor, HTTP Auto-Retry (Exponential Backoff) & Raw Cache Fallback.
"""

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import AIR_QUALITY_API_URL, CITIES, WEATHER_API_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_OUTPUT_PATH = BASE_DIR / "data" / "raw_weather_air_quality.json"


def create_retry_session() -> requests.Session:
    """Membuat HTTP Session dengan fitur otomatis retry 3x jika terjadi Timeout."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=16, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_city_data(session: requests.Session, city: dict) -> dict:
    """Mengambil data Weather API dan Air Quality API untuk 1 ibu kota provinsi."""
    lat = city["latitude"]
    lon = city["longitude"]

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "past_days": 2,
        "forecast_days": 1,
        "timezone": "Asia/Jakarta",
    }
    weather_resp = session.get(WEATHER_API_URL, params=weather_params, timeout=30)
    weather_resp.raise_for_status()

    aq_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm10,pm2_5,carbon_monoxide,us_aqi",
        "past_days": 2,
        "forecast_days": 1,
        "timezone": "Asia/Jakarta",
    }
    aq_resp = session.get(AIR_QUALITY_API_URL, params=aq_params, timeout=30)
    aq_resp.raise_for_status()

    return {
        "city_info": city,
        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "weather_hourly": weather_resp.json().get("hourly", {}),
        "air_quality_hourly": aq_resp.json().get("hourly", {}),
    }


def extract_all_cities() -> Path:
    """Ekstraksi paralel seluruh 38 Provinsi Indonesia dengan ThreadPoolExecutor & Auto-Retry."""
    logger.info("Memulai ekstraksi paralel Open-Meteo API untuk %d Provinsi Indonesia...", len(CITIES))
    session = create_retry_session()
    all_payloads = []

    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_city = {
                executor.submit(fetch_city_data, session, city): city for city in CITIES
            }
            for future in as_completed(future_to_city):
                city = future_to_city[future]
                city_payload = future.result()
                all_payloads.append(city_payload)
                logger.info("-> Selesai: %s (%s)", city["city_name"], city["province"])

        # Urutkan kembali berdasarkan city_id
        all_payloads.sort(key=lambda x: x["city_info"]["city_id"])

        RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RAW_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(all_payloads, f, indent=2)

        logger.info("Selesai! Data 38 Provinsi disimpan di: %s", RAW_OUTPUT_PATH)
    except Exception as exc:
        if RAW_OUTPUT_PATH.exists():
            logger.warning(
                "API mengalami gangguan (%s). Menggunakan cache data mentah di: %s",
                type(exc).__name__,
                RAW_OUTPUT_PATH,
            )
        else:
            raise

    return RAW_OUTPUT_PATH


if __name__ == "__main__":
    extract_all_cities()
