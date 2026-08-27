"""抖音视频服务：直接复用 testDouYin.py 中已验证的分享链接解析器。"""

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from test.testDouYin import DouyinParser

from app.schemas import BilibiliVideoFetchData, BilibiliVideoOwner, BilibiliVideoPage


class DouyinError(RuntimeError):
    pass


@dataclass(frozen=True)
class DouyinVideo:
    video_id: str
    title: str
    cover: str | None
    duration: int | None
    author: str
    play_url: str
    source_url: str

    def as_preview(self) -> BilibiliVideoFetchData:
        return BilibiliVideoFetchData(
            source_url=self.source_url,
            bvid=self.video_id,
            title=self.title,
            description=self.title,
            cover=self.cover,
            duration_seconds=self.duration,
            duration_text=DouyinService.format_duration(self.duration),
            page_count=1,
            owner=BilibiliVideoOwner(name=self.author),
            pages=[BilibiliVideoPage(page=1, part=self.title, duration=self.duration)],
        )


class DouyinService:
    """将测试脚本的解析结果转换为 FastAPI 任务所需的视频信息。"""

    @staticmethod
    def is_douyin_url(value: str) -> bool:
        try:
            url = DouyinParser._extract_url(value)
            hostname = (urlparse(url).hostname or "").lower()
        except ValueError:
            return False
        return hostname == "douyin.com" or hostname.endswith(".douyin.com") or hostname.endswith("iesdouyin.com")

    async def fetch(self, share_text: str) -> DouyinVideo:
        try:
            # 每次任务创建独立 requests.Session，与 testDouYin.py 的执行方式完全一致。
            result = await asyncio.to_thread(DouyinParser().parse_share_link, share_text)
        except Exception as exc:
            raise DouyinError(str(exc) or "抖音视频解析失败") from exc

        try:
            return DouyinVideo(
                video_id=str(result["id"]),
                title=str(result["title"]),
                cover=result.get("cover") or None,
                duration=int(result["duration_seconds"]),
                author=str(result["author"]),
                play_url=str(result["video_url"]),
                source_url=str(result["share_url"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DouyinError("抖音解析结果缺少必要的视频信息") from exc

    @staticmethod
    def format_duration(seconds: int | None) -> str | None:
        if seconds is None:
            return None
        minutes, remaining = divmod(max(0, seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{remaining:02d}" if hours else f"{minutes:02d}:{remaining:02d}"
