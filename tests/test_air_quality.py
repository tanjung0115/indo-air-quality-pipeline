"""
tests/test_air_quality.py
Unit & Integration Tests untuk Indonesia Weather & Air Quality Pipeline.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import CITIES
from src.quality import run_quality_gate
from src.transform import classify_aqi, transform_weather_and_air_quality


def test_classify_aqi_categories():
    """Pastikan batas kategori indeks kualitas udara (US AQI) akurat."""
    assert classify_aqi(25) == "Baik (Good)"
    assert classify_aqi(50) == "Baik (Good)"
    assert classify_aqi(75) == "Sedang (Moderate)"
    assert classify_aqi(125) == "Tidak Sehat bagi Sensitif"
    assert classify_aqi(175) == "Tidak Sehat (Unhealthy)"
    assert classify_aqi(250) == "Sangat Tidak Sehat"


def test_cities_configuration_bounds():
    """Pastikan ada 8 kota dan seluruh koordinatnya berada di wilayah Indonesia."""
    assert len(CITIES) == 8
    city_ids = [c["city_id"] for c in CITIES]
    assert len(set(city_ids)) == 8  # Semua city_id harus unik

    for city in CITIES:
        assert -11.5 <= city["latitude"] <= 6.5, f"Latitude {city['city_name']} di luar Indonesia"
        assert 95.0 <= city["longitude"] <= 141.5, f"Longitude {city['city_name']} di luar Indonesia"


def test_transform_and_quality_gate_integration():
    """Pastikan transformasi JSON dan Data Quality Gate berjalan dan PASSED."""
    dim_cities, fact_df = transform_weather_and_air_quality()

    assert len(dim_cities) == 8
    assert len(fact_df) > 0
    assert fact_df["us_aqi"].isna().sum() == 0
    assert "aqi_category" in fact_df.columns
    assert "is_polluted" in fact_df.columns

    dq_report = run_quality_gate()
    assert dq_report["overall_status"] == "PASSED"
    assert dq_report["passed_checks"] == 6