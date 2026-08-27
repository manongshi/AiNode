import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


class BilibiliError(RuntimeError):
    pass


class BilibiliSubtitleUnavailableError(BilibiliError):
    """视频没有公开字幕时触发，调用方可降级为音频转写。"""


@dataclass
class BilibiliSubtitleResult:
    video: dict[str, Any]
    lines: list[dict[str, Any]]
    text: str
    source: str = "bilibili_subtitle"


class BilibiliService:
    api_base = "https://api.bilibili.com"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }

    async def fetch_subtitle(self, url: str) -> BilibiliSubtitleResult:
        bvid, aid, page_number = self._parse_video_url(url)
        async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
            view = await self._get_json(
                client,
                "/x/web-interface/view",
                {"bvid": bvid} if bvid else {"aid": aid},
            )
            data = view.get("data") or {}
            pages = data.get("pages") or []
            if not pages:
                raise BilibiliError("没有找到视频分 P 信息")

            index = max(0, min(page_number - 1, len(pages) - 1))
            page = pages[index]
            cid = page.get("cid")
            if not cid:
                raise BilibiliError("没有找到视频的 cid 信息")

            player_params: dict[str, Any] = {"cid": cid}
            if bvid:
                player_params["bvid"] = bvid
            else:
                player_params["avid"] = aid
            player = await self._get_json(client, "/x/player/v2", player_params)
            player_data = player.get("data") or {}
            subtitle_info = player_data.get("subtitle") or {}
            subtitles = subtitle_info.get("subtitles") or []
            if not subtitles:
                raise BilibiliSubtitleUnavailableError("这个视频没有可读取的字幕")

            subtitle_url = subtitles[0].get("subtitle_url") or subtitles[0].get("subtitle_url_v2")
            if not subtitle_url:
                raise BilibiliError("字幕地址为空，无法读取字幕内容")
            if subtitle_url.startswith("//"):
                subtitle_url = f"https:{subtitle_url}"
            elif subtitle_url.startswith("/"):
                subtitle_url = f"https://api.bilibili.com{subtitle_url}"

            subtitle_payload = await self._get_external_json(client, subtitle_url)
            raw_lines = subtitle_payload.get("body") or subtitle_payload.get("subtitles") or []
            lines = self._normalize_lines(raw_lines)
            if not lines:
                raise BilibiliSubtitleUnavailableError("字幕内容为空")

            video = {
                "bvid": bvid or f"av{aid}",
                "title": data.get("title") or "未命名视频",
                "cover": self._normalize_media_url(data.get("pic")),
                "duration": data.get("duration"),
                "page": index + 1,
            }
            return BilibiliSubtitleResult(video=video, lines=lines, text="\n".join(line["content"] for line in lines))

    async def _get_json(self, client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await client.get(f"{self.api_base}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BilibiliError("访问 B 站接口失败，请稍后重试") from exc
        if payload.get("code") not in (0, None):
            message = payload.get("message") or payload.get("msg") or "B 站接口返回错误"
            raise BilibiliError(str(message))
        return payload

    async def _get_external_json(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BilibiliError("字幕地址无法访问，请确认视频字幕可公开读取") from exc
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _parse_video_url(url: str) -> tuple[str | None, str | None, int]:
        match = re.search(r"(BV[0-9A-Za-z]{10}|av\d+)", url, flags=re.IGNORECASE)
        if not match:
            raise BilibiliError("请输入有效的 B 站视频链接，例如 https://www.bilibili.com/video/BV...")
        identity = match.group(1)
        page_number = 1
        try:
            page_value = parse_qs(urlparse(url).query).get("p", ["1"])[0]
            page_number = max(1, int(page_value))
        except ValueError:
            page_number = 1
        if identity.lower().startswith("av"):
            return None, identity[2:], page_number
        return identity, None, page_number

    @staticmethod
    def _normalize_lines(raw_lines: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in raw_lines:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("text") or "").strip()
            if not content:
                continue
            try:
                start = float(item.get("from", item.get("start", 0)))
                end = float(item.get("to", item.get("end", start)))
            except (TypeError, ValueError):
                start, end = 0.0, 0.0
            normalized.append({"start": start, "end": end, "content": content})
        return normalized

    @staticmethod
    def _normalize_media_url(url: Any) -> str | None:
        if not isinstance(url, str) or not url.strip():
            return None
        normalized = url.strip()
        if normalized.startswith("//"):
            return f"https:{normalized}"
        return re.sub(r"^http://", "https://", normalized, flags=re.IGNORECASE)
