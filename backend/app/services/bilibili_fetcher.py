"""B站视频信息获取服务，输出结构与 test/video_info.json 保持一致。"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.schemas import (
    BilibiliVideoEntry,
    BilibiliVideoFetchData,
    BilibiliVideoFetchRequest,
    BilibiliVideoOwner,
    BilibiliVideoPage,
    BilibiliVideoStat,
)


class BilibiliFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class BilibiliVideoContext:
    source_url: str
    bvid: str | None
    aid: int | None
    page: int


class BilibiliVideoFetcher:
    api_base = "https://api.bilibili.com"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }

    async def fetch(self, request: BilibiliVideoFetchRequest) -> BilibiliVideoFetchData:
        context = self.parse_video_url(request.url)
        detail = await self.fetch_video_detail(context)
        return self.build_video_info(context, detail)

    @staticmethod
    def parse_video_url(url: str) -> BilibiliVideoContext:
        source_url = url.strip()
        match = re.search(r"(BV[0-9A-Za-z]{10}|av\d+)", source_url, flags=re.IGNORECASE)
        if not match:
            raise BilibiliFetchError("请输入有效的 B站视频链接，例如 https://www.bilibili.com/video/BV...")

        page = 1
        try:
            page = max(1, int(parse_qs(urlparse(source_url).query).get("p", ["1"])[0]))
        except ValueError:
            page = 1

        identity = match.group(1)
        if identity.lower().startswith("av"):
            return BilibiliVideoContext(source_url=source_url, bvid=None, aid=int(identity[2:]), page=page)
        return BilibiliVideoContext(source_url=source_url, bvid=identity, aid=None, page=page)

    async def fetch_video_detail(self, context: BilibiliVideoContext) -> dict[str, Any]:
        params: dict[str, str | int] = {"bvid": context.bvid} if context.bvid else {"aid": context.aid or 0}
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
                response = await client.get(f"{self.api_base}/x/web-interface/view", params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BilibiliFetchError("访问B站视频信息接口失败，请稍后重试") from exc

        if payload.get("code") != 0:
            message = payload.get("message") or payload.get("msg") or "B站接口返回错误"
            raise BilibiliFetchError(str(message))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BilibiliFetchError("B站接口未返回有效的视频信息")
        return data

    @staticmethod
    def build_video_info(context: BilibiliVideoContext, data: dict[str, Any]) -> BilibiliVideoFetchData:
        pages = [p for p in (data.get("pages") or []) if isinstance(p, dict)]
        first_page = pages[0] if pages else {}
        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        pubdate = data.get("pubdate")
        formatted_pubdate = (
            datetime.fromtimestamp(pubdate).astimezone().strftime("%Y-%m-%d %H:%M:%S") if pubdate else None
        )

        bvid = data.get("bvid") or context.bvid
        aid = data.get("aid") or context.aid
        normalized_pages = [
            BilibiliVideoPage(
                cid=page.get("cid"),
                page=page.get("page"),
                part=page.get("part"),
                duration=page.get("duration"),
                duration_text=BilibiliVideoFetcher.format_duration(page.get("duration")),
                resolution=BilibiliVideoFetcher.format_resolution(page.get("dimension")),
                url=BilibiliVideoFetcher.build_page_url(bvid, aid, page.get("page") or idx + 1),
            )
            for idx, page in enumerate(pages)
        ]

        # 每个分P 作为独立视频的完整信息；单P 视频时列表里只有 1 项
        videos = [
            BilibiliVideoEntry(
                bvid=bvid,
                aid=aid,
                url=item.url,
                title=item.part or data.get("title"),
                cover=BilibiliVideoFetcher.normalize_media_url(data.get("pic")),
                cid=item.cid,
                page=item.page,
                duration_seconds=item.duration,
                duration_text=item.duration_text,
                resolution=item.resolution,
            )
            for item in normalized_pages
        ]

        return BilibiliVideoFetchData(
            source_url=context.source_url,
            bvid=bvid,
            aid=aid,
            title=data.get("title"),
            description=data.get("desc"),
            cover=BilibiliVideoFetcher.normalize_media_url(data.get("pic")),
            duration_seconds=data.get("duration"),
            duration_text=BilibiliVideoFetcher.format_duration(data.get("duration")),
            pubdate=formatted_pubdate,
            page_count=data.get("videos") or len(pages),
            is_multipart=len(pages) > 1,
            requested_page=context.page,
            first_cid=normalized_pages[0].cid if normalized_pages else None,
            resolution=normalized_pages[0].resolution if normalized_pages else None,
            owner=BilibiliVideoOwner(
                mid=owner.get("mid"),
                name=owner.get("name"),
                face=owner.get("face"),
            ),
            stat=BilibiliVideoStat(
                view=stat.get("view"),
                danmaku=stat.get("danmaku"),
                reply=stat.get("reply"),
                favorite=stat.get("favorite"),
                coin=stat.get("coin"),
                share=stat.get("share"),
                like=stat.get("like"),
            ),
            pages=normalized_pages,
            videos=videos,
        )

    @staticmethod
    def build_page_url(bvid: str | None, aid: int | None, page: int) -> str:
        """构造每个分P 的可播放链接，如 https://www.bilibili.com/video/BV...?p=3"""
        identity = bvid or f"av{aid}"
        return f"https://www.bilibili.com/video/{identity}?p={page}"

    @staticmethod
    def format_resolution(dimension: Any) -> str | None:
        if not isinstance(dimension, dict):
            return None
        width = dimension.get("width")
        height = dimension.get("height")
        if not width or not height:
            return None
        return f"{width}x{height}"

    @staticmethod
    def format_duration(seconds: int | None) -> str:
        total = int(seconds or 0)
        hours, remainder = divmod(total, 3600)
        minutes, remaining_seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}" if hours else f"{minutes:02d}:{remaining_seconds:02d}"

    @staticmethod
    def normalize_media_url(url: Any) -> str | None:
        """B站经常返回 http 图片地址，统一转换为可在 HTTPS 页面加载的地址。"""
        if not isinstance(url, str) or not url.strip():
            return None
        normalized = url.strip()
        if normalized.startswith("//"):
            return f"https:{normalized}"
        return re.sub(r"^http://", "https://", normalized, flags=re.IGNORECASE)
