"""视频音频下载与 MLX Whisper 本地转写服务。"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any

import asyncio
import httpx

from app.config import settings
from app.schemas import BilibiliVideoFetchRequest
from app.services.bilibili import BilibiliSubtitleResult
from app.services.bilibili_fetcher import BilibiliFetchError, BilibiliVideoFetcher


class AudioTranscriptionError(RuntimeError):
    pass


class AudioTranscriptionService:
    """无字幕时下载音频，并交给 MLX Whisper 在本地生成文字。"""

    _MODEL_LOCK = Lock()

    def __init__(self, video_fetcher: BilibiliVideoFetcher) -> None:
        self.video_fetcher = video_fetcher

    async def transcribe_bilibili_video(self, url: str) -> BilibiliSubtitleResult:
        try:
            video_info = await self.video_fetcher.fetch(BilibiliVideoFetchRequest(url=url))
        except BilibiliFetchError as exc:
            raise AudioTranscriptionError(str(exc)) from exc

        lines = await asyncio.to_thread(self._download_and_transcribe, url)
        if not lines:
            raise AudioTranscriptionError("MLX Whisper 音频转写未返回任何文字")

        selected_page = next((page for page in video_info.pages if page.page == self._get_page_number(url)), None)
        video = {
            "bvid": video_info.bvid or (f"av{video_info.aid}" if video_info.aid else ""),
            "title": video_info.title or "未命名视频",
            "cover": video_info.cover,
            "duration": video_info.duration_seconds,
            "page": selected_page.page if selected_page and selected_page.page else self._get_page_number(url),
        }
        return BilibiliSubtitleResult(
            video=video,
            lines=lines,
            text="\n".join(str(line["content"]) for line in lines),
            source="audio_transcription",
        )

    async def transcribe_remote_video(self, video: dict, media_url: str) -> BilibiliSubtitleResult:
        """下载外部视频播放流，并通过 MLX Whisper 转写其中的人声音轨。"""
        lines = await asyncio.to_thread(self._download_remote_and_transcribe, media_url)
        if not lines:
            raise AudioTranscriptionError("MLX Whisper 音频转写未返回任何文字")
        return BilibiliSubtitleResult(
            video=video,
            lines=lines,
            text="\n".join(str(line["content"]) for line in lines),
            source="audio_transcription",
        )

    def _download_and_transcribe(self, url: str) -> list[dict[str, float | str]]:
        with TemporaryDirectory(prefix="ainote-audio-") as directory:
            audio_path = self._download_audio(url, Path(directory))
            return self._transcribe_audio(audio_path)

    def _download_remote_and_transcribe(self, media_url: str) -> list[dict[str, float | str]]:
        with TemporaryDirectory(prefix="ainote-remote-video-") as directory:
            output_dir = Path(directory)
            media_path = output_dir / "source.mp4"
            try:
                with httpx.Client(timeout=90, follow_redirects=True) as client:
                    with client.stream("GET", media_url, headers={"Referer": "https://www.douyin.com/"}) as response:
                        response.raise_for_status()
                        with media_path.open("wb") as output:
                            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                                output.write(chunk)
            except httpx.HTTPError as exc:
                raise AudioTranscriptionError("视频音频下载失败") from exc
            audio_path = self._extract_audio(media_path, output_dir)
            return self._transcribe_audio(audio_path)

    @staticmethod
    def _extract_audio(media_path: Path, output_dir: Path) -> Path:
        """转换为 Whisper 适合处理的 16kHz 单声道 MP3。"""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise AudioTranscriptionError("本地转写前需要使用 ffmpeg 将视频音轨转换为 MP3")

        audio_path = output_dir / "mlx-whisper-audio.mp3"
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(media_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-b:a",
                    "64k",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(audio_path),
                ],
                capture_output=True,
                check=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioTranscriptionError("视频音轨转换超时") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise AudioTranscriptionError("视频音轨转换为 MP3 失败") from exc

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise AudioTranscriptionError("视频音轨转换后没有生成可用的 MP3 文件")
        return audio_path

    @staticmethod
    def _get_page_number(url: str) -> int:
        from urllib.parse import parse_qs, urlparse

        try:
            return max(1, int(parse_qs(urlparse(url).query).get("p", ["1"])[0]))
        except ValueError:
            return 1

    def _download_audio(self, url: str, output_dir: Path) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:
            raise AudioTranscriptionError("缺少 yt-dlp 依赖，请先安装后端 requirements.txt") from exc

        downloaded_files: list[Path] = []

        def on_progress(event: dict) -> None:
            if event.get("status") == "finished" and event.get("filename"):
                downloaded_files.append(Path(event["filename"]))

        options: dict = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "outtmpl": str(output_dir / "source.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "proxy": settings.bilibili_proxy,
            "http_headers": {
                "Referer": settings.bilibili_referer,
                "User-Agent": settings.bilibili_user_agent,
                "Accept-Language": settings.bilibili_accept_language,
            },
            "progress_hooks": [on_progress],
        }
        cookie_file = self._resolve_cookie_file(output_dir)
        if cookie_file:
            options["cookiefile"] = str(cookie_file)

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.extract_info(url, download=True)
        except Exception as exc:
            raise AudioTranscriptionError("B站音频下载失败；受限视频请配置 BILIBILI_COOKIE_FILE") from exc

        source_path = downloaded_files[-1] if downloaded_files else None
        if not source_path or not source_path.exists():
            candidates = [path for path in output_dir.glob("source.*") if path.is_file()]
            source_path = candidates[0] if candidates else None
        if not source_path:
            raise AudioTranscriptionError("音频下载完成后没有找到音频文件")
        return self._extract_audio(source_path, output_dir)

    @staticmethod
    def _resolve_cookie_file(output_dir: Path) -> Path | None:
        """优先使用标准 Netscape Cookie 文件，并兼容旧的环境变量 Cookie。"""
        configured_file = Path(settings.bilibili_cookie_file).expanduser()
        if settings.bilibili_cookie_file and configured_file.is_file():
            return configured_file

        raw_cookie = settings.bilibili_cookie.strip()
        if not raw_cookie:
            return None

        cookie_lines = ["# Netscape HTTP Cookie File"]
        for item in raw_cookie.split(";"):
            name, separator, value = item.strip().partition("=")
            if not separator or not name:
                continue
            cookie_lines.append(f".bilibili.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}")

        if len(cookie_lines) == 1:
            return None

        cookie_file = output_dir / "bilibili-cookies.txt"
        cookie_file.write_text("\n".join(cookie_lines) + "\n", encoding="utf-8")
        return cookie_file

    def _transcribe_audio(self, audio_path: Path) -> list[dict[str, float | str]]:
        try:
            import mlx_whisper
        except ImportError as exc:
            raise AudioTranscriptionError("缺少 mlx-whisper 依赖，请先安装后端 requirements.txt") from exc

        try:
            with self._MODEL_LOCK:
                result = mlx_whisper.transcribe(
                    str(audio_path),
                    path_or_hf_repo=settings.mlx_whisper_model,
                    language=settings.mlx_whisper_language or None,
                    task="transcribe",
                    verbose=False,
                )
        except Exception as exc:
            raise AudioTranscriptionError(
                f"MLX Whisper 本地转写失败，当前模型：{settings.mlx_whisper_model}"
            ) from exc

        if not isinstance(result, dict):
            raise AudioTranscriptionError("MLX Whisper 返回格式错误")
        return self._parse_mlx_result(result)

    @staticmethod
    def _parse_mlx_result(result: dict[str, Any]) -> list[dict[str, float | str]]:
        lines: list[dict[str, float | str]] = []
        segments = result.get("segments") or []
        if isinstance(segments, list):
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                content = str(segment.get("text") or "").strip()
                if not content:
                    continue
                lines.append(
                    {
                        "start": AudioTranscriptionService._seconds(segment.get("start")),
                        "end": AudioTranscriptionService._seconds(segment.get("end")),
                        "content": content,
                    }
                )

        if not lines:
            content = str(result.get("text") or "").strip()
            if content:
                lines.append({"start": 0.0, "end": 0.0, "content": content})
        return lines

    @staticmethod
    def _seconds(value: Any) -> float:
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return 0.0
