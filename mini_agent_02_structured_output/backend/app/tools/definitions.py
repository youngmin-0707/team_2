from app.schemas import (
    ItineraryArgs,
    RouteArgs,
    SearchPlacesArgs,
    WeatherArgs,
)


TOOL_DEFINITIONS = [
    {
        "name": "search_places",
        "description": (
            "여행 도시에서 관광지, 카페, 식당 등 장소를 검색한다. "
            "장소명, 주소, 카테고리, 위도, 경도를 반환한다."
        ),
        "input_schema": SearchPlacesArgs.model_json_schema(),
    },
    {
        "name": "get_weather",
        "description": (
            "특정 도시와 날짜의 날씨 예보를 조회한다. "
            "날씨 상태, 최고·최저 기온, 강수확률을 반환한다."
        ),
        "input_schema": WeatherArgs.model_json_schema(),
    },
    {
        "name": "get_route",
        "description": (
            "두 장소 사이의 예상 거리와 이동 시간을 조회한다. "
            "이동수단은 walk, car, transit 중 하나를 사용한다."
        ),
        "input_schema": RouteArgs.model_json_schema(),
    },
    {
        "name": "create_itinerary",
        "description": (
            "장소, 날씨, 이동 정보를 바탕으로 시간순 여행 일정을 생성한다. "
            "일정 생성 전에는 장소 검색 결과가 필요하다."
        ),
        "input_schema": ItineraryArgs.model_json_schema(),
    },
]