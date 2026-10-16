"""Runtime settings. Secrets come from `.env` and are never printed or logged."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Project settings. `EIA_API_KEY` is read from the environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    eia_api_key: SecretStr | None = None
    factors_dir: Path = REPO_ROOT / "factors"
    data_raw_dir: Path = REPO_ROOT / "data" / "raw"
    results_dir: Path = REPO_ROOT / "results"
    docs_dir: Path = REPO_ROOT / "docs"

    def require_eia_key(self) -> str:
        if self.eia_api_key is None or not self.eia_api_key.get_secret_value():
            raise RuntimeError("EIA_API_KEY is not set; copy .env.example to .env and fill it in")
        return self.eia_api_key.get_secret_value()

    def __repr__(self) -> str:  # never leak the key
        key = "set" if self.eia_api_key else "unset"
        return f"Settings(factors_dir={self.factors_dir!s}, eia_api_key={key})"


def get_settings() -> Settings:
    return Settings()
