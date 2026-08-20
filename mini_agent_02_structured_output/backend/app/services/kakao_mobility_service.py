"""Kakao Mobility 차량 길찾기 API 클라이언트."""

import httpx

from app.config import settings


def _extract_route_path(route: dict) -> list[list[float]]:
    """Convert Kakao Mobility road vertices to pydeck [longitude, latitude] points."""
    path: list[list[float]] = []

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertices = road.get("vertexes", [])
            for index in range(0, len(vertices) - 1, 2):
                point = [vertices[index], vertices[index + 1]]
                if not path or path[-1] != point:
                    path.append(point)

    return path


def get_car_route(origin: dict, destination: dict) -> dict:
    """두 Kakao Local 장소 사이의 실제 차량 경로 요약을 반환한다."""
    if not settings.kakao_rest_api_key:
        raise ValueError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    response = httpx.get(
        f"{settings.kakao_mobility_base_url}/v1/directions",
        headers={"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"},
        params={
            "origin": f"{origin['longitude']},{origin['latitude']},name={origin['name']}",
            "destination": f"{destination['longitude']},{destination['latitude']},name={destination['name']}",
            "priority": "RECOMMEND",
            "summary": "false",
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    routes = response.json().get("routes", [])
    if not routes:
        raise ValueError("차량 경로를 찾을 수 없습니다.")

    route = routes[0]
    summary = route["summary"]
    fare = summary.get("fare", {})
    return {
        "origin": origin["name"],
        "destination": destination["name"],
        "mode": "car",
        "distance_km": round(summary["distance"] / 1000, 1),
        "duration_minutes": round(summary["duration"] / 60000),
        "taxi_fare": fare.get("taxi", 0),
        "toll_fare": fare.get("toll", 0),
        "path": _extract_route_path(route),
        "source": "kakao-mobility",
    }
