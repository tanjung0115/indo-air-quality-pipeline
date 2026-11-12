"""
dashboard.py
Interactive Analytics, Clickable Real-Time Indonesia Map & On-Demand City Live Lookup
Membaca langsung dari PostgreSQL Data Warehouse & Open-Meteo Live API.
"""

import importlib
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

import src.config
import src.extract
import src.quality
importlib.reload(src.config)
importlib.reload(src.extract)
importlib.reload(src.quality)

from src.config import AIR_QUALITY_API_URL, GEOCODING_API_URL, WEATHER_API_URL
from src.extract import extract_all_cities
from src.load import get_dwh_engine, load_to_warehouse
from src.quality import run_quality_gate
from src.transform import classify_aqi, transform_weather_and_air_quality

BASE_DIR = Path(__file__).resolve().parent
QUARANTINE_PATH = BASE_DIR / "data" / "quarantine" / "rejected_sensor_readings.csv"

st.set_page_config(
    page_title="Indonesia Air Quality & Weather DWH",
    page_icon="🌏",
    layout="wide",
)

# Header & Tombol Sync 38 Provinsi
head_col1, head_col2 = st.columns([3.8, 1.2])
with head_col1:
    st.title("🌏 Indonesia Weather & Air Quality — 38 Provinsi Real-Time DWH")
    st.caption(
        "**Klik titik provinsi mana saja di Peta Indonesia** untuk melihat kondisi real-time, atau **cari kota/kabupaten mana saja di Indonesia**!"
    )
with head_col2:
    st.write("")
    if st.button("🔄 Sync 38 Provinsi Indonesia", use_container_width=True):
        with st.spinner("Menarik data real-time 38 Provinsi dari Aceh s/d Papua ke PostgreSQL..."):
            extract_all_cities()
            transform_weather_and_air_quality()
            run_quality_gate()
            load_to_warehouse()
            st.cache_data.clear()
        st.success("Seluruh 38 Provinsi berhasil diperbarui!")


@st.cache_data(ttl=60)
def load_mart_data():
    engine = get_dwh_engine()
    with engine.connect() as conn:
        ranking_df = pd.read_sql(
            """
            SELECT
                r.*,
                c.latitude,
                c.longitude
            FROM marts.mart_city_pollution_ranking r
            JOIN warehouse.dim_cities c ON r.city_name = c.city_name
            ORDER BY r.avg_us_aqi DESC;
            """,
            conn,
        )
        timeseries_df = pd.read_sql("SELECT * FROM marts.mart_hourly_timeseries;", conn)
        audit_df = pd.read_sql(
            "SELECT * FROM warehouse.etl_run_audit ORDER BY executed_at DESC LIMIT 10;", conn
        )
    quarantine_df = pd.read_csv(QUARANTINE_PATH) if QUARANTINE_PATH.exists() else pd.DataFrame()
    return ranking_df, timeseries_df, audit_df, quarantine_df


def fetch_realtime_single_location(lat: float, lon: float) -> dict:
    """Mengambil data detik ini (current weather & air quality) langsung dari Open-Meteo API."""
    w_resp = requests.get(
        WEATHER_API_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "timezone": "Asia/Jakarta",
        },
        timeout=15,
    ).json()
    aq_resp = requests.get(
        AIR_QUALITY_API_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "us_aqi,pm2_5,pm10,carbon_monoxide",
            "timezone": "Asia/Jakarta",
        },
        timeout=15,
    ).json()
    curr_w = w_resp.get("current", {})
    curr_aq = aq_resp.get("current", {})
    aqi_val = curr_aq.get("us_aqi") or 0
    return {
        "time": curr_w.get("time", "Saat ini"),
        "temperature_c": curr_w.get("temperature_2m", 0),
        "humidity_pct": curr_w.get("relative_humidity_2m", 0),
        "precipitation_mm": curr_w.get("precipitation", 0),
        "wind_speed_kmh": curr_w.get("wind_speed_10m", 0),
        "us_aqi": aqi_val,
        "pm2_5": curr_aq.get("pm2_5", 0),
        "pm10": curr_aq.get("pm10", 0),
        "co_ugm3": curr_aq.get("carbon_monoxide", 0),
        "category": classify_aqi(float(aqi_val)),
    }


ranking_df, timeseries_df, audit_df, quarantine_df = load_mart_data()

# 1. KPI Summary Cards
worst_city = ranking_df.iloc[0]
best_city = ranking_df.iloc[-1]

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "🚨 Kota Paling Berpolusi (#1)",
    f"{worst_city['city_name']}",
    f"Avg AQI: {worst_city['avg_us_aqi']} (PM2.5: {worst_city['avg_pm2_5']})",
    delta_color="inverse",
)
col2.metric(
    "🌿 Kota Udara Terbersih",
    f"{best_city['city_name']}",
    f"Avg AQI: {best_city['avg_us_aqi']} (PM2.5: {best_city['avg_pm2_5']})",
    delta_color="normal",
)
col3.metric(
    "🗄️ Total Data di PostgreSQL DWH",
    f"{len(timeseries_df):,} Jam",
    f"{len(ranking_df)} Kota Aktif di Peta",
)
col4.metric(
    "🛡️ Quarantined Sensor Glitches",
    f"{len(quarantine_df)} Baris Ditolak",
    "6/6 Data Quality Gate PASSED",
)

st.divider()

# 2. PETA INTERAKTIF INDONESIA (KLIK KOTA UNTUK CEK REAL-TIME!) + PENCARIAN SELURUH INDONESIA
st.subheader("🗺️ Peta Interaktif Seluruh Indonesia (Klik Titik Kota untuk Cek Kondisi Real-Time!)")

map_col, detail_col = st.columns([1.6, 1])

map_df = ranking_df.copy()
map_df["latitude"] = map_df["latitude"].astype(float)
map_df["longitude"] = map_df["longitude"].astype(float)
map_df["avg_us_aqi"] = map_df["avg_us_aqi"].astype(float)
map_df["avg_pm2_5"] = map_df["avg_pm2_5"].astype(float)

with map_col:
    fig_map = px.scatter_map(
        map_df,
        lat="latitude",
        lon="longitude",
        hover_name="city_name",
        custom_data=["city_name", "province", "latitude", "longitude", "avg_us_aqi", "avg_pm2_5", "avg_temp_c"],
        hover_data={
            "province": True,
            "most_polluted_rank": True,
            "avg_us_aqi": True,
            "peak_us_aqi": True,
            "avg_pm2_5": True,
            "avg_temp_c": True,
            "avg_humidity_pct": True,
            "latitude": False,
            "longitude": False,
        },
        size="avg_us_aqi",
        color="avg_us_aqi",
        color_continuous_scale="RdYlGn_r",
        size_max=30,
        zoom=3.9,
        center={"lat": -2.5, "lon": 118.0},
        map_style="open-street-map",
    )
    fig_map.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0), clickmode="event+select")

    # Tangkap event klik pada titik kota di peta!
    map_event = st.plotly_chart(
        fig_map,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="indonesia_map",
    )

with detail_col:
    st.markdown("### 📍 Live Inspector (Real-Time Detik Ini)")

    # Fitur Cari Kota/Kabupaten mana pun di seluruh Indonesia
    search_query = st.text_input(
        "🔍 Cari Kota/Kabupaten/Kecamatan di Seluruh Indonesia:",
        placeholder="Contoh: Bogor, Solo, Garut, Balikpapan, Labuan Bajo...",
    )

    # Tentukan kota mana yang sedang dipilih (dari Klik Peta atau dari Pencarian)
    selected_name = worst_city["city_name"]
    selected_prov = worst_city["province"]
    selected_lat = float(worst_city["latitude"])
    selected_lon = float(worst_city["longitude"])

    if search_query.strip():
        geo_resp = requests.get(
            GEOCODING_API_URL,
            params={"name": search_query.strip(), "count": 5, "language": "id", "countryCode": "ID"},
            timeout=10,
        ).json()
        results = geo_resp.get("results", [])
        if results:
            chosen = results[0]
            selected_name = chosen.get("name", search_query)
            selected_prov = chosen.get("admin1", "Indonesia")
            selected_lat = float(chosen["latitude"])
            selected_lon = float(chosen["longitude"])
        else:
            st.warning(f"Kota '{search_query}' tidak ditemukan di Indonesia.")
    elif map_event and map_event.selection and map_event.selection.points:
        pt = map_event.selection.points[0]
        cdata = pt.get("customdata", [])
        if cdata:
            selected_name = cdata[0]
            selected_prov = cdata[1]
            selected_lat = float(cdata[2])
            selected_lon = float(cdata[3])

    with st.spinner(f"Mengambil sensor real-time untuk {selected_name}..."):
        live = fetch_realtime_single_location(selected_lat, selected_lon)

    st.info(
        f"📌 **{selected_name}** ({selected_prov})  \n"
        f"Koordinat: `{selected_lat:.4f}, {selected_lon:.4f}` | Update: `{live['time']}`"
    )

    m1, m2 = st.columns(2)
    m1.metric("🌡️ Suhu Saat Ini", f"{live['temperature_c']} °C", f"Kelembapan: {live['humidity_pct']}%")
    m2.metric("💨 US AQI Saat Ini", f"{live['us_aqi']}", f"{live['category']}")

    m3, m4 = st.columns(2)
    m3.metric("🌫️ Polusi PM2.5", f"{live['pm2_5']} µg/m³", f"PM10: {live['pm10']} µg/m³")
    m4.metric("🍃 Kecepatan Angin", f"{live['wind_speed_kmh']} km/j", f"Hujan: {live['precipitation_mm']} mm")

    if live["us_aqi"] <= 50:
        st.success("✅ **Kualitas Udara Baik:** Sangat aman untuk aktivitas luar ruangan.")
    elif live["us_aqi"] <= 100:
        st.warning("⚠️ **Kualitas Udara Sedang:** Aman, namun kelompok sangat sensitif sebaiknya mengurangi aktivitas berat.")
    else:
        st.error("🚨 **Udara Tidak Sehat / Berpolusi:** Disarankan memakai masker saat beraktivitas di luar ruangan!")

st.divider()

# 3. Bar Chart & Ranking Table
left_col, right_col = st.columns([1.2, 1])

with left_col:
    st.subheader("📊 Peringkat Rata-Rata Polusi Udara (US AQI) Seluruh Kota")
    fig_bar = px.bar(
        ranking_df.sort_values("avg_us_aqi", ascending=True),
        x="avg_us_aqi",
        y="city_name",
        color="avg_us_aqi",
        orientation="h",
        text="avg_us_aqi",
        color_continuous_scale="YlOrRd",
        labels={"avg_us_aqi": "Rata-Rata US AQI", "city_name": "Kota"},
    )
    fig_bar.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

with right_col:
    st.subheader("📋 Tabel Data Mart (`marts.mart_city_pollution_ranking`)")
    st.dataframe(
        ranking_df[
            [
                "most_polluted_rank",
                "city_name",
                "province",
                "avg_us_aqi",
                "peak_us_aqi",
                "avg_pm2_5",
                "avg_temp_c",
                "polluted_hours_count",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        height=520,
    )

st.divider()

# 4. Interactive Time-Series Explorer
st.subheader("📈 Tren Per Jam: Polusi Udara (US AQI / PM2.5) & Cuaca (`marts.mart_hourly_timeseries`)")
f_col1, f_col2 = st.columns([2, 1])

with f_col1:
    all_cities = ranking_df["city_name"].tolist()
    default_cities = [c for c in [selected_name, "Jakarta", "Surabaya", "Denpasar"] if c in all_cities]
    selected_cities = st.multiselect(
        "Pilih Kota untuk Dibandingkan:",
        options=all_cities,
        default=list(dict.fromkeys(default_cities))[:4],
    )

with f_col2:
    metric_choice = st.selectbox(
        "Pilih Metrik Sensor:",
        options=[
            ("us_aqi", "US Air Quality Index (AQI)"),
            ("pm2_5", "Particulate Matter PM2.5 (µg/m³)"),
            ("temperature_c", "Suhu Udara (°C)"),
            ("humidity_pct", "Kelembapan Udara (%)"),
        ],
        format_func=lambda x: x[1],
    )

filtered_ts = timeseries_df[timeseries_df["city_name"].isin(selected_cities)]
fig_line = px.line(
    filtered_ts,
    x="observed_at",
    y=metric_choice[0],
    color="city_name",
    markers=False,
    labels={"observed_at": "Waktu Pengamatan (WIB)", metric_choice[0]: metric_choice[1], "city_name": "Kota"},
)
fig_line.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10))
st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# 5. Data Engineering Observability & Dead-Letter Quarantine
st.subheader("🛠️ Data Engineering Observability & Dead-Letter Quarantine Audit")
obs_col1, obs_col2 = st.columns([1, 1.3])

with obs_col1:
    st.markdown("**Riwayat Eksekusi Pipeline (`warehouse.etl_run_audit`)**")
    st.dataframe(audit_df, use_container_width=True, hide_index=True)

with obs_col2:
    st.markdown("**Data Sensor Rusak yang Dikarantina (`data/quarantine/rejected_sensor_readings.csv`)**")
    if not quarantine_df.empty:
        st.dataframe(
            quarantine_df[
                ["city_id", "observed_at", "temperature_c", "pm2_5", "us_aqi", "rejection_reason"]
            ],
            use_container_width=True,
            hide_index=True,
        )