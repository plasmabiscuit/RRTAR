from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


@dataclass(frozen=True)
class Settings:
    app_dir: Path
    state_root: Path
    config_dir: Path
    data_dir: Path
    schemas_dir: Path
    db_dir: Path
    db_path: Path
    tmp_dir: Path
    log_dir: Path
    host: str
    port: int
    shared_api_key: str
    worker_poll_seconds: float
    cors_origin_regex: str

    @classmethod
    def load(cls) -> "Settings":
        repo_root = _repo_root()
        state_root = _env_path("RRTARD_STATE_ROOT", repo_root / ".backend-state")
        app_dir = _env_path("RRTARD_APP_DIR", repo_root)
        config_dir = _env_path("RRTARD_CONFIG_DIR", state_root / "config")
        data_dir = _env_path("RRTARD_DATA_DIR", state_root / "data")
        schemas_dir = _env_path("RRTARD_SCHEMAS_DIR", state_root / "schemas")
        db_dir = _env_path("RRTARD_DB_DIR", state_root / "db")
        tmp_dir = _env_path("RRTARD_TMP_DIR", state_root / "tmp")
        log_dir = _env_path("RRTARD_LOG_DIR", state_root / "log")
        db_path = _env_path("RRTARD_DB_PATH", db_dir / "rrtard.sqlite3")
        host = os.getenv("RRTARD_HOST", "0.0.0.0")
        port = int(os.getenv("RRTARD_PORT", "8081"))
        shared_api_key = os.getenv("RRTARD_SHARED_API_KEY", "")
        worker_poll_seconds = float(os.getenv("RRTARD_WORKER_POLL_SECONDS", "2.0"))
        cors_origin_regex = os.getenv("RRTARD_CORS_ORIGIN_REGEX", r"chrome-extension://.*")
        return cls(
            app_dir=app_dir,
            state_root=state_root,
            config_dir=config_dir,
            data_dir=data_dir,
            schemas_dir=schemas_dir,
            db_dir=db_dir,
            db_path=db_path,
            tmp_dir=tmp_dir,
            log_dir=log_dir,
            host=host,
            port=port,
            shared_api_key=shared_api_key,
            worker_poll_seconds=worker_poll_seconds,
            cors_origin_regex=cors_origin_regex,
        )

    def ensure_dirs(self) -> None:
        for path in (
            self.state_root,
            self.config_dir,
            self.data_dir,
            self.schemas_dir,
            self.db_dir,
            self.tmp_dir,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

