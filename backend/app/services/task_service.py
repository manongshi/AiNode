"""视频笔记异步任务、步骤状态和 SSE 订阅管理。"""

import asyncio
import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.schemas import (
    BilibiliVideoFetchRequest,
    CollectionVideo,
    NoteGenerateResponse,
    SubtitleLine,
    SubtitleResponse,
    VideoCollection,
    VideoInfo,
    VideoTaskCreateRequest,
    VideoTaskResponse,
    VideoTaskStep,
)
from app.services.ai import AIService
from app.services.bilibili import BilibiliService, BilibiliSubtitleResult, BilibiliSubtitleUnavailableError
from app.services.bilibili_fetcher import BilibiliVideoFetcher
from app.services.chunking import split_text
from app.services.douyin import DouyinService
from app.services.note_repository import NoteRepository
from app.services.transcription import AudioTranscriptionService
from app.services.user_repository import UserRepository


TASK_STEPS = [
    ("analyze_video", "解析视频"),
    ("get_video_info", "获取视频信息"),
    ("get_subtitle", "检测字幕"),
    ("download_subtitle", "下载字幕"),
    ("translate_subtitle", "翻译字幕"),
    ("clean_subtitle", "清洗字幕"),
    ("chunk_text", "文本切片"),
    ("ai_analysis", "AI 内容分析"),
    ("generate_note", "生成笔记"),
    ("save_note", "保存笔记"),
]


@dataclass
class TaskRecord:
    state: VideoTaskResponse
    request: VideoTaskCreateRequest
    user_id: int
    points_cost: int
    result: NoteGenerateResponse | None = None
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)


class VideoTaskService:
    """第一版任务服务：使用进程内状态，接口保持可替换为 Redis 的形式。"""

    def __init__(
        self,
        bilibili_service: BilibiliService,
        video_fetcher: BilibiliVideoFetcher,
        transcription_service: AudioTranscriptionService,
        ai_service: AIService,
        note_repository: NoteRepository,
        douyin_service: DouyinService,
        user_repository: UserRepository,
    ) -> None:
        self.bilibili_service = bilibili_service
        self.video_fetcher = video_fetcher
        self.transcription_service = transcription_service
        self.ai_service = ai_service
        self.note_repository = note_repository
        self.douyin_service = douyin_service
        self.user_repository = user_repository
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, request: VideoTaskCreateRequest, user_id: int, points_cost: int) -> tuple[VideoTaskResponse, int]:
        task_id = uuid.uuid4().hex
        if points_cost > 0:
            points_balance = await self.user_repository.consume_points(
                user_id,
                points_cost,
                task_id,
                f"生成视频笔记（{points_cost} 积分）",
            )
        else:
            points_balance = 0
        state = VideoTaskResponse(
            taskId=task_id,
            status="pending",
            videoUrl=request.videoUrl,
            createdAt=self._now(),
            steps=[VideoTaskStep(key=key, label=label) for key, label in TASK_STEPS],
        )
        record = TaskRecord(state=state, request=request, user_id=user_id, points_cost=points_cost)
        async with self._lock:
            self._tasks[task_id] = record
        asyncio.create_task(self._run(record), name=f"video-note-{task_id}")
        return self._snapshot(record), points_balance

    async def get_task(self, task_id: str, user_id: int) -> VideoTaskResponse | None:
        async with self._lock:
            record = self._tasks.get(task_id)
            return self._snapshot(record) if record and record.user_id == user_id else None

    async def get_note(self, task_id: str, user_id: int) -> NoteGenerateResponse | None:
        async with self._lock:
            record = self._tasks.get(task_id)
            return copy.deepcopy(record.result) if record and record.user_id == user_id and record.result else None

    async def subscribe(self, task_id: str, user_id: int) -> asyncio.Queue[dict[str, Any]] | None:
        async with self._lock:
            record = self._tasks.get(task_id)
            if not record or record.user_id != user_id:
                return None
            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
            record.subscribers.add(queue)
            queue.put_nowait(self._snapshot(record).model_dump())
            return queue

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            record = self._tasks.get(task_id)
            if record:
                record.subscribers.discard(queue)

    async def _run(self, record: TaskRecord) -> None:
        try:
            await self._update_step(record, "analyze_video", "running", 10, "正在解析视频链接")
            is_douyin = self.douyin_service.is_douyin_url(record.request.videoUrl)
            if not is_douyin:
                self.video_fetcher.parse_video_url(record.request.videoUrl)
            await self._update_step(record, "analyze_video", "success", 100, "视频链接解析完成")

            await self._update_step(record, "get_video_info", "running", 20, "正在读取视频标题和封面")
            selected_entries = []
            video_data = None
            if is_douyin:
                douyin_video = await self.douyin_service.fetch(record.request.videoUrl)
                record.state.videoTitle = douyin_video.title
            else:
                video_data = await self.video_fetcher.fetch(BilibiliVideoFetchRequest(url=record.request.videoUrl))
                record.state.videoTitle = video_data.title
                selected_entries = self._select_bilibili_entries(video_data, record.request.videoUrls)
            await self._update_step(record, "get_video_info", "success", 100, "视频信息获取完成")

            await self._update_step(record, "get_subtitle", "running", 25, "正在检测原始字幕")
            collection = None
            note_source = ""
            if is_douyin:
                await self._update_step(record, "get_subtitle", "skipped", 100, "抖音未提供公开字幕，改用视频音频转写")
                await self._update_step(record, "download_subtitle", "running", 10, "正在下载视频音频并转写")
                transcript = await self.transcription_service.transcribe_remote_video(
                    {
                        "bvid": douyin_video.video_id,
                        "title": douyin_video.title,
                        "cover": douyin_video.cover,
                        "duration": douyin_video.duration,
                        "page": 1,
                        "platform": "douyin",
                        "sourceUrl": douyin_video.source_url,
                    },
                    douyin_video.play_url,
                )
                await self._update_step(record, "download_subtitle", "success", 100, f"音频转写完成，共 {len(transcript.lines)} 条文字")
            else:
                transcript, collection, note_source = await self._collect_bilibili_transcripts(
                    record,
                    video_data,
                    selected_entries,
                )

            await self._update_step(record, "translate_subtitle", "running", 10, "正在判断字幕语言")
            await self._update_step(record, "translate_subtitle", "skipped", 100, "当前版本保留原字幕语言")

            await self._update_step(record, "clean_subtitle", "running", 20, "正在去除重复与空白字幕")
            transcript = self._clean_transcript(transcript)
            await self._update_step(record, "clean_subtitle", "success", 100, f"字幕清洗完成，保留 {len(transcript.lines)} 条")

            await self._update_step(record, "chunk_text", "running", 10, "正在按内容长度切片")
            chunks = split_text(note_source or transcript.text)
            if not chunks:
                raise RuntimeError("清洗后的字幕为空，无法生成笔记")
            await self._update_step(record, "chunk_text", "success", 100, f"文本已切分为 {len(chunks)} 段")

            if len(chunks) == 1:
                await self._update_step(record, "ai_analysis", "skipped", 100, "文本较短，直接生成笔记")
                note_input = chunks[0]
            else:
                await self._update_step(record, "ai_analysis", "running", 0, f"正在分析 0/{len(chunks)} 个文本分段")

                async def on_analysis_progress(completed: int, total: int) -> None:
                    progress = int(completed / total * 90)
                    await self._update_step(
                        record,
                        "ai_analysis",
                        "running",
                        progress,
                        f"正在分析 {completed}/{total} 个文本分段",
                    )

                summaries = await self.ai_service.analyze_chunks(
                    chunks,
                    on_analysis_progress,
                    provider=record.request.modelProvider,
                )
                note_input = await self.ai_service.merge_summaries(summaries, record.request.modelProvider)
                await self._update_step(record, "ai_analysis", "success", 100, "AI 内容分析完成")

            await self._update_step(record, "generate_note", "running", 15, "正在组织最终笔记")
            note, mind_map, content_type = await self.ai_service.create_final_note(
                note_input,
                record.request.style,
                record.request.extraInstruction,
                record.request.modelProvider,
            )
            await self._update_step(record, "generate_note", "success", 100, "笔记生成完成")

            subtitle = SubtitleResponse(
                video=VideoInfo(**transcript.video),
                lines=[SubtitleLine(**line) for line in transcript.lines],
                text=transcript.text,
                source=transcript.source,
            )
            record.result = NoteGenerateResponse(
                video=subtitle.video,
                subtitle=subtitle,
                note=note.strip(),
                mindMap=mind_map,
                contentType=content_type,
                chunk_count=len(chunks),
                collection=collection,
            )
            await self._update_step(record, "save_note", "running", 30, "正在保存本次笔记结果")
            await self.note_repository.save(
                record.user_id,
                record.state.taskId,
                record.request,
                record.result,
                record.state.createdAt,
            )
            await self._update_step(record, "save_note", "success", 100, "笔记已保存至当前任务")
            record.state.status = "success"
            record.state.progress = 100
            record.state.finishedAt = self._now()
            await self._publish(record)
        except Exception as exc:
            active_step = record.state.currentStep
            if active_step:
                await self._update_step(record, active_step, "failed", 100, str(exc))
            record.state.status = "failed"
            record.state.errorMessage = str(exc)
            record.state.finishedAt = self._now()
            if record.points_cost > 0:
                try:
                    await self.user_repository.refund_points(record.user_id, record.points_cost, record.state.taskId)
                except Exception:
                    record.state.errorMessage = f"{record.state.errorMessage}；积分退回失败，请联系管理员"
            await self._publish(record)

    async def _collect_bilibili_transcripts(
        self,
        record: TaskRecord,
        video_data,
        entries,
    ) -> tuple[BilibiliSubtitleResult, VideoCollection | None, str]:
        """按选中的分 P 逐个获取字幕，并拼成一篇带清晰分段的合集笔记。"""
        if not entries:
            raise RuntimeError("没有找到需要处理的分 P，请重新读取视频信息后再试")

        all_lines: list[dict[str, Any]] = []
        note_sections: list[str] = []
        subtitle_sources: list[str] = []
        elapsed = 0.0
        total = len(entries)

        for index, entry in enumerate(entries, start=1):
            page = entry.page or index
            entry_title = entry.title or f"第 {page} P"
            label = f"第 {page} P（{index}/{total}）"
            await self._update_step(record, "get_subtitle", "running", int((index - 1) / total * 90), f"正在检测{label}的字幕")
            try:
                piece = await self.bilibili_service.fetch_subtitle(entry.url)
                await self._update_step(record, "get_subtitle", "running", int(index / total * 90), f"{label}已读取公开字幕")
                await self._update_step(record, "download_subtitle", "running", int((index - 1) / total * 90), f"正在整理{label}的字幕")
            except BilibiliSubtitleUnavailableError:
                await self._update_step(record, "get_subtitle", "running", int(index / total * 90), f"{label}没有公开字幕，改用音频转写")
                await self._update_step(record, "download_subtitle", "running", int((index - 1) / total * 90), f"正在下载{label}的视频音频并转写")
                piece = await self.transcription_service.transcribe_bilibili_video(entry.url)

            piece.video.update(
                {
                    "bvid": entry.bvid or video_data.bvid or "",
                    "title": entry_title,
                    "cover": entry.cover or video_data.cover,
                    "duration": entry.duration_seconds,
                    "page": page,
                    "platform": "bilibili",
                    "sourceUrl": entry.url,
                }
            )
            piece = self._clean_transcript(piece)
            subtitle_sources.append(piece.source)
            note_sections.append(f"【第 {page} P：{entry_title}】\n{piece.text}")

            for line in piece.lines:
                start = float(line.get("start") or 0) + elapsed
                end = float(line.get("end") or 0) + elapsed
                all_lines.append({**line, "start": start, "end": end})

            elapsed += float(entry.duration_seconds or self._transcript_duration(piece))
            await self._update_step(record, "download_subtitle", "running", int(index / total * 90), f"{label}字幕已整理")

        await self._update_step(record, "get_subtitle", "success", 100, f"已完成 {total} 个视频的字幕检测")
        await self._update_step(record, "download_subtitle", "success", 100, f"已合并 {total} 个视频，共 {len(all_lines)} 条字幕")

        source_entries = [entry for entry in video_data.videos if entry.url] or entries
        is_collection = video_data.is_multipart
        total_duration = sum(int(entry.duration_seconds or 0) for entry in source_entries)
        selected_duration = sum(int(entry.duration_seconds or 0) for entry in entries)
        collection = None
        if is_collection:
            collection = VideoCollection(
                title=video_data.title or "未命名合集",
                sourceUrl=record.request.videoUrl,
                cover=video_data.cover,
                videoCount=len(source_entries),
                totalDuration=total_duration,
                generatedPages=[entry.page or position for position, entry in enumerate(entries, start=1)],
                videos=[
                    CollectionVideo(
                        bvid=entry.bvid or video_data.bvid or "",
                        title=entry.title or f"第 {entry.page or position} P",
                        cover=entry.cover or video_data.cover,
                        duration=entry.duration_seconds,
                        page=entry.page or position,
                        sourceUrl=entry.url,
                    )
                    for position, entry in enumerate(source_entries, start=1)
                ],
            )

        representative = {
            "bvid": video_data.bvid or entries[0].bvid or "",
            "title": video_data.title or entries[0].title or "未命名视频",
            "cover": video_data.cover or entries[0].cover,
            "duration": selected_duration or entries[0].duration_seconds,
            "page": 1,
            "platform": "bilibili",
            "sourceUrl": record.request.videoUrl,
        }
        source = "bilibili_subtitle" if all(item == "bilibili_subtitle" for item in subtitle_sources) else "audio_transcription"
        transcript = BilibiliSubtitleResult(
            video=representative,
            lines=all_lines,
            text="\n".join(str(line["content"]) for line in all_lines),
            source=source,
        )
        return transcript, collection, "\n\n".join(note_sections)

    @staticmethod
    def _select_bilibili_entries(video_data, requested_urls: list[str]):
        entries = [entry for entry in video_data.videos if entry.url]
        if not entries:
            return []

        selected_urls = {url.strip() for url in requested_urls if url and url.strip()}
        if selected_urls:
            selected = [entry for entry in entries if entry.url in selected_urls]
            if selected:
                return selected
            raise RuntimeError("所选视频不属于当前 B 站合集，请重新读取视频信息")

        # 打开一个多 P 合集时默认处理完整合集；明确带 ?p=N 的链接则只处理该分 P。
        if video_data.is_multipart and video_data.requested_page == 1:
            return entries
        return [entry for entry in entries if entry.page == video_data.requested_page] or [entries[0]]

    @staticmethod
    def _transcript_duration(transcript: BilibiliSubtitleResult) -> float:
        return max((float(line.get("end") or 0) for line in transcript.lines), default=0.0)

    async def _update_step(
        self,
        record: TaskRecord,
        key: str,
        status: str,
        progress: int,
        message: str,
    ) -> None:
        step = next(item for item in record.state.steps if item.key == key)
        step.status = status  # type: ignore[assignment]
        step.progress = max(0, min(100, progress))
        step.message = message
        record.state.status = "running"
        record.state.currentStep = key
        record.state.progress = self._calculate_progress(record.state.steps)
        await self._publish(record)

    @staticmethod
    def _clean_transcript(transcript: BilibiliSubtitleResult) -> BilibiliSubtitleResult:
        cleaned_lines: list[dict[str, Any]] = []
        previous = ""
        for line in transcript.lines:
            content = " ".join(str(line.get("content") or "").split())
            if not content or content == previous:
                continue
            cleaned_lines.append({**line, "content": content})
            previous = content
        transcript.lines = cleaned_lines
        transcript.text = "\n".join(str(line["content"]) for line in cleaned_lines)
        return transcript

    @staticmethod
    def _calculate_progress(steps: list[VideoTaskStep]) -> int:
        completed = sum(step.progress for step in steps)
        return int(completed / len(steps)) if steps else 0

    async def _publish(self, record: TaskRecord) -> None:
        snapshot = self._snapshot(record).model_dump()
        for queue in tuple(record.subscribers):
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull:
                record.subscribers.discard(queue)

    @staticmethod
    def _snapshot(record: TaskRecord | None) -> VideoTaskResponse:
        if record is None:
            raise ValueError("任务不存在")
        return VideoTaskResponse.model_validate(record.state.model_dump())

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
