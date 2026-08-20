# 여행 랜드마크 구조화 출력·지도 시각화 계획

## 목표

사용자가 여행 질문을 보내면 AI가 방문할 랜드마크를 **리스트 안의 딕셔너리 형태**로 반환한다.
프런트엔드는 반환된 위도·경도를 지도에 표시하고, 각 장소의 설명과 위치를 함께 보여 준다.

목표 응답 예시:

```json
{
  "destination": "부산",
  "summary": "해운대 중심의 하루 여행 코스입니다.",
  "landmarks": [
    {
      "name": "해운대 해수욕장",
      "description": "부산을 대표하는 해변 산책 명소입니다.",
      "address": "부산광역시 해운대구 우동",
      "latitude": 35.1587,
      "longitude": 129.1604
    }
  ]
}
```

## 초보자를 위한 작업 순서

### 0. 준비와 확인

- 현재 백엔드와 프런트엔드를 각각 실행하고, `/docs`에서 기존 `/api/structured/generate`가 동작하는지 확인한다.
- 처음에는 Provider를 `mock`으로 선택해 API 키 없이 화면과 지도부터 확인한다.
- 모든 단계가 끝날 때마다 `pytest -q`와 Streamlit 화면을 확인한다.

### 1. 백엔드: 응답 데이터 모양 만들기

**파일:** `backend/app/schemas.py`

- `Landmark` 모델을 만든다.
  - `name`: 장소 이름
  - `description`: 장소 설명
  - `address`: 사람이 읽을 수 있는 위치
  - `latitude`: -90~90 범위의 위도
  - `longitude`: -180~180 범위의 경도
- `TravelLandmarks` 모델을 만든다.
  - `destination`, `summary`, `landmarks: list[Landmark]`
  - 랜드마크는 1~10개만 허용한다.
- `StructuredSchemaName`에 `travel_landmarks`를 추가한다.
- Pydantic의 `extra="forbid"`를 사용해 AI가 약속하지 않은 필드를 넣으면 검증에서 실패하게 한다.

완료 기준: Swagger의 스키마에 `Landmark`, `TravelLandmarks`가 나타나고, 잘못된 좌표는 422 검증 오류가 난다.

### 2. 백엔드: Provider가 새 구조를 생성하게 하기

**파일:** `backend/app/providers.py`

- `get_structured_model()`에 `travel_landmarks` → `TravelLandmarks` 매핑을 추가한다.
- `generate_structured_mock()`에 부산 랜드마크 2~3개를 반환하는 분기를 추가한다.
  - 해운대 해수욕장, 동백섬처럼 고정된 정상 좌표를 사용한다.
- 기존 OpenAI/Gemini/Ollama 구조화 생성 함수는 `get_structured_model()`을 공통으로 사용하므로, 새 스키마를 자동으로 처리하는지 확인한다.
- 시스템 프롬프트에 “좌표가 확실하지 않은 장소는 만들지 말고, 유효한 위도·경도만 반환한다”는 지시를 추가한다.

완료 기준: `provider=mock`, `schema_type=travel_landmarks` 요청이 위 예시와 같은 JSON을 반환한다.

### 3. 백엔드: API와 테스트 추가

**파일:** `backend/app/routers/agent_router.py`, `backend/tests/test_api.py`

- 기존 `POST /api/structured/generate`를 그대로 재사용한다. 새 URL을 만들 필요 없이 요청의 `schema_type`만 `travel_landmarks`로 보낸다.
- Swagger에서 이 API가 `Mini Agent 02 · Structured Output` 태그 아래에 보이는지 확인한다.
- 테스트에 아래 경우를 추가한다.
  - mock 랜드마크 생성 성공
  - 위도 90 초과 또는 경도 180 초과 시 검증 실패
  - 랜드마크가 빈 리스트일 때 검증 실패

완료 기준: 새 테스트와 기존 테스트가 함께 통과한다.

### 4. 프런트엔드: API 호출 함수 추가

**파일:** `frontend/clients/agent_client.py`

- `generate_travel_landmarks(provider, message)` 함수를 만든다.
- 내부에서는 기존 구조화 출력 API를 호출한다.

```python
return request(
    "POST",
    "/api/structured/generate",
    json={
        "provider": provider,
        "message": message,
        "schema_type": "travel_landmarks",
    },
)
```

완료 기준: Python 함수가 백엔드 JSON을 그대로 반환한다.

### 5. 프런트엔드: 지도 화면 만들기

**파일:** `frontend/app_pages/12_travel_map.py`, `frontend/app.py`, `requirements.txt`

- 새 Streamlit 페이지를 만들고 사이드바의 “02. Prompt와 구조화 출력” 그룹에 `2-4. 여행 지도` 메뉴를 추가한다.
- 화면에 Provider 선택 상자, 여행 질문 입력창, “지도 만들기” 버튼을 둔다.
- 버튼을 누르면 `generate_travel_landmarks()`를 호출한다.
- 성공한 `landmarks` 리스트를 `pandas.DataFrame`으로 바꾼다.
- `st.pydeck_chart`로 위도·경도 위치에 마커를 표시한다.
  - 마커를 클릭하거나 가리키면 장소명, 설명, 주소가 보이는 tooltip을 설정한다.
- 지도 아래에 장소별 이름·설명·주소를 `st.expander` 또는 표로 보여 준다.
- `pandas`를 `requirements.txt`에 명시적으로 추가한다.

완료 기준: “부산 하루 여행지 추천” 입력 시 최소 1개 이상의 마커와 장소 설명이 함께 나타난다.

### 6. 오류 처리와 사용자 안내

**파일:** `frontend/app_pages/12_travel_map.py`

- 백엔드 오류는 기존 `BackendAPIError`로 표시한다.
- 좌표가 없거나 범위를 벗어난 항목은 지도에 넣지 않고 경고를 보여 준다.
- `mock`은 항상 부산 예시를 반환한다고 화면에 안내한다.
- OpenAI/Gemini가 실제 장소 좌표를 잘못 만들 수 있음을 안내한다. 정확도가 필요한 다음 버전에서는 서버에서 지오코딩 API로 주소를 좌표로 변환한다.

## 지도 API 키 계획

### 1차 구현: API 키 없이 지도 표시

- `st.pydeck_chart`의 기본 Carto 지도 타일을 사용한다.
- AI가 반환한 `latitude`, `longitude`를 그대로 마커로 표시한다.
- 별도의 지도 API 키는 필요하지 않다.
- 장소명·설명·주소는 지도 tooltip과 지도 아래 목록에서 표시한다.

### 다음 구현: 실제 주소를 정확한 좌표로 변환

- AI가 만든 좌표는 틀릴 수 있으므로, 정확도가 필요한 경우 주소를 지오코딩 API로 실제 좌표로 변환한다.
- Google Maps, Kakao Maps, Naver Maps 등은 API 키가 필요할 수 있다.
- 키를 사용하는 경우 `.env`에 저장하고 GitHub에 커밋하지 않는다.
- 지도 화면이 먼저 완성된 뒤에 지오코딩 기능을 별도 작업으로 추가한다.

### 키가 필요한 경우

| 기능 | API 키 |
|---|---|
| 기본 지도와 위도·경도 마커 표시 | 필요 없음 |
| Mapbox 스타일 지도 | `MAPBOX_API_KEY` 필요 |
| Google Maps 지도 | `GOOGLE_MAPS_API_KEY` 필요 |
| 주소·장소명에서 정확한 좌표 찾기 | 선택한 지오코딩 서비스 정책에 따름 |

## 구현 순서 요약

1. 스키마 → 2. mock Provider → 3. API 테스트 → 4. 프런트 API 함수 → 5. 지도 화면 → 6. 실제 Provider 테스트

이 순서를 지키면 AI API 키나 지도 기능 문제를 한 번에 디버깅하지 않고, 각 단계의 결과를 따로 확인할 수 있다.
