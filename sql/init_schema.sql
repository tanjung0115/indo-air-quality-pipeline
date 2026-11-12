-- ============================================================================
-- sql/init_schema.sql
-- Star Schema & Analytical Data Marts untuk Indonesia Air Quality Warehouse
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS marts;

-- 1. Tabel Dimensi Kota (warehouse.dim_cities)
CREATE TABLE IF NOT EXISTS warehouse.dim_cities (
    city_id INTEGER PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    latitude NUMERIC(9, 4) NOT NULL,
    longitude NUMERIC(9, 4) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabel Fakta Pengamatan Cuaca & Polusi (warehouse.fact_air_quality)
CREATE TABLE IF NOT EXISTS warehouse.fact_air_quality (
    observation_id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES warehouse.dim_cities(city_id),
    observed_at TIMESTAMP NOT NULL,
    date_key INTEGER NOT NULL,
    hour_of_day INTEGER NOT NULL,
    temperature_c NUMERIC(5, 2) NOT NULL,
    humidity_pct INTEGER NOT NULL,
    precipitation_mm NUMERIC(6, 2) NOT NULL,
    wind_speed_kmh NUMERIC(6, 2) NOT NULL,
    pm2_5 NUMERIC(7, 2) NOT NULL,
    pm10 NUMERIC(7, 2) NOT NULL,
    co_ugm3 NUMERIC(8, 2) NOT NULL,
    us_aqi INTEGER NOT NULL,
    aqi_category VARCHAR(60) NOT NULL,
    is_polluted BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_fact_aq_city_date ON warehouse.fact_air_quality(city_id, date_key);

-- 3. Data Mart 1: Peringkat Kualitas Udara & Cuaca Kota Indonesia
CREATE OR REPLACE VIEW marts.mart_city_pollution_ranking AS
SELECT
    c.city_name,
    c.province,
    COUNT(f.observation_id) AS total_hours_monitored,
    ROUND(AVG(f.us_aqi), 1) AS avg_us_aqi,
    MAX(f.us_aqi) AS peak_us_aqi,
    ROUND(AVG(f.pm2_5), 2) AS avg_pm2_5,
    ROUND(AVG(f.temperature_c), 1) AS avg_temp_c,
    ROUND(AVG(f.humidity_pct), 0) AS avg_humidity_pct,
    SUM(CASE WHEN f.is_polluted THEN 1 ELSE 0 END) AS polluted_hours_count,
    RANK() OVER (ORDER BY AVG(f.us_aqi) DESC) AS most_polluted_rank
FROM warehouse.dim_cities c
JOIN warehouse.fact_air_quality f ON c.city_id = f.city_id
GROUP BY c.city_id, c.city_name, c.province
ORDER BY avg_us_aqi DESC;

-- 4. Data Mart 2: Ringkasan Harian per Kota
CREATE OR REPLACE VIEW marts.mart_daily_city_summary AS
SELECT
    c.city_name,
    DATE(f.observed_at) AS observation_date,
    ROUND(AVG(f.temperature_c), 1) AS avg_temp_c,
    SUM(f.precipitation_mm) AS total_rain_mm,
    ROUND(AVG(f.pm2_5), 2) AS avg_pm2_5,
    ROUND(AVG(f.us_aqi), 1) AS avg_us_aqi,
    MAX(f.us_aqi) AS max_us_aqi
FROM warehouse.fact_air_quality f
JOIN warehouse.dim_cities c ON f.city_id = c.city_id
GROUP BY c.city_name, DATE(f.observed_at)
ORDER BY observation_date DESC, avg_us_aqi DESC;

-- 5. Tabel Audit History Eksekusi Pipeline (Observability)
CREATE TABLE IF NOT EXISTS warehouse.etl_run_audit (
    run_id SERIAL PRIMARY KEY,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_rows INTEGER NOT NULL,
    quarantined_rows INTEGER NOT NULL,
    upserted_rows INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL
);

-- 6. Data Mart 3: Time-Series Per Jam (Untuk Grafik Interaktif di Dashboard)
CREATE OR REPLACE VIEW marts.mart_hourly_timeseries AS
SELECT
    f.observed_at,
    c.city_name,
    c.province,
    f.temperature_c,
    f.humidity_pct,
    f.precipitation_mm,
    f.wind_speed_kmh,
    f.pm2_5,
    f.pm10,
    f.co_ugm3,
    f.us_aqi,
    f.aqi_category,
    f.is_polluted
FROM warehouse.fact_air_quality f
JOIN warehouse.dim_cities c ON f.city_id = c.city_id
ORDER BY f.observed_at ASC, c.city_name ASC;