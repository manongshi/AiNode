"""从 Bilibili 视频接口抓取视频关键信息，并以 JSON 形式返回。

接口: GET https://api.bilibili.com/x/web-interface/view?bvid={bvid}

同时支持两种链接：
1. 单个视频（分P数 = 1）  -> pages / videos 里只有 1 项
2. 多P视频 / 合集（分P数 > 1）-> pages / videos 里是完整的分P列表，
   每个分P都带独立可播放链接（?p=N）、标题、cid、时长、分辨率
"""

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import requests

SINGLE_VIDEO_URL = "https://www.bilibili.com/video/BV1jz8C6hEz5"
MULTI_VIDEO_URL = "https://www.bilibili.com/video/BV13iDvBVENd/"
API_BASE = "https://api.bilibili.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


def parse_video_identity(url: str) -> tuple[str | None, str | None, int]:
    """从链接中提取 (BV号, av号, 分P页码 p)，支持 ?p=N 指定具体分P。

    例如:
      https://www.bilibili.com/video/BV13iDvBVENd/        -> ("BV13iDvBVENd", None, 1)
      https://www.bilibili.com/video/BV13iDvBVENd?p=5     -> ("BV13iDvBVENd", None, 5)
      https://www.bilibili.com/video/av12345?p=2          -> (None, "12345", 2)
    """
    match = re.search(r"(BV[0-9A-Za-z]{10}|av\d+)", url, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"无法从链接中解析出视频 ID: {url}")

    identity = match.group(1)
    page = 1
    try:
        page = max(1, int(parse_qs(urlparse(url).query).get("p", ["1"])[0]))
    except ValueError:
        page = 1

    if identity.lower().startswith("av"):
        return None, identity[2:], page
    return identity, None, page


def format_duration(seconds: int) -> str:
    """把秒数格式化为 mm:ss 或 hh:mm:ss。"""
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_page_url(bvid: str | None, aid: int | None, page: int) -> str:
    """构造每个分P 的可播放链接，如 https://www.bilibili.com/video/BV...?p=3"""
    identity = bvid or f"av{aid}"
    return f"https://www.bilibili.com/video/{identity}?p={page}"


def format_resolution(dimension: dict | None) -> str | None:
    if not dimension:
        return None
    width = dimension.get("width")
    height = dimension.get("height")
    if not width or not height:
        return None
    return f"{width}x{height}"


def fetch_video_info(url: str) -> dict:
    """请求 B 站 view 接口并提取视频关键信息，单/多P 视频统一处理。"""
    bvid, aid, requested_page = parse_video_identity(url)
    params: dict = {"bvid": bvid} if bvid else {"aid": aid}

    resp = requests.get(
        f"{API_BASE}/x/web-interface/view",
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"B 站接口返回错误: {payload.get('message')}")

    d = payload["data"]
    bvid = d.get("bvid") or bvid
    aid = d.get("aid") or aid
    pages = [p for p in (d.get("pages") or []) if isinstance(p, dict)]
    owner = d.get("owner") or {}
    stat = d.get("stat") or {}

    pubdate = d.get("pubdate")
    pubtime = (
        datetime.fromtimestamp(pubdate, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        if pubdate
        else None
    )

    normalized_pages = [
        {
            "cid": p.get("cid"),
            "page": p.get("page"),
            "part": p.get("part"),
            "duration": p.get("duration"),
            "duration_text": format_duration(p.get("duration")),
            "resolution": format_resolution(p.get("dimension")),
            "url": build_page_url(bvid, aid, p.get("page") or idx + 1),
        }
        for idx, p in enumerate(pages)
    ]

    # 每个分P 作为独立视频的完整信息；单P 视频时列表里只有 1 项
    videos = [
        {
            "bvid": bvid,
            "aid": aid,
            "url": item["url"],
            "title": item["part"] or d.get("title"),
            "cover": d.get("pic"),
            "cid": item["cid"],
            "page": item["page"],
            "duration_seconds": item["duration"],
            "duration_text": item["duration_text"],
            "resolution": item["resolution"],
        }
        for item in normalized_pages
    ]

    first_page = normalized_pages[0] if normalized_pages else {}

    return {
        "source_url": url,
        "bvid": bvid,
        "aid": aid,
        "title": d.get("title"),
        "description": d.get("desc"),
        "cover": d.get("pic"),
        "duration_seconds": d.get("duration"),
        "duration_text": format_duration(d.get("duration")),
        "pubdate": pubtime,
        "page_count": d.get("videos") or len(pages),
        "is_multipart": len(pages) > 1,
        "requested_page": requested_page,
        "first_cid": first_page.get("cid"),
        "resolution": first_page.get("resolution"),
        "owner": {
            "mid": owner.get("mid"),
            "name": owner.get("name"),
            "face": owner.get("face"),
        },
        "stat": {
            "view": stat.get("view"),
            "danmaku": stat.get("danmaku"),
            "reply": stat.get("reply"),
            "favorite": stat.get("favorite"),
            "coin": stat.get("coin"),
            "share": stat.get("share"),
            "like": stat.get("like"),
        },
        # 分P 明细（含每个分P 的可播放链接）
        "pages": normalized_pages,
        # 统一的分P 列表：无论单/多P，都能按"独立视频"遍历
        "videos": videos,
    }


if __name__ == "__main__":
    start = time.perf_counter()

    results = {}
    for label, url in (("单视频", SINGLE_VIDEO_URL), ("多P视频", MULTI_VIDEO_URL)):
        info = fetch_video_info(url)
        results[label] = info
        print(f"===== {label}: {info['title']} (分P数: {info['page_count']}) =====")
        print(f"  总时长: {info['duration_text']} | 多P: {info['is_multipart']}")
        if info["videos"]:
            first = info["videos"][0]
            print(f"  第一个分P: {first['title']} | {first['duration_text']} | {first['url']}")
            if len(info["videos"]) > 1:
                last = info["videos"][-1]
                print(f"  最后一个分P: {last['title']} | {last['duration_text']} | {last['url']}")
        print()

    json_str = json.dumps(results, ensure_ascii=False, indent=2)
    print(json_str)

    # 同时写入一份 JSON 文件便于查看
    with open("video_info.json", "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"\nJSON 已写入 test/video_info.json，耗时 {time.perf_counter() - start:.2f}s")
