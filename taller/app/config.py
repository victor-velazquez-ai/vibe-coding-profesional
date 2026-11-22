"""Configuracion de la aplicacion.

Todo se lee de variables de entorno (o de un `.env` local que nunca se versiona).
No hay valores por defecto para los secretos: si faltan, la app no arranca.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from psycopg.conninfo import make_conninfo
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres: las mismas variables que consume docker-compose.yml.
    # min_length=1 para que un .env a medio rellenar falle aqui y no mas tarde.
    postgres_user: str = Field(min_length=1)
    postgres_password: str = Field(min_length=1)
    postgres_db: str = Field(min_length=1)
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    # Override completo de la URL (lo usan los tests con su base temporal).
    database_url: str | None = None

    # Tokens.
    secret_key: str = Field(min_length=1)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Servidor de desarrollo.
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Logs.
    log_level: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        """URL que usa SQLAlchemy para la base de la app."""
        if self.database_url:
            return self.database_url
        return self.sqlalchemy_url_for(self.postgres_db)

    def sqlalchemy_url_for(self, database: str) -> str:
        """URL de SQLAlchemy para una base concreta del mismo servidor."""
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{database}"
        )

    def psycopg_conninfo(self, database: str) -> str:
        """Cadena de conexion de psycopg (sin el prefijo de dialecto)."""
        return make_conninfo(
            host=self.postgres_host,
            port=self.postgres_port,
            user=self.postgres_user,
            password=self.postgres_password,
            dbname=database,
        )

    @property
    def log_dir(self) -> Path:
        return PROJECT_ROOT / "logs"

    @property
    def log_file(self) -> Path:
        return self.log_dir / "app.log"


class MissingConfigError(RuntimeError):
    """Falta configuracion obligatoria (normalmente, no existe el .env)."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        # Los campos obligatorios llegan del entorno, no como argumentos: el
        # type checker no puede saberlo (es el patron documentado de
        # pydantic-settings).
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = sorted(
            str(error["loc"][0]).upper()
            for error in exc.errors()
            if error["loc"] and error["type"] in {"missing", "string_too_short"}
        )
        if not missing:
            raise
        raise MissingConfigError(
            f"Faltan variables de entorno (o estan vacias): {', '.join(missing)}. "
            "Copia .env.example a .env (o ejecuta `uv run poe init-env`)."
        ) from exc
