"""按用户隔离的 MySQL 笔记持久化仓库。"""

import asyncio
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pymysql

from app.config import settings
from app.schemas import (
    CollectionVideo,
    NoteGenerateResponse,
    SavedNoteGroup,
    SavedNoteSummary,
    SubtitleLine,
    SubtitleResponse,
    VideoCollection,
    VideoInfo,
    VideoTaskCreateRequest,
)


class NoteRepository:
    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize)

    async def save(
        self,
        user_id: int,
        task_id: str,
        request: VideoTaskCreateRequest,
        result: NoteGenerateResponse,
        created_at: str,
    ) -> None:
        await asyncio.to_thread(self._save, user_id, task_id, request, result, created_at)

    async def list_notes(self, user_id: int) -> list[SavedNoteSummary]:
        return await asyncio.to_thread(self._list_notes, user_id)

    async def list_note_groups(self, user_id: int) -> list[SavedNoteGroup]:
        return await asyncio.to_thread(self._list_note_groups, user_id)

    async def get_note(self, user_id: int, task_id: str) -> NoteGenerateResponse | None:
        return await asyncio.to_thread(self._get_note, user_id, task_id)

    def _connect(self, database: str | None = None, *, autocommit: bool = True):
        return pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=database,
            charset="utf8mb4",
            autocommit=autocommit,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _initialize(self) -> None:
        database = settings.mysql_database
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        with self._connect(database) as connection:
            cursor = connection.cursor()
            cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notes (
                        task_id VARCHAR(32) PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        video_url TEXT NOT NULL,
                        bvid VARCHAR(64) NOT NULL,
                        title VARCHAR(500) NOT NULL,
                        cover TEXT NULL,
                        duration INT NULL,
                        page INT NOT NULL,
                        platform VARCHAR(32) DEFAULT 'bilibili' NOT NULL,
                        style VARCHAR(32) NOT NULL,
                        ai_provider VARCHAR(32) NOT NULL DEFAULT 'deepseek',
                        extra_instruction TEXT NULL,
                        note LONGTEXT NOT NULL,
                        mind_map JSON NULL,
                        content_type VARCHAR(64) DEFAULT '通用笔记' NOT NULL,
                        collection_data JSON NULL,
                        subtitle_source VARCHAR(64) NOT NULL,
                        subtitle_text LONGTEXT NOT NULL,
                        subtitle_lines JSON NOT NULL,
                        chunk_count INT NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            cursor.execute("SHOW COLUMNS FROM notes LIKE 'user_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE notes ADD COLUMN user_id BIGINT NOT NULL DEFAULT 0 AFTER task_id")
            cursor.execute("SHOW COLUMNS FROM notes LIKE 'ai_provider'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE notes ADD COLUMN ai_provider VARCHAR(32) NOT NULL DEFAULT 'deepseek' AFTER style")
            cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS note_collections (
                        collection_key VARCHAR(200) PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        bvid VARCHAR(64) NOT NULL,
                        platform VARCHAR(32) NOT NULL,
                        title VARCHAR(500) NOT NULL,
                        cover TEXT NULL,
                        source_url TEXT NULL,
                        video_count INT DEFAULT 1 NOT NULL,
                        total_duration INT DEFAULT 0 NOT NULL,
                        collection_note_task_id VARCHAR(32) NULL,
                        updated_at TIMESTAMP NOT NULL,
                        KEY IDX_AINOTE_COLLECTION_USER (user_id, platform, bvid)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            cursor.execute("SHOW COLUMNS FROM note_collections LIKE 'user_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE note_collections ADD COLUMN user_id BIGINT NOT NULL DEFAULT 0 AFTER collection_key")
            cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS note_collection_videos (
                        collection_key VARCHAR(200) NOT NULL,
                        page INT NOT NULL,
                        bvid VARCHAR(64) NOT NULL,
                        title VARCHAR(500) NOT NULL,
                        cover TEXT NULL,
                        duration INT NULL,
                        source_url TEXT NOT NULL,
                        note_task_id VARCHAR(32) NULL,
                        updated_at TIMESTAMP NOT NULL,
                        PRIMARY KEY (collection_key, page),
                        KEY IDX_AINOTE_COLLECTION_VIDEO_NOTE (note_task_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            cursor.close()

    def _save(
        self,
        user_id: int,
        task_id: str,
        request: VideoTaskCreateRequest,
        result: NoteGenerateResponse,
        created_at: str,
    ) -> None:
        values = (
            task_id,
            user_id,
            request.videoUrl,
            result.video.bvid,
            result.video.title,
            result.video.cover,
            result.video.duration,
            result.video.page,
            result.video.platform,
            request.style,
            request.modelProvider,
            request.extraInstruction,
            result.note,
            json.dumps(result.mindMap, ensure_ascii=False),
            result.contentType,
            json.dumps(result.collection.model_dump(), ensure_ascii=False) if result.collection else None,
            result.subtitle.source,
            result.subtitle.text,
            json.dumps([line.model_dump() for line in result.subtitle.lines], ensure_ascii=False),
            result.chunk_count,
            created_at,
        )
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO notes (
                        task_id, user_id, video_url, bvid, title, cover, duration, page, platform, style, ai_provider,
                        extra_instruction, note, mind_map, content_type, collection_data, subtitle_source,
                        subtitle_text, subtitle_lines, chunk_count, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
                self._save_collection_catalog(cursor, user_id, result.collection, task_id, result.video.platform, created_at)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def _list_notes(self, user_id: int) -> list[SavedNoteSummary]:
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT task_id, video_url, title, bvid, cover, page, style, collection_data, created_at
                FROM notes WHERE user_id = %s ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
        summaries = []
        for row in rows:
            collection = self._load_collection(row.get("collection_data"))
            summaries.append(
                SavedNoteSummary(
                    taskId=row["task_id"],
                    title=row["title"],
                    bvid=row["bvid"],
                    cover=row["cover"],
                    style=row["style"],
                    createdAt=self._format_datetime(row["created_at"]),
                    isCollection=collection is not None,
                    videoCount=collection.videoCount if collection else 1,
                    page=row.get("page") or 1,
                    sourceUrl=row.get("video_url"),
                    generatedPages=self._generated_pages(collection, row),
                )
            )
        return summaries

    def _save_collection_catalog(
        self,
        cursor,
        user_id: int,
        collection: VideoCollection | None,
        task_id: str,
        platform: str,
        created_at: str,
    ) -> None:
        if not collection or not collection.videos:
            return

        bvid = collection.videos[0].bvid
        collection_key = self._collection_key(user_id, platform, bvid)
        selected_pages = {page for page in collection.generatedPages if page > 0}
        collection_task_id = task_id if len(selected_pages) != 1 else None
        cursor.execute("SELECT COUNT(*) AS total FROM note_collections WHERE collection_key = %s", (collection_key,))
        if cursor.fetchone()["total"]:
            cursor.execute(
                """
                UPDATE note_collections
                SET title = %s, cover = %s, source_url = %s, video_count = %s, total_duration = %s,
                    collection_note_task_id = COALESCE(%s, collection_note_task_id), updated_at = %s
                WHERE collection_key = %s
                """,
                (
                    collection.title,
                    collection.cover,
                    collection.sourceUrl,
                    collection.videoCount,
                    collection.totalDuration,
                    collection_task_id,
                    created_at,
                    collection_key,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO note_collections (
                    collection_key, user_id, bvid, platform, title, cover, source_url, video_count,
                    total_duration, collection_note_task_id, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    collection_key,
                    user_id,
                    bvid,
                    platform,
                    collection.title,
                    collection.cover,
                    collection.sourceUrl,
                    collection.videoCount,
                    collection.totalDuration,
                    collection_task_id,
                    created_at,
                ),
            )

        for video in collection.videos:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM note_collection_videos WHERE collection_key = %s AND page = %s",
                (collection_key, video.page),
            )
            if cursor.fetchone()["total"]:
                cursor.execute(
                    """
                    UPDATE note_collection_videos
                    SET title = %s, cover = %s, duration = %s, source_url = %s, updated_at = %s
                    WHERE collection_key = %s AND page = %s
                    """,
                    (video.title, video.cover, video.duration, video.sourceUrl, created_at, collection_key, video.page),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO note_collection_videos (
                        collection_key, page, bvid, title, cover, duration, source_url, note_task_id, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s)
                    """,
                    (collection_key, video.page, video.bvid, video.title, video.cover, video.duration, video.sourceUrl, created_at),
                )

        if len(selected_pages) == 1:
            cursor.execute(
                """
                UPDATE note_collection_videos SET note_task_id = %s, updated_at = %s
                WHERE collection_key = %s AND page = %s
                """,
                (task_id, created_at, collection_key, selected_pages.pop()),
            )

    @staticmethod
    def _collection_key(user_id: int, platform: str, bvid: str) -> str:
        return f"{user_id}:{platform}:{bvid}"

    def _load_collection_catalog(self, user_id: int) -> dict[str, dict]:
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM note_collections WHERE user_id = %s", (user_id,))
            collection_rows = cursor.fetchall()
            keys = [row["collection_key"] for row in collection_rows]
            video_rows = []
            for key in keys:
                cursor.execute(
                    "SELECT * FROM note_collection_videos WHERE collection_key = %s ORDER BY page",
                    (key,),
                )
                video_rows.extend(cursor.fetchall())
            cursor.close()

        catalog = {
            f'{row["platform"]}:{row["bvid"]}': {
                "title": row["title"],
                "cover": row["cover"],
                "sourceUrl": row["source_url"],
                "videoCount": row["video_count"],
                "collectionNoteTaskId": row["collection_note_task_id"],
                "collectionKey": row["collection_key"],
                "videos": [],
            }
            for row in collection_rows
        }
        by_internal_key = {item["collectionKey"]: item for item in catalog.values()}
        for row in video_rows:
            group = by_internal_key.get(row["collection_key"])
            if group:
                group["videos"].append(
                    CollectionVideo(
                        bvid=row["bvid"],
                        title=row["title"],
                        cover=row["cover"],
                        duration=row["duration"],
                        page=row["page"],
                        sourceUrl=row["source_url"],
                        noteTaskId=row["note_task_id"],
                    )
                )
        return catalog

    def _list_note_groups(self, user_id: int) -> list[SavedNoteGroup]:
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT task_id, video_url, bvid, title, cover, duration, page, platform, style,
                       collection_data, created_at
                FROM notes WHERE user_id = %s ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()

        catalog = self._load_collection_catalog(user_id)
        groups: dict[str, dict] = {}
        for row in rows:
            platform = row.get("platform") or "bilibili"
            bvid = row.get("bvid") or row["task_id"]
            group_id = f"{platform}:{bvid}"
            collection = self._load_collection(row.get("collection_data"))
            summary = SavedNoteSummary(
                taskId=row["task_id"],
                title=row["title"],
                bvid=bvid,
                cover=row["cover"],
                style=row["style"],
                createdAt=self._format_datetime(row["created_at"]),
                isCollection=collection is not None,
                videoCount=collection.videoCount if collection else 1,
                page=row.get("page") or 1,
                sourceUrl=row.get("video_url"),
                generatedPages=self._generated_pages(collection, row),
            )
            if group_id not in groups:
                videos = collection.videos if collection else [
                    CollectionVideo(
                        bvid=bvid,
                        title=row["title"],
                        cover=row["cover"],
                        duration=row["duration"],
                        page=row["page"],
                        platform=platform,
                        sourceUrl=row["video_url"],
                    )
                ]
                groups[group_id] = {
                    "groupId": group_id,
                    "title": collection.title if collection else row["title"],
                    "bvid": bvid,
                    "cover": collection.cover if collection else row["cover"],
                    "sourceUrl": collection.sourceUrl if collection else row["video_url"],
                    "platform": platform,
                    "videoCount": collection.videoCount if collection else 1,
                    "videos": videos,
                    "notes": [],
                }
            group = groups[group_id]
            if collection and len(collection.videos) > len(group["videos"]):
                group["videos"] = collection.videos
                group["videoCount"] = collection.videoCount
            group["notes"].append(summary)

        return [
            SavedNoteGroup(**self._apply_catalog_group(group, catalog.get(group["groupId"])))
            for group in groups.values()
        ]

    @staticmethod
    def _apply_catalog_group(group: dict, catalog: dict | None) -> dict:
        if not catalog:
            group["generatedCount"] = len(group["notes"])
            return group
        group["title"] = catalog["title"] or group["title"]
        group["cover"] = catalog["cover"] or group["cover"]
        group["sourceUrl"] = catalog["sourceUrl"] or group["sourceUrl"]
        group["videoCount"] = catalog["videoCount"]
        group["collectionNoteTaskId"] = catalog["collectionNoteTaskId"]
        group["videos"] = catalog["videos"]
        group["generatedCount"] = sum(1 for video in catalog["videos"] if video.noteTaskId)
        return group

    def _get_note(self, user_id: int, task_id: str) -> NoteGenerateResponse | None:
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM notes WHERE task_id = %s AND user_id = %s", (task_id, user_id))
            row = cursor.fetchone()
            cursor.close()
        if not row:
            return None
        subtitle_lines = self._load_json_list(row["subtitle_lines"])
        video = VideoInfo(
            bvid=row["bvid"],
            title=row["title"],
            cover=row["cover"],
            duration=row["duration"],
            page=row["page"],
            platform=row.get("platform") or "bilibili",
            sourceUrl=row["video_url"],
        )
        return NoteGenerateResponse(
            video=video,
            subtitle=SubtitleResponse(
                video=video,
                lines=[SubtitleLine.model_validate(line) for line in subtitle_lines],
                text=row["subtitle_text"],
                source=row["subtitle_source"],
            ),
            note=row["note"],
            mindMap=self._load_json(row.get("mind_map")),
            contentType=row.get("content_type") or "通用笔记",
            chunk_count=row["chunk_count"],
            collection=self._load_collection(row.get("collection_data")),
        )

    @staticmethod
    def _format_datetime(value: datetime | str) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    @staticmethod
    def _load_json(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value:
            return json.loads(value)
        return {}

    @staticmethod
    def _load_json_list(value) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value:
            return json.loads(value)
        return []

    @classmethod
    def _load_collection(cls, value) -> VideoCollection | None:
        payload = cls._load_json(value)
        return VideoCollection.model_validate(payload) if payload else None

    @staticmethod
    def _generated_pages(collection: VideoCollection | None, row: dict) -> list[int]:
        if collection and collection.generatedPages:
            return collection.generatedPages
        if collection and collection.videos:
            return [video.page for video in collection.videos]
        try:
            page = parse_qs(urlparse(row.get("video_url") or "").query).get("p", [row.get("page") or 1])[0]
            return [max(1, int(page))]
        except (TypeError, ValueError):
            return [row.get("page") or 1]
