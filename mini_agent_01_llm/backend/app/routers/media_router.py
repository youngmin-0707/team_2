"""이미지·영상 분석 및 TTS API 라우터.

실행 방법:
    uvicorn app.main:app --reload

`POST /api/media/video-analysis`는 브라우저가 추출한 최대 12개 JPG 프레임과
타임스탬프를 받아 통합 장면 요약을 반환합니다. 원본 영상은 받거나 저장하지 않습니다.
"""

import json

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.schemas import TtsRequest
from app.services.media_service import analyze_image, analyze_video_frames, create_speech


media_router = APIRouter(prefix="/api/media", tags=["Multimodal"])


@media_router.post("/image-analysis")
async def image_analysis(
    image: UploadFile = File(...),
    question: str = Form("여행자가 알아야 할 정보와 주의점을 알려주세요."),
) -> dict:
    try:
        result = analyze_image(image.content_type or "", await image.read(), question)
        return result.model_dump()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"이미지 분석 실패: {error}") from error


@media_router.post("/video-analysis")
async def video_analysis(
    frames: list[UploadFile] = File(...),
    frame_timestamps: str = Form(...),
    language: str = Form(...),
) -> dict:
    try:
        timestamps = json.loads(frame_timestamps)
        if not isinstance(timestamps, list) or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in timestamps
        ):
            raise ValueError("frame_timestamps must be a JSON array of numbers.")
        contents = [(frame.content_type or "", await frame.read()) for frame in frames]
        result = analyze_video_frames(contents, [float(value) for value in timestamps], language)
        return result.model_dump()
    except (json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Video analysis failed: {error}") from error


@media_router.post("/tts")
def text_to_speech(payload: TtsRequest) -> Response:
    try:
        audio = create_speech(payload.text, payload.voice, payload.instructions)
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"X-Synthetic-Voice": "true"},
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"TTS 생성 실패: {error}") from error
