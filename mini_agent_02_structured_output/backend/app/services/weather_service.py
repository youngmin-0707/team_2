from datetime import date

import httpx

from app.config import settings


WEATHER_CODES = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분적으로 흐림",
    3: "흐림",
    45: "안개",
    51: "약한 이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    80: "소나기",
    81: "소나기",
    82: "강한 소나기",
    95: "뇌우",
}


# Open-Meteo geocoding is more reliable with the official English city name.
CITY_GEOCODING_NAMES = {
    "서울": "Seoul",
    "부산": "Busan",
    "제주": "Jeju City",
    "강릉": "Gangneung",
    "대구": "Daegu",
    "인천": "Incheon",
    "경주": "Gyeongju",
}


def geocode_city(city: str) -> dict:
    response = httpx.get(
        f"{settings.open_meteo_geocoding_url}/v1/search",
        params={
            "name": CITY_GEOCODING_NAMES.get(city, city),
            "count": 1,
            "language": "ko",
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        raise ValueError(f"도시를 찾을 수 없습니다: {city}")

    location = results[0]

    return {
        "name": location["name"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
    }


def get_weather_forecast(city: str, target_date: date) -> dict:
    forecast = get_weather_forecast_range(city, target_date, target_date)
    return forecast["days"][0]


def get_weather_forecast_range(
    city: str,
    start_date: date,
    end_date: date,
) -> dict:
    location = geocode_city(city)

    response = httpx.get(
        f"{settings.open_meteo_base_url}/v1/forecast",
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "Asia/Seoul",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()

    daily = response.json().get("daily", {})

    if not daily.get("time"):
        raise ValueError(f"날씨 예보가 없습니다: {start_date.isoformat()}")

    days = []
    for index, current_date in enumerate(daily["time"]):
        weather_code = int(daily["weather_code"][index])
        days.append({
            "city": location["name"],
            "date": current_date,
            "condition": WEATHER_CODES.get(weather_code, f"날씨 코드 {weather_code}"),
            "temperature_max_c": daily["temperature_2m_max"][index],
            "temperature_min_c": daily["temperature_2m_min"][index],
            "precipitation_probability_percent": daily["precipitation_probability_max"][index],
        })

    return {"city": location["name"], "days": days, "source": "open-meteo"}
