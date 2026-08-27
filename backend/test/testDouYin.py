"""独立测试抖音分享链接解析。

示例：
python testDouYin.py '3.07 :4pm o@q.Eu ... https://v.douyin.com/aS5ShUKsRyg/'
python testDouYin.py 'https://www.douyin.com/root/search?...&modal_id=xxx' --download
"""

import argparse
import base64
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


LOGGER = logging.getLogger("testDouYin")
URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}
MOBILE_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}


class DouyinParser:
    """解析分享文案、短链接和抖音视频页。"""

    API_URL = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"

    def __init__(self, download_dir: str = "downloads") -> None:
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = (10, 30)
        self.max_retries = 3

    def parse_share_link(self, share_text: str) -> dict[str, Any]:
        """仅传入抖音分享文案或短链接，自动完成后续全部解析。"""
        share_url = self._extract_url(share_text)
        resolved_url = self._resolve_redirect(share_url)
        video_id = self._extract_video_id(resolved_url)
        item_info = self._fetch_item_info(video_id, resolved_url)
        return self._build_result(item_info, video_id, share_url, resolved_url)

    def download(self, share_text: str) -> Path:
        result = self.parse_share_link(share_text)
        direct_url = result["video_url"]
        title = self._safe_filename(result["title"])
        path = self.download_dir / f"{title}.mp4"
        self._download_file(direct_url, path)
        return path

    @staticmethod
    def _extract_url(text: str) -> str:
        match = URL_PATTERN.search(text)
        if not match:
            raise ValueError("未找到有效的抖音分享链接")
        return match.group(0).strip().strip('"').strip("'").rstrip(").,;!?，。！？”’》】")

    def _resolve_redirect(self, share_url: str) -> str:
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    share_url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    headers=DEFAULT_HEADERS,
                )
                response.raise_for_status()
                return response.url
            except requests.RequestException as exc:
                if attempt == self.max_retries - 1:
                    raise ValueError(f"短链接解析失败：{exc}") from exc
                time.sleep(2**attempt)
        raise ValueError("短链接解析失败")

    @staticmethod
    def _extract_video_id(url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("modal_id", "item_ids", "group_id", "aweme_id"):
            value = (query.get(key) or [""])[0]
            match = re.search(r"\d{8,24}", value)
            if match:
                return match.group(0)
        for pattern in (r"/video/(\d{8,24})", r"/note/(\d{8,24})", r"/(\d{8,24})(?:/|$)"):
            match = re.search(pattern, parsed.path)
            if match:
                return match.group(1)
        fallback = re.search(r"\d{15,24}", url)
        if fallback:
            return fallback.group(0)
        raise ValueError("无法从链接中提取视频 ID")

    def _fetch_item_info(self, video_id: str, resolved_url: str) -> dict[str, Any]:
        try:
            return self._fetch_via_api(video_id)
        except Exception as exc:
            LOGGER.warning("公开接口未返回视频数据，改用分享页解析：%s", exc)
            return self._fetch_via_share_page(video_id, resolved_url)

    def _fetch_via_api(self, video_id: str) -> dict[str, Any]:
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(self.API_URL, params={"item_ids": video_id}, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                items = payload.get("item_list") if isinstance(payload, dict) else None
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    return items[0]
                raise ValueError("公开接口返回空数据")
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)
        raise ValueError("公开接口请求失败")

    def _fetch_via_share_page(self, video_id: str, resolved_url: str) -> dict[str, Any]:
        parsed = urlparse(resolved_url)
        share_url = resolved_url if "iesdouyin.com" in (parsed.hostname or "") else f"https://www.iesdouyin.com/share/video/{video_id}/"
        response = self.session.get(share_url, headers=MOBILE_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        html = response.text or ""
        if "Please wait..." in html and "wci=" in html and "cs=" in html:
            html = self._solve_waf_and_retry(html, share_url)
        router_data = self._extract_router_data(html)
        loader_data = router_data.get("loaderData") if isinstance(router_data, dict) else None
        if isinstance(loader_data, dict):
            for node in loader_data.values():
                video_info = node.get("videoInfoRes") if isinstance(node, dict) else None
                items = video_info.get("item_list") if isinstance(video_info, dict) else None
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    return items[0]
        raise ValueError("分享页未找到视频信息")

    def _solve_waf_and_retry(self, html: str, page_url: str) -> str:
        match = re.search(r'wci="([^"]+)"\s*,\s*cs="([^"]+)"', html)
        if not match:
            return html
        cookie_name, challenge_blob = match.groups()
        try:
            challenge = json.loads(self._decode_base64(challenge_blob).decode("utf-8"))
            prefix = self._decode_base64(challenge["v"]["a"])
            expected = self._decode_base64(challenge["v"]["c"]).hex()
        except (KeyError, ValueError, UnicodeDecodeError):
            return html
        for candidate in range(1_000_001):
            if hashlib.sha256(prefix + str(candidate).encode()).hexdigest() != expected:
                continue
            challenge["d"] = base64.b64encode(str(candidate).encode()).decode()
            cookie_value = base64.b64encode(json.dumps(challenge, separators=(",", ":")).encode()).decode()
            self.session.cookies.set(cookie_name, cookie_value, domain=urlparse(page_url).hostname, path="/")
            return self.session.get(page_url, headers=MOBILE_HEADERS, timeout=self.timeout).text or ""
        return html

    @staticmethod
    def _extract_router_data(html: str) -> dict[str, Any]:
        marker = "window._ROUTER_DATA = "
        start = html.find(marker)
        if start < 0:
            return {}
        index = start + len(marker)
        while index < len(html) and html[index].isspace():
            index += 1
        if index >= len(html) or html[index] != "{":
            return {}
        depth = 0
        in_string = False
        escaped = False
        for cursor in range(index, len(html)):
            char = html[cursor]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(html[index : cursor + 1])
                    except ValueError:
                        return {}
                    return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        normalized = value.replace("-", "+").replace("_", "/")
        return base64.b64decode(normalized + "=" * (-len(normalized) % 4))

    @staticmethod
    def _safe_filename(title: str) -> str:
        cleaned = re.sub(r'[\\/*?:"<>|\n\r\t#@]', "_", title).strip("_. ")[:60]
        return re.sub(r"_+", "_", cleaned) or "douyin_video"

    @staticmethod
    def _download_file(url: str, filepath: Path) -> None:
        with requests.get(url, headers=MOBILE_HEADERS, stream=True, timeout=(10, 90), allow_redirects=True) as response:
            response.raise_for_status()
            temporary = filepath.with_suffix(".part")
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        output.write(chunk)
            temporary.replace(filepath)

    @staticmethod
    def _build_result(item: dict[str, Any], video_id: str, share_url: str, resolved_url: str) -> dict[str, Any]:
        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        play_urls = (video.get("play_addr") or {}).get("url_list") if isinstance(video.get("play_addr"), dict) else []
        cover_urls = (video.get("cover") or {}).get("url_list") if isinstance(video.get("cover"), dict) else []
        if not isinstance(play_urls, list) or not play_urls:
            raise ValueError("未找到视频播放地址")
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        duration = int(video.get("duration") or 0) // 1000
        return {
            "id": video_id,
            "title": str(item.get("desc") or f"抖音视频_{video_id}"),
            "author": str(author.get("nickname") or "抖音用户"),
            "duration_seconds": duration,
            "cover": cover_urls[0] if isinstance(cover_urls, list) and cover_urls else "",
            "video_url": str(play_urls[0]).replace("playwm", "play"),
            "share_url": share_url,
            "resolved_url": resolved_url,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="测试抖音分享文案或链接解析")
    parser.add_argument("url", nargs="?", help="抖音分享文案、短链接或视频链接")
    parser.add_argument("--download", action="store_true", help="解析完成后下载 MP4 到 downloads 目录")
    arguments = parser.parse_args()
    source = arguments.url or input("请粘贴抖音分享文案或视频链接：").strip()
    if not source:
        raise SystemExit("未输入抖音分享文案或视频链接")
    douyin = DouyinParser()
    result = douyin.parse_share_link(source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.download:
        print(f"已下载：{douyin.download(source)}")


if __name__ == "__main__":
    main()
