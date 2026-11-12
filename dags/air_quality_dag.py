"""
dags/air_quality_dag.py
Apache Airflow DAG untuk mengorkestrasi Indonesia Weather & Air Quality Pipeline secara terjadwal.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Pastikan folder project terbaca di dalam container Airflow
PROJECT_ROOT = Path("/opt/airflow/project")
if PROJECT_ROOT.exists() and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    local_root = Path(__file__).resolve().parent.parent
    if str(local_root) not in sys.path:
        sys.path.insert(0, str(local_root))

from src.extract import extract_all_cities
from src.load import load_to_warehouse
from src.quality import run_quality_gate
from src.transform import transform_weather_and_air_quality

default_args = {
    "owner": "data_engineer_indonesia",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


def task_extract():
    path = extract_all_cities()
    return str(path)


def task_transform():
    dim_cities, fact_df = transform_weather_and_air_quality()
    return {"cities_count": len(dim_cities), "fact_rows": len(fact_df)}


def task_quality():
    report = run_quality_gate()
    return report["overall_status"]


def task_load():
    ranking_df = load_to_warehouse()
    top_polluted_city = ranking_df.iloc[0]["city_name"]
    return {"top_polluted_city": top_polluted_city, "cities_ranked": len(ranking_df)}


with DAG(
    dag_id="indo_air_quality_monitoring_dag",
    default_args=default_args,
    description="Automated Weather & Air Quality ETL Pipeline for 8 Indonesian Cities",
    schedule="0 */6 * * *",  # Jalan otomatis setiap 6 jam
    start_date=datetime(2026, 11, 1),
    catchup=False,
    tags=["indonesia", "air-quality", "open-meteo-api", "star-schema"],
) as dag:

    t1_extract = PythonOperator(
        task_id="extract_open_meteo_api",
        python_callable=task_extract,
    )

    t2_transform = PythonOperator(
        task_id="transform_weather_and_aqi",
        python_callable=task_transform,
    )

    t3_quality = PythonOperator(
        task_id="run_data_quality_gate",
        python_callable=task_quality,
    )

    t4_load = PythonOperator(
        task_id="load_postgres_star_schema",
        python_callable=task_load,
    )

    t1_extract >> t2_transform >> t3_quality >> t4_load