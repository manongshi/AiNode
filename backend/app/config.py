import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.deepseek.com").rstrip("/")
    ai_model: str = os.getenv("AI_MODEL", "deepseek-v4-flash")
    qwen_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").rstrip("/")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen3.7-flash")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "120"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    xfyun_app_id: str = os.getenv("XFYUN_APP_ID", "cefebe6c").strip()
    xfyun_api_key: str = os.getenv("XFYUN_API_KEY", "").strip()
    xfyun_api_secret: str = os.getenv("XFYUN_API_SECRET", "").strip()
    xfyun_request_timeout_seconds: float = float(os.getenv("XFYUN_REQUEST_TIMEOUT_SECONDS", "180"))
    xfyun_poll_interval_seconds: float = float(os.getenv("XFYUN_POLL_INTERVAL_SECONDS", "3"))
    xfyun_poll_timeout_seconds: float = float(os.getenv("XFYUN_POLL_TIMEOUT_SECONDS", "7200"))
    mlx_whisper_model: str = os.getenv(
        "MLX_WHISPER_MODEL",
        "mlx-community/whisper-large-v3-turbo",
    ).strip()
    mlx_whisper_language: str = os.getenv("MLX_WHISPER_LANGUAGE", "zh").strip()
    bilibili_cookie_file: str = os.getenv("BILIBILI_COOKIE_FILE", "")
    bilibili_cookie: str = os.getenv("BILIBILI_COOKIE", "")
    # 留空时显式绕过系统 HTTP(S)_PROXY，避免本地失效代理影响音频下载。
    bilibili_proxy: str = os.getenv("BILIBILI_PROXY", "").strip()
    bilibili_user_agent: str = os.getenv(
        "BILIBILI_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    bilibili_referer: str = os.getenv("BILIBILI_REFERER", "https://www.bilibili.com/")
    bilibili_accept_language: str = os.getenv("BILIBILI_ACCEPT_LANGUAGE", "zh-CN,zh;q=0.9")
    mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "123456")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "ainote")
    session_days: int = int(os.getenv("SESSION_DAYS", "30"))
    initial_points: int = int(os.getenv("INITIAL_POINTS", "100"))
    points_per_minute: int = int(os.getenv("POINTS_PER_MINUTE", "1"))
    pdf_chromium_executable: str = os.getenv(
        "PDF_CHROMIUM_EXECUTABLE",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
