from datetime import date, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st

from clients.agent_client import run_selected_travel_plan
from core.api_client import BackendAPIError


INTEREST_OPTIONS = {
    "관광 명소": "attraction",
    "카페": "cafe",
    "맛집": "restaurant",
    "실내 관광": "indoor",
}


def weather_icon(condition: str) -> str:
    icons = (
        (("뇌우",), "⛈️"),
        (("눈",), "❄️"),
        (("소나기",), "🌦️"),
        (("비",), "🌧️"),
        (("안개",), "🌫️"),
        (("흐림",), "☁️"),
        (("부분", "대체"), "⛅"),
        (("맑",), "☀️"),
    )
    return next((icon for keywords, icon in icons if any(word in condition for word in keywords)), "🌤️")


def render_weather(days: list[dict], error: str | None) -> None:
    st.subheader("여행 날씨")
    if not days:
        st.warning("날씨 정보를 불러오지 못했습니다. 일정은 장소와 차량 경로 기준으로 만들었습니다.")
        if error:
            st.caption(f"확인 내용: {error}")
        return

    columns = st.columns(min(len(days), 7))
    for column, forecast in zip(columns, days):
        condition = forecast.get("condition", "날씨 정보 없음")
        target_date = forecast.get("date", "")
        with column:
            st.markdown(f"### {weather_icon(condition)}")
            st.caption(target_date.replace("-", "."))
            st.write(condition)
            st.caption(
                f"최저 {forecast.get('temperature_min_c', '-')}° · "
                f"최고 {forecast.get('temperature_max_c', '-')}°"
            )
            st.caption(f"강수확률 {forecast.get('precipitation_probability_percent', '-')}%")


def build_deck(points: list[dict]) -> pdk.Deck:
    map_data = pd.DataFrame(points)
    return pdk.Deck(
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position="[longitude, latitude]",
                get_radius=150,
                get_fill_color=[255, 82, 82, 220],
                get_line_color=[255, 255, 255, 230],
                line_width_min_pixels=2,
                stroked=True,
                pickable=True,
            )
        ],
        initial_view_state=pdk.ViewState(
            latitude=map_data["latitude"].mean(),
            longitude=map_data["longitude"].mean(),
            zoom=11,
        ),
        tooltip={
            "html": "<b>{name}</b><br/>{address}",
            "style": {"backgroundColor": "white", "color": "black"},
        },
        map_style="light",
    )


def tool_error(executions: list[dict], tool_name: str) -> str | None:
    for execution in executions:
        if execution["tool_name"] == tool_name and not execution["success"]:
            return execution.get("error")
    return None


def clean_itinerary_text(text: str) -> str:
    """지도는 별도 UI로 제공하므로 AI 본문의 중복 지도 링크를 숨긴다."""
    hidden_markers = ("카카오맵 링크", "http://", "https://")
    return "\n".join(
        line for line in text.splitlines()
        if not any(marker in line for marker in hidden_markers)
    )


st.title("여행 플래너")
st.caption("도시와 관심사를 선택하면 실제 장소·날씨·차량 경로를 바탕으로 여행 일정을 만듭니다.")

with st.form("travel-planner"):
    left, right = st.columns(2)
    with left:
        city = st.selectbox("여행 도시", ["서울", "부산", "제주", "강릉", "대구", "인천", "경주"])
        interest_label = st.selectbox("여행 관심사", list(INTEREST_OPTIONS))
    with right:
        trip_period = st.date_input(
            "여행 기간",
            value=(date.today(), date.today() + timedelta(days=2)),
            min_value=date.today(),
            max_value=date.today() + timedelta(days=6),
            format="YYYY/MM/DD",
        )
        st.text_input("이동수단", value="차량", disabled=True)

    submitted = st.form_submit_button("실제 데이터로 일정 만들기", type="primary")

if submitted:
    try:
        if not isinstance(trip_period, tuple) or len(trip_period) != 2:
            st.error("여행 시작일과 종료일을 모두 선택해주세요.")
            st.stop()
        start_date, end_date = trip_period
        with st.spinner("장소, 날씨, 차량 경로를 확인하고 일정을 만들고 있습니다."):
            st.session_state["selected_travel_plan"] = run_selected_travel_plan(
                city,
                start_date.isoformat(),
                end_date.isoformat(),
                INTEREST_OPTIONS[interest_label],
            )
    except BackendAPIError as error:
        st.error(str(error))

developer_mode = st.toggle(
    "개발자 모드",
    value=False,
    help="실제 API 호출 순서, 입력값, 성공·실패 결과를 확인합니다.",
)

result = st.session_state.get("selected_travel_plan")

if result:
    executions = result["tool_executions"]
    succeeded = sum(item["success"] for item in executions)
    places = result.get("places", [])
    weather = result.get("weather") or {}
    routes = result.get("routes", [])
    day_count = len(weather.get("days", []))

    st.subheader("추천 일정")
    if day_count:
        st.caption(f"{weather.get('city', city)} · {day_count}일 · 차량 이동")
    st.write(clean_itinerary_text(result["final_answer"]))

    render_weather(weather.get("days", []), tool_error(executions, "get_weather"))

    if places:
        st.subheader("추천 장소 지도")
        st.pydeck_chart(build_deck(places), use_container_width=True)
        st.caption("● 추천 장소 마커 · 마커에 마우스를 올리면 장소명과 주소를 확인할 수 있습니다.")

    if developer_mode:
        st.divider()
        st.subheader("도구 실행 기록")
        st.caption(f"실제 데이터 조회 {succeeded}/{len(executions)}개 성공")
        if not executions:
            st.info("이번 요청에서는 호출한 도구가 없습니다.")
        for index, execution in enumerate(executions, start=1):
            status = "성공" if execution["success"] else "실패"
            with st.expander(f"{index}. {execution['tool_name']} · {status}"):
                st.write("입력값")
                st.json(execution["arguments"])
                if execution["success"]:
                    st.write("결과")
                    st.json(execution["data"])
                else:
                    st.error(execution["error"])
