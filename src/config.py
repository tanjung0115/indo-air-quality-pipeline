"""
src/config.py
Konfigurasi daftar kota Indonesia & endpoint Open-Meteo API
"""

CITIES = [
    {"city_id": 1, "city_name": "Jakarta", "province": "DKI Jakarta", "latitude": -6.2088, "longitude": 106.8456},
    {"city_id": 2, "city_name": "Surabaya", "province": "Jawa Timur", "latitude": -7.2575, "longitude": 112.7521},
    {"city_id": 3, "city_name": "Bandung", "province": "Jawa Barat", "latitude": -6.9175, "longitude": 107.6191},
    {"city_id": 4, "city_name": "Medan", "province": "Sumatera Utara", "latitude": 3.5952, "longitude": 98.6722},
    {"city_id": 5, "city_name": "Semarang", "province": "Jawa Tengah", "latitude": -6.9667, "longitude": 110.4167},
    {"city_id": 6, "city_name": "Makassar", "province": "Sulawesi Selatan", "latitude": -5.1477, "longitude": 119.4327},
    {"city_id": 7, "city_name": "Palembang", "province": "Sumatera Selatan", "latitude": -2.9761, "longitude": 104.7754},
    {"city_id": 8, "city_name": "Denpasar", "province": "Bali", "latitude": -8.6705, "longitude": 115.2126},
]

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"