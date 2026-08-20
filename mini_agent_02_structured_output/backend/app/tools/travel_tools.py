from math import ceil

from app.schemas import (
    ItineraryArgs,
    RouteArgs,
    SearchPlacesArgs,
    WeatherArgs,
)
from app.services.kakao_local_service import search_places
from app.services.weather_service import get_weather_forecast


def run_search_places(arguments: dict) -> dict:
    args = SearchPlacesArgs.model_validate(arguments)

    return {
        "city": args.city,
        "query": args.query,
        "items": search_places(args.city, args.query),
        "source": "kakao-local",
    }


def run_get_weather(arguments: dict) -> dict:
    args = WeatherArgs.model_validate(arguments)

    return get_weather_forecast(
        city=args.city,
        target_date=args.target_date,
    )

def run_get_route(arguments: dict) -> dict:
    args = RouteArgs.model_validate(arguments)

    # 첫 버전에서는 실제 길찾기 API 대신,
    # 동일한 입력에 항상 같은 결과를 주는 Mock 거리값을 사용한다.
    seed = sum(ord(char) for char in f"{args.origin}{args.destination}")
    distance_km = round(1.0 + (seed % 80) / 10, 1)

    speed_kmh = {
        "walk": 4.5,
        "car": 28,
        "transit": 20,
    }[args.mode]

    duration_minutes = ceil(distance_km / speed_kmh * 60)

    return {
        "origin": args.origin,
        "destination": args.destination,
        "mode": args.mode,
        "distance_km": distance_km,
        "duration_minutes": duration_minutes,
        "source": "mock-routing",
    }


def run_create_itinerary(arguments: dict) -> dict:
    args = ItineraryArgs.model_validate(arguments)

    if not args.places:
        raise ValueError("일정을 만들려면 최소 한 곳의 장소가 필요합니다.")

    precipitation = 0
    if args.weather is not None:
        precipitation = args.weather.get(
            "precipitation_probability_percent",
            0,
        )

    weather_note = (
        "비 예보가 있어 실내 휴식 또는 우산을 준비하세요."
        if precipitation >= 50
        else "야외 이동에 무난한 날씨입니다."
    )

    itinerary_items: list[dict] = []

    for index, place in enumerate(args.places[:3]):
        hour = 10 + index * 2
        route = args.routes[index - 1] if index > 0 and len(args.routes) >= index else None

        itinerary_items.append(
            {
                "time": f"{hour:02d}:00",
                "place_name": place["name"],
                "address": place.get("address", ""),
                "activity": f"{place['name']} 방문",
                "travel_note": (
                    f"{route['mode']} 약 {route['duration_minutes']}분 이동"
                    if route is not None
                    else "첫 방문 장소"
                ),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
            }
        )

    return {
        "city": args.city,
        "date": args.target_date.isoformat(),
        "weather_note": weather_note,
        "items": itinerary_items,
        "source": "mock-itinerary",
    }

TOOLS = {
    "search_places": run_search_places,
    "get_weather": run_get_weather,
    "get_route": run_get_route,
    "create_itinerary": run_create_itinerary,
}


def run_tool(tool_name: str, arguments: dict) -> dict:
    tool = TOOLS.get(tool_name)

    if tool is None:
        raise ValueError(f"허용되지 않은 도구입니다: {tool_name}")

    return tool(arguments)