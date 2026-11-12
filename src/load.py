"""
src/load.py
Memuat tabel Star Schema ke PostgreSQL Data Warehouse menggunakan teknik
Incremental Upsert (ON CONFLICT DO UPDATE) agar histori data terus bertambah,
serta mencatat log eksekusi ke warehouse.etl_run_audit.
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

PROCESSED_DIR = BASE_DIR / "data" / "processed"
QUARANTINE_PATH = BASE_DIR / "data" / "quarantine" / "rejected_sensor_readings.csv"
SQL_INIT_PATH = BASE_DIR / "sql" / "init_schema.sql"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_dwh_engine():
    host = os.getenv("DWH_HOST", "localhost")
    port = os.getenv("DWH_PORT", "5434")
    db = os.getenv("DWH_DB", "air_quality_dwh")
    user = os.getenv("DWH_USER", "aq_admin")
    password = os.getenv("DWH_PASSWORD", "aq_secret_2026")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_to_warehouse() -> pd.DataFrame:
    """Incremental Upsert dim_cities & fact_air_quality ke PostgreSQL."""
    dim_cities = pd.read_csv(PROCESSED_DIR / "dim_cities.csv")
    fact_df = pd.read_csv(PROCESSED_DIR / "fact_air_quality.csv")
    quarantined_count = len(pd.read_csv(QUARANTINE_PATH)) if QUARANTINE_PATH.exists() else 0

    engine = get_dwh_engine()

    with engine.begin() as conn:
        # 1. Pastikan DDL schema, tabel, dan view terbaru sudah terpasang
        sql_script = SQL_INIT_PATH.read_text(encoding="utf-8")
        conn.execute(text(sql_script))

        # 2. Upsert dim_cities (ON CONFLICT city_id DO UPDATE)
        for _, row in dim_cities.iterrows():
            conn.execute(
                text(
                    """
                    INSERT INTO warehouse.dim_cities (city_id, city_name, province, latitude, longitude, updated_at)
                    VALUES (:city_id, :city_name, :province, :latitude, :longitude, CURRENT_TIMESTAMP)
                    ON CONFLICT (city_id) DO UPDATE SET
                        city_name = EXCLUDED.city_name,
                        province = EXCLUDED.province,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        updated_at = CURRENT_TIMESTAMP;
                    """
                ),
                row.to_dict(),
            )

        # 3. Incremental Upsert fact_air_quality (ON CONFLICT city_id, observed_at DO UPDATE)
        upsert_sql = text(
            """
            INSERT INTO warehouse.fact_air_quality (
                city_id, observed_at, date_key, hour_of_day,
                temperature_c, humidity_pct, precipitation_mm, wind_speed_kmh,
                pm2_5, pm10, co_ugm3, us_aqi, aqi_category, is_polluted, loaded_at
            )
            VALUES (
                :city_id, :observed_at, :date_key, :hour_of_day,
                :temperature_c, :humidity_pct, :precipitation_mm, :wind_speed_kmh,
                :pm2_5, :pm10, :co_ugm3, :us_aqi, :aqi_category, :is_polluted, CURRENT_TIMESTAMP
            )
            ON CONFLICT (city_id, observed_at) DO UPDATE SET
                temperature_c = EXCLUDED.temperature_c,
                humidity_pct = EXCLUDED.humidity_pct,
                precipitation_mm = EXCLUDED.precipitation_mm,
                wind_speed_kmh = EXCLUDED.wind_speed_kmh,
                pm2_5 = EXCLUDED.pm2_5,
                pm10 = EXCLUDED.pm10,
                co_ugm3 = EXCLUDED.co_ugm3,
                us_aqi = EXCLUDED.us_aqi,
                aqi_category = EXCLUDED.aqi_category,
                is_polluted = EXCLUDED.is_polluted,
                loaded_at = CURRENT_TIMESTAMP;
            """
        )
        records = fact_df.to_dict(orient="records")
        conn.execute(upsert_sql, records)

        # 4. Catat ke tabel audit warehouse.etl_run_audit
        conn.execute(
            text(
                """
                INSERT INTO warehouse.etl_run_audit (raw_rows, quarantined_rows, upserted_rows, status)
                VALUES (:raw_rows, :quarantined_rows, :upserted_rows, 'SUCCESS');
                """
            ),
            {
                "raw_rows": len(fact_df) + quarantined_count,
                "quarantined_rows": quarantined_count,
                "upserted_rows": len(fact_df),
            },
        )

    logger.info(
        "Incremental Upsert selesai! %d baris di-upsert ke warehouse.fact_air_quality (%d baris anomali dikarantina).",
        len(fact_df),
        quarantined_count,
    )

    with engine.connect() as conn:
        ranking_df = pd.read_sql("SELECT * FROM marts.mart_city_pollution_ranking;", conn)

    return ranking_df


if __name__ == "__main__":
    load_to_warehouse()