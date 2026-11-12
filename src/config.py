"""
src/config.py
Konfigurasi Lengkap 38 Provinsi di Seluruh Indonesia (Ibu Kota Provinsi Resmi,
termasuk 4 Daerah Otonomi Baru di Pulau Papua) beserta endpoint Open-Meteo API.
"""

CITIES = [
    # === PULAU SUMATERA (10 Provinsi) ===
    {"city_id": 1, "city_name": "Banda Aceh", "province": "Aceh", "latitude": 5.5483, "longitude": 95.3238},
    {"city_id": 2, "city_name": "Medan", "province": "Sumatera Utara", "latitude": 3.5952, "longitude": 98.6722},
    {"city_id": 3, "city_name": "Padang", "province": "Sumatera Barat", "latitude": -0.9471, "longitude": 100.4172},
    {"city_id": 4, "city_name": "Pekanbaru", "province": "Riau", "latitude": 0.5071, "longitude": 101.4478},
    {"city_id": 5, "city_name": "Tanjungpinang", "province": "Kepulauan Riau", "latitude": 0.9186, "longitude": 104.4467},
    {"city_id": 6, "city_name": "Jambi", "province": "Jambi", "latitude": -1.6101, "longitude": 103.6131},
    {"city_id": 7, "city_name": "Palembang", "province": "Sumatera Selatan", "latitude": -2.9761, "longitude": 104.7754},
    {"city_id": 8, "city_name": "Pangkalpinang", "province": "Kepulauan Bangka Belitung", "latitude": -2.1316, "longitude": 106.1169},
    {"city_id": 9, "city_name": "Bengkulu", "province": "Bengkulu", "latitude": -3.7928, "longitude": 102.2608},
    {"city_id": 10, "city_name": "Bandar Lampung", "province": "Lampung", "latitude": -5.4292, "longitude": 105.2610},

    # === PULAU JAWA (6 Provinsi) ===
    {"city_id": 11, "city_name": "Serang", "province": "Banten", "latitude": -6.1104, "longitude": 106.1630},
    {"city_id": 12, "city_name": "Jakarta", "province": "DKI Jakarta", "latitude": -6.2088, "longitude": 106.8456},
    {"city_id": 13, "city_name": "Bandung", "province": "Jawa Barat", "latitude": -6.9175, "longitude": 107.6191},
    {"city_id": 14, "city_name": "Semarang", "province": "Jawa Tengah", "latitude": -6.9667, "longitude": 110.4167},
    {"city_id": 15, "city_name": "Yogyakarta", "province": "DI Yogyakarta", "latitude": -7.7956, "longitude": 110.3695},
    {"city_id": 16, "city_name": "Surabaya", "province": "Jawa Timur", "latitude": -7.2575, "longitude": 112.7521},

    # === BALI & NUSA TENGGARA (3 Provinsi) ===
    {"city_id": 17, "city_name": "Denpasar", "province": "Bali", "latitude": -8.6705, "longitude": 115.2126},
    {"city_id": 18, "city_name": "Mataram", "province": "Nusa Tenggara Barat", "latitude": -8.5833, "longitude": 116.1167},
    {"city_id": 19, "city_name": "Kupang", "province": "Nusa Tenggara Timur", "latitude": -10.1772, "longitude": 123.6070},

    # === PULAU KALIMANTAN (5 Provinsi) ===
    {"city_id": 20, "city_name": "Pontianak", "province": "Kalimantan Barat", "latitude": -0.0263, "longitude": 109.3425},
    {"city_id": 21, "city_name": "Palangka Raya", "province": "Kalimantan Tengah", "latitude": -2.2136, "longitude": 113.9108},
    {"city_id": 22, "city_name": "Banjarbaru", "province": "Kalimantan Selatan", "latitude": -3.4420, "longitude": 114.8321},
    {"city_id": 23, "city_name": "Samarinda", "province": "Kalimantan Timur", "latitude": -0.5022, "longitude": 117.1536},
    {"city_id": 24, "city_name": "Tanjung Selor", "province": "Kalimantan Utara", "latitude": 2.8375, "longitude": 117.3653},

    # === PULAU SULAWESI (6 Provinsi) ===
    {"city_id": 25, "city_name": "Manado", "province": "Sulawesi Utara", "latitude": 1.4748, "longitude": 124.8421},
    {"city_id": 26, "city_name": "Gorontalo", "province": "Gorontalo", "latitude": 0.5435, "longitude": 123.0568},
    {"city_id": 27, "city_name": "Palu", "province": "Sulawesi Tengah", "latitude": -0.8917, "longitude": 119.8707},
    {"city_id": 28, "city_name": "Mamuju", "province": "Sulawesi Barat", "latitude": -2.6748, "longitude": 118.8885},
    {"city_id": 29, "city_name": "Makassar", "province": "Sulawesi Selatan", "latitude": -5.1477, "longitude": 119.4327},
    {"city_id": 30, "city_name": "Kendari", "province": "Sulawesi Tenggara", "latitude": -3.9985, "longitude": 122.5130},

    # === KEPULAUAN MALUKU (2 Provinsi) ===
    {"city_id": 31, "city_name": "Ambon", "province": "Maluku", "latitude": -3.6954, "longitude": 128.1814},
    {"city_id": 32, "city_name": "Sofifi", "province": "Maluku Utara", "latitude": 0.7373, "longitude": 127.5588},

    # === PULAU PAPUA (6 Provinsi Lengkap) ===
    {"city_id": 33, "city_name": "Manokwari", "province": "Papua Barat", "latitude": -0.8615, "longitude": 134.0620},
    {"city_id": 34, "city_name": "Sorong", "province": "Papua Barat Daya", "latitude": -0.8762, "longitude": 131.2558},
    {"city_id": 35, "city_name": "Jayapura", "province": "Papua", "latitude": -2.5337, "longitude": 140.7181},
    {"city_id": 36, "city_name": "Nabire", "province": "Papua Tengah", "latitude": -3.3638, "longitude": 135.4960},
    {"city_id": 37, "city_name": "Wamena", "province": "Papua Pegunungan", "latitude": -4.0977, "longitude": 138.9525},
    {"city_id": 38, "city_name": "Merauke", "province": "Papua Selatan", "latitude": -8.4932, "longitude": 140.4018},
]

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
