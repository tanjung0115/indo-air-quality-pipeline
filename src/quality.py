"""
src/quality.py
Menjalankan 6 pemeriksaan kualitas data (Data Quality Gate) sebelum data
dimuat ke PostgreSQL Data Warehouse, serta menyimpan laporan ke logs/dq_report.json.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOGS_DIR = BASE_DIR / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_quality_gate() -> dict:
    """Validasi kualitas data dim_cities dan fact_air_quality."""
    dim_cities = pd.read_csv(PROCESSED_DIR / "dim_cities.csv")
    fact_df = pd.read_csv(PROCESSED_DIR / "fact_air_quality.csv")

    checks = []

    def add_check(name: str, passed: bool, detail: str):
        checks.append(
            {
                "check_name": name,
                "status": "PASSED" if passed else "FAILED",
                "passed": bool(passed),
                "detail": detail,
            }
        )

    # 1. Cek keunikan Primary Key dim_cities
    pk_cities_ok = dim_cities["city_id"].is_unique and len(dim_cities) >= 8
    add_check(
        "pk_unique_dim_cities",
        pk_cities_ok,
        f"Jumlah kota unik: {dim_cities['city_id'].nunique()} (Min: 8)",
    )

    # 2. Cek keunikan Composite Key (city_id + observed_at) di fact_air_quality
    dup_count = fact_df.duplicated(subset=["city_id", "observed_at"]).sum()
    add_check(
        "no_duplicate_observations",
        dup_count == 0,
        f"Jumlah baris duplikat (city_id, observed_at): {dup_count}",
    )

    # 3. Cek tidak ada nilai NULL pada kolom sensor utama
    null_count = int(fact_df[["temperature_c", "us_aqi", "pm2_5"]].isna().sum().sum())
    add_check(
        "no_null_critical_sensors",
        null_count == 0,
        f"Total nilai NULL pada sensor utama: {null_count}",
    )

    # 4. Cek batas wajar suhu Indonesia (8°C dataran tinggi Papua s/d 45°C)
    min_temp = float(fact_df["temperature_c"].min())
    max_temp = float(fact_df["temperature_c"].max())
    temp_ok = (min_temp >= 8.0) and (max_temp <= 45.0)
    add_check(
        "valid_temperature_range_indonesia",
        temp_ok,
        f"Rentang suhu terukur: {min_temp}°C s/d {max_temp}°C",
    )

    # 5. Cek angka polusi tidak boleh negatif
    min_aqi = int(fact_df["us_aqi"].min())
    min_pm25 = float(fact_df["pm2_5"].min())
    pollution_ok = (min_aqi >= 0) and (min_pm25 >= 0.0)
    add_check(
        "non_negative_pollution_metrics",
        pollution_ok,
        f"Min US AQI: {min_aqi}, Min PM2.5: {min_pm25}",
    )

    # 6. Cek Foreign Key Integrity (fact -> dim_cities)
    orphan_cities = set(fact_df["city_id"]) - set(dim_cities["city_id"])
    add_check(
        "fk_integrity_city_id",
        len(orphan_cities) == 0,
        f"Orphan city_id: {len(orphan_cities)}",
    )

    all_passed = all(c["passed"] for c in checks)
    report = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "PASSED" if all_passed else "FAILED",
        "passed_checks": sum(1 for c in checks if c["passed"]),
        "total_checks": len(checks),
        "total_fact_rows_validated": len(fact_df),
        "checks": checks,
    }

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOGS_DIR / "dq_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    for c in checks:
        logger.info("[%s] %s -> %s", c["status"], c["check_name"], c["detail"])

    if not all_passed:
        raise ValueError("Data Quality Gate GAGAL! Cek logs/dq_report.json")

    logger.info(
        "Data Quality Gate LULUS (%d/%d checks PASSED)! Laporan disimpan di: %s",
        report["passed_checks"],
        report["total_checks"],
        report_path,
    )
    return report


if __name__ == "__main__":
    run_quality_gate()