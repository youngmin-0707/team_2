import json

from app.config import settings
from app.tools.definitions import TOOL_DEFINITIONS
from app.services.kakao_mobility_service import get_car_route
from app.services.weather_service import get_weather_forecast_range
import re
from datetime import date, timedelta

from pydantic import ValidationError

from app.schemas import (
    SelectedTravelPlanResponse,
    ToolExecution,
    TravelAgentResponse,
)
from app.tools.travel_tools import run_tool


CITIES = ("서울", "부산", "제주", "강릉", "대구", "인천", "경주")

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def find_city(message: str) -> str | None:
    return next((city for city in CITIES if city in message), None)


def find_date(message: str) -> str | None:
    matched = DATE_PATTERN.search(message)

    if matched:
        return matched.group()

    if "오늘" in message:
        return date.today().isoformat()

    if "내일" in message:
        return (date.today() + timedelta(days=1)).isoformat()

    return None


def find_place_query(message: str) -> str:
    if "카페" in message:
        return "카페"
    if "맛집" in message or "식당" in message:
        return "맛집"
    if "박물관" in message:
        return "박물관"
    if "실내" in message:
        return "실내 관광지"

    return "관광지"


def is_itinerary_request(message: str) -> bool:
    keywords = ("일정", "코스", "계획", "짜줘", "하루")
    return any(keyword in message for keyword in keywords)


def execute_tool(
    tool_name: str,
    arguments: dict,
) -> tuple[ToolExecution, dict | None]:
    try:
        data = run_tool(tool_name, arguments)

        return (
            ToolExecution(
                tool_name=tool_name,
                arguments=arguments,
                success=True,
                data=data,
            ),
            data,
        )
    except (ValueError, ValidationError) as error:
        return (
            ToolExecution(
                tool_name=tool_name,
                arguments=arguments,
                success=False,
                error=str(error),
            ),
            None,
        )


INTEREST_QUERIES = {
    "attraction": "관광지",
    "cafe": "카페",
    "restaurant": "맛집",
    "indoor": "실내 관광지",
}


def generate_selected_itinerary(
    city: str,
    start_date: date,
    end_date: date,
    interest: str,
    places: list[dict],
    weather: dict | None,
    routes: list[dict],
) -> str:
    """실제 조회 결과만 근거로 한 번의 OpenAI 호출로 여행 안내를 생성한다."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    from openai import OpenAI

    context = {
        "city": city,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "interest": interest,
        "places": places,
        "weather": weather,
        "car_routes": routes,
    }
    response = OpenAI(api_key=settings.openai_api_key).responses.create(
        model=settings.openai_model,
        instructions=(
            "Write a concise Korean itinerary in plain text. Never include URLs, map links, or the phrase '카카오맵 링크'. "
            "Place names and route summaries are enough because the interface already renders the map. "
            "당신은 한국 국내 여행 플래너입니다. 제공된 JSON 데이터에 있는 장소와 "
            "날씨, 차량 경로 정보만 사용해 날짜별 여행 일정을 한국어로 작성하세요. "
            "각 날짜에 추천 장소와 차량 이동 시간을 간결하게 안내하고, "
            "정보가 없는 영업시간·가격·예약 정보는 추측하지 마세요."
        ),
        input=json.dumps(context, ensure_ascii=False),
    )
    return response.output_text.strip()


def run_selected_travel_plan(
    city: str,
    start_date: date,
    end_date: date,
    interest: str,
) -> TravelAgentResponse:
    """선택형 UI용: 실제 API를 고정 순서로 호출하는 빠른 여행 플래너."""
    executions: list[ToolExecution] = []

    place_execution, place_result = execute_tool(
        "search_places",
        {"city": city, "query": INTEREST_QUERIES[interest]},
    )
    executions.append(place_execution)
    if place_result is None or not place_result.get("items"):
        return SelectedTravelPlanResponse(
            provider="openai",
            tool_executions=executions,
            final_answer="실제 장소 검색에 실패했습니다. Kakao API 설정을 확인해주세요.",
        )

    trip_days = (end_date - start_date).days + 1
    places = place_result["items"][:min(5, trip_days + 1)]
    try:
        weather_result = get_weather_forecast_range(city, start_date, end_date)
        executions.append(ToolExecution(
            tool_name="get_weather",
            arguments={"city": city, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            success=True,
            data=weather_result,
        ))
    except Exception as error:
        weather_result = None
        executions.append(ToolExecution(
            tool_name="get_weather",
            arguments={"city": city, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            success=False,
            error=str(error),
        ))

    route_results: list[dict] = []
    for origin, destination in zip(places, places[1:]):
        try:
            route_result = get_car_route(origin, destination)
            route_results.append(route_result)
            executions.append(ToolExecution(
                tool_name="get_route",
                arguments={"origin": origin["name"], "destination": destination["name"], "mode": "car"},
                success=True,
                data=route_result,
            ))
        except Exception as error:
            executions.append(ToolExecution(
                tool_name="get_route",
                arguments={"origin": origin["name"], "destination": destination["name"], "mode": "car"},
                success=False,
                error=str(error),
            ))

    try:
        final_answer = generate_selected_itinerary(
            city, start_date, end_date, interest, places, weather_result, route_results
        )
        executions.append(ToolExecution(
            tool_name="create_itinerary",
            arguments={"city": city, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "interest": interest},
            success=True,
            data={"source": "openai", "place_count": len(places)},
        ))
    except Exception as error:
        executions.append(ToolExecution(
            tool_name="create_itinerary",
            arguments={"city": city, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "interest": interest},
            success=False,
            error=str(error),
        ))
        final_answer = "실제 장소와 날씨는 조회했지만 일정 문장 생성에 실패했습니다."

    return SelectedTravelPlanResponse(
        provider="openai",
        tool_executions=executions,
        final_answer=final_answer,
        places=places,
        weather=weather_result,
        routes=route_results,
    )


def run_mock_travel_agent(message: str) -> TravelAgentResponse:
    city = find_city(message)
    target_date = find_date(message)
    executions: list[ToolExecution] = []

    if city is None:
        return TravelAgentResponse(
            provider="mock",
            final_answer="여행할 도시를 알 수 없습니다.",
            follow_up_question="어느 도시로 여행할지 알려주세요.",
        )

    if is_itinerary_request(message) and target_date is None:
        return TravelAgentResponse(
            provider="mock",
            final_answer="일정을 만들 날짜가 필요합니다.",
            follow_up_question="여행 날짜를 YYYY-MM-DD 형식으로 알려주세요.",
        )

    query = find_place_query(message)

    place_execution, place_result = execute_tool(
        "search_places",
        {
            "city": city,
            "query": query,
        },
    )
    executions.append(place_execution)

    if place_result is None:
        return TravelAgentResponse(
            provider="mock",
            tool_executions=executions,
            final_answer="장소 검색에 실패했습니다. Kakao API 키와 검색어를 확인해주세요.",
        )

    if not is_itinerary_request(message):
        count = len(place_result["items"])

        return TravelAgentResponse(
            provider="mock",
            tool_executions=executions,
            final_answer=f"{city}에서 '{query}' 장소 {count}곳을 찾았습니다.",
        )

    weather_execution, weather_result = execute_tool(
        "get_weather",
        {
            "city": city,
            "target_date": target_date,
        },
    )
    executions.append(weather_execution)

    places = place_result["items"][:2]
    routes: list[dict] = []

    for index in range(len(places) - 1):
        route_execution, route_result = execute_tool(
            "get_route",
            {
                "origin": places[index]["name"],
                "destination": places[index + 1]["name"],
                "mode": "walk",
            },
        )
        executions.append(route_execution)

        if route_result is not None:
            routes.append(route_result)

    itinerary_execution, itinerary_result = execute_tool(
        "create_itinerary",
        {
            "city": city,
            "target_date": target_date,
            "places": places,
            "weather": weather_result,
            "routes": routes,
        },
    )
    executions.append(itinerary_execution)

    if itinerary_result is None:
        return TravelAgentResponse(
            provider="mock",
            tool_executions=executions,
            final_answer="장소와 날씨를 확인했지만 일정 생성에는 실패했습니다.",
        )

    item_count = len(itinerary_result["items"])

    return TravelAgentResponse(
        provider="mock",
        tool_executions=executions,
        final_answer=(
            f"{target_date} {city} 여행 일정 {item_count}곳을 만들었습니다. "
            f"{itinerary_result['weather_note']}"
        ),
    )
def run_openai_travel_agent(message: str) -> TravelAgentResponse:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    tools = [
        {
            "type": "function",
            "name": definition["name"],
            "description": definition["description"],
            "parameters": definition["input_schema"],
        }
        for definition in TOOL_DEFINITIONS
    ]

    response = client.responses.create(
        model=settings.openai_model,
        instructions=(
            "당신은 여행 도우미입니다. 필요한 경우에만 제공된 도구를 호출하세요. "
            "도구 결과에 없는 사실을 만들지 마세요. "
            "일정 요청은 장소, 날씨, 경로, 일정 생성 순서를 우선하세요. "
            "필수 정보가 부족하면 도구를 호출하지 말고 사용자에게 질문하세요."
        ),
        input=message,
        tools=tools,
        tool_choice="auto",
        parallel_tool_calls=False,
    )

    executions: list[ToolExecution] = []

    for _ in range(4):
        calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        if not calls:
            break

        tool_outputs = []

        for call in calls:
            arguments = json.loads(call.arguments)
            execution, data = execute_tool(call.name, arguments)
            executions.append(execution)

            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(
                        data if data is not None else {"error": execution.error},
                        ensure_ascii=False,
                    ),
                }
            )

        response = client.responses.create(
            model=settings.openai_model,
            previous_response_id=response.id,
            input=tool_outputs,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )

    final_answer = response.output_text.strip()

    if not final_answer:
        final_answer = "도구 실행은 완료됐지만 최종 답변을 생성하지 못했습니다."

    return TravelAgentResponse(
        provider="openai",
        tool_executions=executions,
        final_answer=final_answer,
    )
