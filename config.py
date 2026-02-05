import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise ConfigError(f"Переменная {name} не установлена")
    return value.strip()


def _require_int_env(name: str) -> int:
    value = _require_env(name)
    try:
        return int(value)
    except ValueError as e:
        raise ConfigError(f"Переменная {name} должна быть числом: {value!r}") from e


def _default_sqlite_url() -> str:
    """
    Default sqlite path:
    - Docker: /app/data/db.sqlite3  (if /app/data exists)
    - Local: ./data/db.sqlite3
    """
    docker_data = Path("/app/data")
    base_dir = docker_data if docker_data.exists() else Path(__file__).resolve().parent / "data"
    base_dir.mkdir(parents=True, exist_ok=True)

    db_path = base_dir / "db.sqlite3"
    return f"sqlite:////{db_path.as_posix().lstrip('/')}"


# === REQUIRED ===
BOT_TOKEN = _require_env("BOT_TOKEN")
SUPPORT_CHAT_ID = _require_int_env("SUPPORT_CHAT_ID")

# === OPTIONAL ===
DATABASE_URL = os.getenv("DATABASE_URL") or _default_sqlite_url()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
