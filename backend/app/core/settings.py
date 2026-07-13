from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "configuration"

load_dotenv(REPO_ROOT / ".env")


class Settings(BaseModel):
    repo_root: Path = REPO_ROOT
    db_path: Path = REPO_ROOT / "data" / "runs.db"
    host: str = "127.0.0.1"
    port: int = 8000
    agents_config: Path = CONFIG_DIR / "agents.yaml"
    models_config: Path = CONFIG_DIR / "models.yaml"
    workflow_config: Path = CONFIG_DIR / "workflow.yaml"
    max_agent_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    env_file = CONFIG_DIR / "environments" / "local.yaml"
    overrides = (yaml.safe_load(env_file.read_text()) if env_file.exists() else None) or {}
    return Settings(**overrides)
