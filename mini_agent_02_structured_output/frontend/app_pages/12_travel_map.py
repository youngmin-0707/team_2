import pandas as pd
import pydeck as pdk
import streamlit as st

from clients.agent_client import generate_travel_landmarks
from core.api_client import BackendAPIError


st.title("🗺️ 여행 랜드마크 지도")
st.caption("여행 질문을 보내면 추천 장소를 지도와 목록으로 보여 줍니다.")

provider = st.selectbox(
    "Provider",
    ["mock", "gemini", "openai", "ollama"],
    index=0,
)

message = st.text_area(
    "여행 질문",
    value="부산에서 하루 동안 갈 만한 여행지를 추천해 주세요.",
    max_chars=1000,
)

if st.button("지도 만들기", type="primary", disabled=not message.strip()):
    try:
        with st.spinner("여행 랜드마크를 만들고 있습니다."):
            result = generate_travel_landmarks(provider, message)

        st.session_state["travel_landmarks_result"] = result

    except BackendAPIError as error:
        st.error(str(error))


result = st.session_state.get("travel_landmarks_result")

if result:
    content = result["content"]
    landmarks = content["landmarks"]

    st.subheader(content["destination"])
    st.write(content["summary"])

    map_data = pd.DataFrame(landmarks)

    if map_data.empty:
        st.warning("지도에 표시할 랜드마크가 없습니다.")
    else:
        center_latitude = map_data["latitude"].mean()
        center_longitude = map_data["longitude"].mean()

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_data,
            get_position="[longitude, latitude]",
            get_radius=180,
            get_fill_color="[255, 75, 75, 180]",
            pickable=True,
        )

        view_state = pdk.ViewState(
            latitude=center_latitude,
            longitude=center_longitude,
            zoom=12,
            pitch=0,
        )

        tooltip = {
            "html": (
                "<b>{name}</b><br/>"
                "{description}<br/>"
                "<small>{address}</small>"
            ),
            "style": {
                "backgroundColor": "white",
                "color": "black",
            },
        }

        deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="light",
)

        st.pydeck_chart(deck, use_container_width=True)

        st.subheader("추천 장소 목록")

        for landmark in landmarks:
            with st.expander(landmark["name"]):
                st.write(landmark["description"])
                st.caption(landmark["address"])
                st.code(
                    f'위도: {landmark["latitude"]}, '
                    f'경도: {landmark["longitude"]}'
                )

        st.caption(
            f'Provider: {result["provider"]} · '
            f'Model: {result["model"]} · '
            f'응답 시간: {result["latency_ms"]}ms'
        )