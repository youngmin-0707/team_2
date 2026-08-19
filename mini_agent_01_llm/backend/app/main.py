from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.agent_router import agent_router
from app.routers.media_router import media_router


app = FastAPI(title="Mini Agent 01 · LLM 판단에서 서비스 연결까지")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", 
                   "http://127.0.0.1:8501"
                   "https://9bbyrmawmtasbjghg8ahcg.streamlit.app/"
                   ],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)
app.include_router(agent_router)
app.include_router(media_router)
