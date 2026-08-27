import asyncio
import json
from urllib.parse import quote, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.schemas import (
    BilibiliVideoFetchRequest,
    BilibiliVideoFetchResponse,
    LoginRequest,
    NoteGenerateRequest,
    NoteGenerateResponse,
    RegisterRequest,
    SavedNoteGroup,
    SavedNoteSummary,
    SubtitleResponse,
    VideoInfo,
    SubtitleLine,
    VideoTaskCreateRequest,
    VideoTaskCreateResponse,
    VideoTaskResponse,
    VideoTaskStep,
    UserProfile,
)
from app.services.ai import AIService, AIServiceError
from app.services.bilibili import BilibiliError, BilibiliService, BilibiliSubtitleResult, BilibiliSubtitleUnavailableError
from app.services.bilibili_fetcher import (
    BilibiliFetchError,
    BilibiliVideoFetcher,
)
from app.services.transcription import AudioTranscriptionError, AudioTranscriptionService
from app.services.task_service import VideoTaskService
from app.services.note_repository import NoteRepository
from app.services.douyin import DouyinError, DouyinService
from app.services.pdf_export import NotePdfService, PdfExportError
from app.services.user_repository import (
    InsufficientPointsError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserRepository,
)

app = FastAPI(title="AiNote API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bilibili_service = BilibiliService()
bilibili_video_fetcher = BilibiliVideoFetcher()
audio_transcription_service = AudioTranscriptionService(bilibili_video_fetcher)
ai_service = AIService()
note_repository = NoteRepository()
user_repository = UserRepository()
douyin_service = DouyinService()
note_pdf_service = NotePdfService()
video_task_service = VideoTaskService(
    bilibili_service,
    bilibili_video_fetcher,
    audio_transcription_service,
    ai_service,
    note_repository,
    douyin_service,
    user_repository,
)


@app.on_event("startup")
async def initialize_note_repository() -> None:
    await user_repository.initialize()
    await note_repository.initialize()


async def current_user(request: Request) -> UserProfile:
    token = request.cookies.get("ainote_session", "")
    user = await user_repository.get_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录后继续使用")
    return user


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "ainote_session",
        token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


@app.post("/api/auth/register", response_model=UserProfile)
async def register(request: RegisterRequest, response: Response) -> UserProfile:
    try:
        session = await user_repository.register(request.account, request.email, request.password)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    set_session_cookie(response, session.token)
    return session.user


@app.post("/api/auth/login", response_model=UserProfile)
async def login(request: LoginRequest, response: Response) -> UserProfile:
    try:
        session = await user_repository.login(request.login, request.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_session_cookie(response, session.token)
    return session.user


@app.post("/api/auth/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    await user_repository.logout(request.cookies.get("ainote_session", ""))
    response.delete_cookie("ainote_session", path="/")


@app.get("/api/auth/me", response_model=UserProfile)
async def get_current_user(user: UserProfile = Depends(current_user)) -> UserProfile:
    return user


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/video/cover")
@app.get("/api/bilibili/cover", include_in_schema=False)
async def get_video_cover(url: str = Query(min_length=1)) -> Response:
    """代理已支持平台的封面，避免浏览器跨域或防盗链导致图片无法显示。"""
    image_url = url.strip()
    if image_url.startswith("//"):
        image_url = f"https:{image_url}"
    elif image_url.startswith("http://"):
        image_url = f"https://{image_url.removeprefix('http://')}"

    parsed_url = urlparse(image_url)
    hostname = (parsed_url.hostname or "").lower()
    allowed_domains = ("hdslb.com", "douyinpic.com", "douyinvod.com", "byteimg.com", "ibytedtos.com")
    if parsed_url.scheme != "https" or not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
        raise HTTPException(status_code=400, detail="该图片域名暂不支持代理")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            upstream = await client.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.douyin.com/" if "douyin" in hostname else "https://www.bilibili.com/",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="视频封面获取失败") from exc

    content_type = upstream.headers.get("content-type", "image/jpeg").split(";", maxsplit=1)[0]
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="封面地址没有返回图片内容")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/bilibili/video/fetch", response_model=BilibiliVideoFetchResponse)
async def fetch_bilibili_video(
    request: BilibiliVideoFetchRequest,
    _: UserProfile = Depends(current_user),
) -> BilibiliVideoFetchResponse:
    """按链接域名读取 B站或抖音视频信息。"""
    try:
        data = (await douyin_service.fetch(request.url)).as_preview() if douyin_service.is_douyin_url(request.url) else await bilibili_video_fetcher.fetch(request)
    except (BilibiliFetchError, DouyinError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BilibiliVideoFetchResponse(success=True, message="获取视频信息成功", data=data)


@app.post("/api/v1/video/tasks", response_model=VideoTaskCreateResponse)
async def create_video_task(
    request: VideoTaskCreateRequest,
    user: UserProfile = Depends(current_user),
) -> VideoTaskCreateResponse:
    try:
        points_cost = 0 if user.isAdmin else await estimate_task_cost(request)
        task, points_balance = await video_task_service.create_task(request, user.id, points_cost)
        if user.isAdmin:
            points_balance = user.points
    except InsufficientPointsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except (BilibiliFetchError, DouyinError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VideoTaskCreateResponse(
        taskId=task.taskId,
        status=task.status,
        pointsCost=points_cost,
        pointsBalance=points_balance,
    )


async def estimate_task_cost(request: VideoTaskCreateRequest) -> int:
    if douyin_service.is_douyin_url(request.videoUrl):
        video = await douyin_service.fetch(request.videoUrl)
        return user_repository.calculate_video_cost(video.duration)
    video_data = await bilibili_video_fetcher.fetch(BilibiliVideoFetchRequest(url=request.videoUrl))
    entries = video_task_service._select_bilibili_entries(video_data, request.videoUrls)
    durations = [int(item.duration_seconds or 0) for item in entries]
    if not durations:
        raise RuntimeError("没有找到需要生成笔记的视频")
    known_duration = sum(durations)
    return user_repository.calculate_video_cost(known_duration) if known_duration else len(entries)


@app.get("/api/v1/tasks/{task_id}", response_model=VideoTaskResponse)
async def get_video_task(task_id: str, user: UserProfile = Depends(current_user)) -> VideoTaskResponse:
    task = await video_task_service.get_task(task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return task


@app.get("/api/v1/tasks/{task_id}/steps", response_model=list[VideoTaskStep])
async def get_video_task_steps(task_id: str, user: UserProfile = Depends(current_user)) -> list[VideoTaskStep]:
    task = await video_task_service.get_task(task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return task.steps


@app.get("/api/v1/tasks/{task_id}/note", response_model=NoteGenerateResponse)
async def get_video_task_note(task_id: str, user: UserProfile = Depends(current_user)) -> NoteGenerateResponse:
    task = await video_task_service.get_task(task_id, user.id)
    if not task:
        saved_note = await note_repository.get_note(user.id, task_id)
        if saved_note:
            return saved_note
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if task.status == "failed":
        raise HTTPException(status_code=400, detail=task.errorMessage or "任务执行失败")
    if task.status != "success":
        raise HTTPException(status_code=409, detail="笔记仍在生成中")
    note = await video_task_service.get_note(task_id, user.id)
    if not note:
        raise HTTPException(status_code=404, detail="任务未找到笔记结果")
    return note


@app.get("/api/v1/notes", response_model=list[SavedNoteSummary])
async def list_saved_notes(user: UserProfile = Depends(current_user)) -> list[SavedNoteSummary]:
    return await note_repository.list_notes(user.id)


@app.get("/api/v1/note-groups", response_model=list[SavedNoteGroup])
async def list_saved_note_groups(user: UserProfile = Depends(current_user)) -> list[SavedNoteGroup]:
    """返回按视频源归档的笔记，以及多P合集的完整可生成视频清单。"""
    return await note_repository.list_note_groups(user.id)


@app.get("/api/v1/notes/{task_id}", response_model=NoteGenerateResponse)
async def get_saved_note(task_id: str, user: UserProfile = Depends(current_user)) -> NoteGenerateResponse:
    note = await note_repository.get_note(user.id, task_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@app.get("/api/v1/notes/{task_id}/export/pdf")
async def export_saved_note_pdf(task_id: str, user: UserProfile = Depends(current_user)) -> Response:
    """由后端 Chromium 进行原生分页，避免浏览器截图式导出的断页与重叠。"""
    note = await note_repository.get_note(user.id, task_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    try:
        content = await note_pdf_service.export(note)
    except PdfExportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    filename = f"{note.video.title or 'AI笔记'}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/v1/tasks/{task_id}/events")
async def stream_video_task_events(task_id: str, user: UserProfile = Depends(current_user)) -> StreamingResponse:
    queue = await video_task_service.subscribe(task_id, user.id)
    if not queue:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    async def event_stream():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    if payload["status"] in {"success", "failed", "cancelled"}:
                        return
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await video_task_service.unsubscribe(task_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def resolve_video_transcript(url: str) -> BilibiliSubtitleResult:
    """优先使用 B站字幕；无可用字幕时自动降级为音频转文字。"""
    try:
        return await bilibili_service.fetch_subtitle(url)
    except BilibiliSubtitleUnavailableError:
        try:
            return await audio_transcription_service.transcribe_bilibili_video(url)
        except AudioTranscriptionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/videos/subtitle", response_model=SubtitleResponse)
async def get_subtitle(url: str, _: UserProfile = Depends(current_user)) -> SubtitleResponse:
    try:
        result = await resolve_video_transcript(url)
    except BilibiliError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SubtitleResponse(
        video=VideoInfo(**result.video),
        lines=[SubtitleLine(**line) for line in result.lines],
        text=result.text,
        source=result.source,
    )


@app.post("/api/notes/generate", response_model=NoteGenerateResponse)
async def generate_note(
    request: NoteGenerateRequest,
    _: UserProfile = Depends(current_user),
) -> NoteGenerateResponse:
    raise HTTPException(status_code=410, detail="请通过视频任务接口生成笔记，以便正确计算积分")
