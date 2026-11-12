"""
src/load.py
Memuat tabel Star Schema (dim_cities & fact_air_quality) ke PostgreSQL Data Warehouse
dan menampilkan hasil query analitik dari schema marts.
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
    """Memuat dim_cities & fact_air_quality ke PostgreSQL secara idempotent."""
    dim_cities = pd.read_csv(PROCESSED_DIR / "dim_cities.csv")
    fact_df = pd.read_csv(PROCESSED_DIR / "fact_air_quality.csv")

    engine = get_dwh_engine()

    with engine.begin() as conn:
        # Pastikan schema, tabel, dan view sudah terbentuk
        sql_script = SQL_INIT_PATH.read_text(encoding="utf-8")
        conn.execute(text(sql_script))

        # Kosongkan isi lama sebelum memuat batch terbaru (Idempotent Refresh)
        conn.execute(
            text("TRUNCATE TABLE warehouse.fact_air_quality, warehouse.dim_cities RESTART IDENTITY CASCADE;")
        )

        # Muat Dimensi & Fakta ke schema warehouse
        dim_cities.to_sql("dim_cities", conn, schema="warehouse", if_exists="append", index=False)
        fact_df.to_sql("fact_air_quality", conn, schema="warehouse", if_exists="append", index=False)

    logger.info(
        "Berhasil memuat %d baris ke warehouse.dim_cities dan %d baris ke warehouse.fact_air_quality!",
        len(dim_cities),
        len(fact_df),
    )

    # Query hasil analitik dari Data Mart
    with engine.connect() as conn:
        ranking_df = pd.read_sql("SELECT * FROM marts.mart_city_pollution_ranking;", conn)

    print("\n=== PERINGKAT KUALITAS UDARA & CUACA KOTA INDONESIA (72 JAM TERAKHIR) ===")
    print(ranking_df.to_string(index=False))
    print("=========================================================================\n")
    return ranking_df


if __name__ == "__main__":
    load_to_warehouse()