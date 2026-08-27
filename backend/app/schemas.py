from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SubtitleLine(BaseModel):
    start: float
    end: float
    content: str


class VideoInfo(BaseModel):
    bvid: str
    title: str
    cover: str | None = None
    duration: int | None = None
    page: int = 1
    platform: str = "bilibili"
    sourceUrl: str | None = None


class CollectionVideo(BaseModel):
    """合集内一个可独立播放、可独立转写的分 P 视频。"""

    bvid: str
    title: str
    cover: str | None = None
    duration: int | None = None
    page: int = 1
    platform: str = "bilibili"
    sourceUrl: str
    noteTaskId: str | None = None


class VideoCollection(BaseModel):
    """一篇笔记关联的合集快照，写入数据库后用于重新打开详情。"""

    title: str
    sourceUrl: str
    cover: str | None = None
    videoCount: int
    totalDuration: int = 0
    videos: list[CollectionVideo] = Field(default_factory=list)
    generatedPages: list[int] = Field(default_factory=list)


class SubtitleResponse(BaseModel):
    video: VideoInfo
    lines: list[SubtitleLine]
    text: str
    source: Literal["bilibili_subtitle", "audio_transcription"] = "bilibili_subtitle"


class NoteGenerateRequest(BaseModel):
    url: str = Field(min_length=1, description="B站视频链接")
    style: Literal["structured", "brief", "study"] = "structured"
    extra_instruction: str | None = Field(default=None, max_length=1000)
    modelProvider: Literal["deepseek", "qwen"] = "deepseek"


class NoteGenerateResponse(BaseModel):
    video: VideoInfo
    subtitle: SubtitleResponse
    note: str
    mindMap: dict[str, Any] = Field(default_factory=dict)
    contentType: str = "通用笔记"
    chunk_count: int
    collection: VideoCollection | None = None


class SavedNoteSummary(BaseModel):
    taskId: str
    title: str
    bvid: str
    cover: str | None = None
    style: str
    createdAt: str
    isCollection: bool = False
    videoCount: int = 1
    page: int = 1
    sourceUrl: str | None = None
    generatedPages: list[int] = Field(default_factory=list)


class SavedNoteGroup(BaseModel):
    """按同一视频源归档的笔记组，合集展开时返回完整分P清单。"""

    groupId: str
    title: str
    bvid: str
    cover: str | None = None
    sourceUrl: str | None = None
    platform: str = "bilibili"
    videoCount: int = 1
    generatedCount: int = 0
    collectionNoteTaskId: str | None = None
    videos: list[CollectionVideo] = Field(default_factory=list)
    notes: list[SavedNoteSummary] = Field(default_factory=list)


TaskStatus = Literal["pending", "running", "success", "failed", "cancelled"]
TaskStepStatus = Literal["pending", "running", "success", "failed", "skipped"]


class VideoTaskCreateRequest(BaseModel):
    videoUrl: str = Field(min_length=1, description="B站视频链接")
    videoUrls: list[str] = Field(default_factory=list, max_length=200, description="合集内需要生成笔记的分P链接")
    style: Literal["structured", "brief", "study"] = "structured"
    extraInstruction: str | None = Field(default=None, max_length=1000)
    modelProvider: Literal["deepseek", "qwen"] = "deepseek"


class VideoTaskStep(BaseModel):
    key: str
    label: str
    status: TaskStepStatus = "pending"
    progress: int = Field(default=0, ge=0, le=100)
    message: str = "等待处理"


class VideoTaskResponse(BaseModel):
    taskId: str
    status: TaskStatus
    currentStep: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    videoUrl: str
    videoTitle: str | None = None
    errorMessage: str | None = None
    createdAt: str
    finishedAt: str | None = None
    steps: list[VideoTaskStep]


class VideoTaskCreateResponse(BaseModel):
    taskId: str
    status: TaskStatus
    pointsCost: int
    pointsBalance: int


class RegisterRequest(BaseModel):
    account: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\u4e00-\u9fa5]+$")
    email: str = Field(min_length=5, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class UserProfile(BaseModel):
    id: int
    account: str
    email: str
    points: int
    memberLevel: str = "FREE"
    memberExpiresAt: datetime | None = None
    isAdmin: bool = False


class AuthSession(BaseModel):
    token: str
    user: UserProfile


class BilibiliVideoFetchRequest(BaseModel):
    """B站视频信息接口入参。"""

    url: str = Field(min_length=1, description="B站视频链接或 BV/av 号")


class BilibiliVideoOwner(BaseModel):
    mid: int | None = None
    name: str | None = None
    face: str | None = None


class BilibiliVideoStat(BaseModel):
    view: int | None = None
    danmaku: int | None = None
    reply: int | None = None
    favorite: int | None = None
    coin: int | None = None
    share: int | None = None
    like: int | None = None


class BilibiliVideoPage(BaseModel):
    cid: int | None = None
    page: int | None = None
    part: str | None = None
    duration: int | None = None
    duration_text: str | None = None
    resolution: str | None = None
    url: str | None = None


class BilibiliVideoEntry(BaseModel):
    """每个分P 作为独立视频的完整信息；单P 视频时列表里只有 1 项。"""

    bvid: str | None = None
    aid: int | None = None
    url: str | None = None
    title: str | None = None
    cover: str | None = None
    cid: int | None = None
    page: int | None = None
    duration_seconds: int | None = None
    duration_text: str | None = None
    resolution: str | None = None


class BilibiliVideoFetchData(BaseModel):
    """与 test/video_info.json 保持一致的视频信息结构，单/多P 视频统一处理。"""

    source_url: str
    bvid: str | None = None
    aid: int | None = None
    title: str | None = None
    description: str | None = None
    cover: str | None = None
    duration_seconds: int | None = None
    duration_text: str | None = None
    pubdate: str | None = None
    page_count: int | None = None
    is_multipart: bool = False
    requested_page: int = 1
    first_cid: int | None = None
    resolution: str | None = None
    owner: BilibiliVideoOwner = Field(default_factory=BilibiliVideoOwner)
    stat: BilibiliVideoStat = Field(default_factory=BilibiliVideoStat)
    pages: list[BilibiliVideoPage] = Field(default_factory=list)
    videos: list[BilibiliVideoEntry] = Field(default_factory=list)


class BilibiliVideoFetchResponse(BaseModel):
    success: bool
    message: str
    data: BilibiliVideoFetchData
