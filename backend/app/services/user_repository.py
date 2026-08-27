"""MySQL 用户、会话、积分与会员预留能力。"""

import asyncio
import base64
import hashlib
import hmac
import math
import secrets
from datetime import datetime, timedelta

import pymysql

from app.config import settings
from app.schemas import AuthSession, UserProfile


class UserAlreadyExistsError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InsufficientPointsError(ValueError):
    pass


class UserRepository:
    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize)

    async def register(self, account: str, email: str, password: str) -> AuthSession:
        return await asyncio.to_thread(self._register, account, email, password)

    async def login(self, login: str, password: str) -> AuthSession:
        return await asyncio.to_thread(self._login, login, password)

    async def get_by_session(self, token: str) -> UserProfile | None:
        return await asyncio.to_thread(self._get_by_session, token)

    async def logout(self, token: str) -> None:
        await asyncio.to_thread(self._logout, token)

    async def consume_points(self, user_id: int, points: int, reference_id: str, description: str) -> int:
        return await asyncio.to_thread(self._change_points, user_id, -points, "VIDEO_NOTE", reference_id, description)

    async def refund_points(self, user_id: int, points: int, reference_id: str) -> int:
        return await asyncio.to_thread(self._refund_points, user_id, points, reference_id)

    @staticmethod
    def calculate_video_cost(duration_seconds: int | None) -> int:
        return max(1, math.ceil(max(0, duration_seconds or 0) / 60)) * settings.points_per_minute

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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        email VARCHAR(320) NOT NULL,
                        account VARCHAR(64) NOT NULL,
                        password_hash VARCHAR(512) NOT NULL,
                        points INT NOT NULL DEFAULT 100,
                        member_level VARCHAR(32) NOT NULL DEFAULT 'FREE',
                        member_expires_at DATETIME NULL,
                        role VARCHAR(24) NOT NULL DEFAULT 'USER',
                        status VARCHAR(24) NOT NULL DEFAULT 'ACTIVE',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_users_email (email),
                        UNIQUE KEY uk_users_account (account)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT UNSIGNED NOT NULL,
                        token_hash CHAR(64) NOT NULL,
                        expires_at DATETIME NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_user_sessions_token (token_hash),
                        KEY idx_user_sessions_user (user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(24) NOT NULL DEFAULT 'USER' AFTER member_expires_at")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS point_transactions (
                        transaction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT UNSIGNED NOT NULL,
                        amount INT NOT NULL,
                        balance_after INT NOT NULL,
                        transaction_type VARCHAR(32) NOT NULL,
                        reference_id VARCHAR(64) NULL,
                        description VARCHAR(300) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_point_transactions_user (user_id, created_at),
                        KEY idx_point_transactions_reference (reference_id, transaction_type)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )

    def _register(self, account: str, email: str, password: str) -> AuthSession:
        normalized_account = account.strip()
        normalized_email = email.strip().lower()
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT user_id FROM users WHERE LOWER(email) = %s OR account = %s",
                        (normalized_email, normalized_account),
                    )
                    if cursor.fetchone():
                        raise UserAlreadyExistsError("邮箱或账号已被注册")
                    cursor.execute(
                        "INSERT INTO users (email, account, password_hash, points) VALUES (%s, %s, %s, %s)",
                        (normalized_email, normalized_account, self._hash_password(password), settings.initial_points),
                    )
                    user_id = cursor.lastrowid
                    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                    user = cursor.fetchone()
                    cursor.execute(
                        """
                        INSERT INTO point_transactions
                            (user_id, amount, balance_after, transaction_type, description)
                        VALUES (%s, %s, %s, 'REGISTER_BONUS', '注册赠送积分')
                        """,
                        (user_id, settings.initial_points, settings.initial_points),
                    )
                    token = self._create_session(cursor, user_id)
                connection.commit()
                return AuthSession(token=token, user=self._profile(user))
            except Exception:
                connection.rollback()
                raise

    def _login(self, login: str, password: str) -> AuthSession:
        normalized = login.strip()
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE account = %s OR LOWER(email) = %s",
                    (normalized, normalized.lower()),
                )
                user = cursor.fetchone()
                if not user or user["status"] != "ACTIVE" or not self._verify_password(password, user["password_hash"]):
                    raise InvalidCredentialsError("账号、邮箱或密码不正确")
                token = self._create_session(cursor, user["user_id"])
            connection.commit()
            return AuthSession(token=token, user=self._profile(user))

    def _get_by_session(self, token: str) -> UserProfile | None:
        if not token:
            return None
        with self._connect(settings.mysql_database) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.* FROM users u
                    JOIN user_sessions s ON s.user_id = u.user_id
                    WHERE s.token_hash = %s AND s.expires_at > NOW() AND u.status = 'ACTIVE'
                    """,
                    (self._token_hash(token),),
                )
                user = cursor.fetchone()
        return self._profile(user) if user else None

    def _logout(self, token: str) -> None:
        if not token:
            return
        with self._connect(settings.mysql_database) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM user_sessions WHERE token_hash = %s", (self._token_hash(token),))

    def _change_points(self, user_id: int, amount: int, transaction_type: str, reference_id: str, description: str) -> int:
        with self._connect(settings.mysql_database, autocommit=False) as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT points FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
                    row = cursor.fetchone()
                    if not row:
                        raise InvalidCredentialsError("用户不存在")
                    balance = int(row["points"])
                    next_balance = balance + amount
                    if next_balance < 0:
                        raise InsufficientPointsError(f"积分不足，本次需要 {abs(amount)} 积分，当前剩余 {balance} 积分")
                    cursor.execute("UPDATE users SET points = %s WHERE user_id = %s", (next_balance, user_id))
                    cursor.execute(
                        """
                        INSERT INTO point_transactions
                            (user_id, amount, balance_after, transaction_type, reference_id, description)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, amount, next_balance, transaction_type, reference_id, description),
                    )
                connection.commit()
                return next_balance
            except Exception:
                connection.rollback()
                raise

    def _refund_points(self, user_id: int, points: int, reference_id: str) -> int:
        with self._connect(settings.mysql_database) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT transaction_id FROM point_transactions WHERE reference_id = %s AND transaction_type = 'VIDEO_REFUND' LIMIT 1",
                    (reference_id,),
                )
                already_refunded = bool(cursor.fetchone())
        if already_refunded:
            return self._get_user(user_id).points
        return self._change_points(user_id, points, "VIDEO_REFUND", reference_id, "视频笔记生成失败，退回积分")

    def _get_user(self, user_id: int) -> UserProfile:
        with self._connect(settings.mysql_database) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user = cursor.fetchone()
        if not user:
            raise InvalidCredentialsError("用户不存在")
        return self._profile(user)

    def _create_session(self, cursor, user_id: int) -> str:
        token = secrets.token_urlsafe(40)
        expires_at = datetime.now() + timedelta(days=settings.session_days)
        cursor.execute(
            "INSERT INTO user_sessions (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, self._token_hash(token), expires_at),
        )
        return token

    @staticmethod
    def _profile(user: dict) -> UserProfile:
        return UserProfile(
            id=int(user["user_id"]),
            account=user["account"],
            email=user["email"],
            points=int(user["points"]),
            memberLevel=user.get("member_level") or "FREE",
            memberExpiresAt=user.get("member_expires_at"),
            isAdmin=(user.get("role") == "ADMIN"),
        )

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return f"scrypt$16384$8$1${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            _, n, r, p, salt_text, digest_text = encoded.split("$", 5)
            salt = base64.urlsafe_b64decode(salt_text.encode())
            expected = base64.urlsafe_b64decode(digest_text.encode())
            actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
