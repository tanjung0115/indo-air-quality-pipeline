"""
run_pipeline.py
Entrypoint utama untuk menjalankan End-to-End Weather & Air Quality ETL Pipeline.
"""

import logging
import time

from src.extract import extract_all_cities
from src.load import load_to_warehouse
from src.quality import run_quality_gate
from src.transform import transform_weather_and_air_quality

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    t0 = time.perf_counter()
    logger.info("==============================================================")
    logger.info("STARTING INDONESIA WEATHER & AIR QUALITY DATA PIPELINE")
    logger.info("==============================================================")

    # Step 1: Extract dari Open-Meteo Public API
    extract_all_cities()

    # Step 2: Transform & Clean menjadi Star Schema
    transform_weather_and_air_quality()

    # Step 3: Jalankan Data Quality Gate (6 Assertions)
    run_quality_gate()

    # Step 4: Load ke PostgreSQL Data Warehouse & Tampilkan Data Mart
    load_to_warehouse()

    elapsed = round(time.perf_counter() - t0, 2)
    logger.info("Pipeline selesai secara menyeluruh dalam %s detik!", elapsed)


if __name__ == "__main__":
    main()