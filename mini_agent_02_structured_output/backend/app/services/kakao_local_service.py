import httpx

from app.config import settings
from app.schemas import Landmark, TravelLandmarks


KAKAO_KEYWORD_SEARCH_URL = (
    "https://dapi.kakao.com/v2/local/search/keyword.json"
)


def search_place(query: str) -> dict | None:
    """카카오 키워드 장소 검색에서 첫 번째 검색 결과를 반환한다."""

    if not settings.kakao_rest_api_key:
        raise ValueError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"KakaoAK {settings.kakao_rest_api_key}",
    }
    params = {
        "query": query,
        "size": 1,
    }

    response = httpx.get(
        KAKAO_KEYWORD_SEARCH_URL,
        headers=headers,
        params=params,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()

    documents = response.json()["documents"]

    if not documents:
        return None

    return documents[0]


def correct_landmark_coordinates(
    travel_landmarks: TravelLandmarks,
) -> TravelLandmarks:
    """LLM 랜드마크 목록을 카카오 검색 결과의 실제 좌표로 보정한다."""

    corrected_landmarks: list[Landmark] = []

    for landmark in travel_landmarks.landmarks:
        query = f"{travel_landmarks.destination} {landmark.name}"
        place = search_place(query)

        if place is None:
            continue

        address = place["road_address_name"] or place["address_name"]

        corrected_landmarks.append(
            Landmark(
                name=place["place_name"],
                description=landmark.description,
                address=address,
                latitude=float(place["y"]),
                longitude=float(place["x"]),
            )
        )

    if not corrected_landmarks:
        raise ValueError("카카오에서 찾을 수 있는 여행 장소가 없습니다.")

    return TravelLandmarks(
        destination=travel_landmarks.destination,
        summary=travel_landmarks.summary,
        landmarks=corrected_landmarks,
    )
def search_places(city: str, query: str, size: int = 5) -> list[dict]:
    """도시와 검색어에 맞는 Kakao 장소 목록을 반환한다."""

    if not settings.kakao_rest_api_key:
        raise ValueError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"KakaoAK {settings.kakao_rest_api_key}",
    }
    params = {
        "query": f"{city} {query}",
        "size": min(size, 15),
    }

    response = httpx.get(
        KAKAO_KEYWORD_SEARCH_URL,
        headers=headers,
        params=params,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()

    items: list[dict] = []

    for place in response.json().get("documents", []):
        items.append(
            {
                "name": place["place_name"],
                "address": place["road_address_name"] or place["address_name"],
                "category": place["category_name"],
                "latitude": float(place["y"]),
                "longitude": float(place["x"]),
            }
        )

    return items