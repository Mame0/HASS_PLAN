"""Configuracion del Sistema de Gestion y Planificacion del Cultivo de Palta Hass."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    """Normaliza la URL para SQLAlchemy (psycopg2)."""
    # Heroku/algunos proveedores entregan 'postgres://'; SQLAlchemy quiere 'postgresql://'
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _default_pg_url():
    """URL de PostgreSQL por defecto (rol de la app). Se puede ajustar por entorno:
    PG_USER / PG_PASSWORD / PG_HOST / PG_PORT / PG_DB, o sobreescribir todo con DATABASE_URL.
    """
    user = os.environ.get("PG_USER", "app_palta")
    pwd = os.environ.get("PG_PASSWORD", "71804217")
    host = os.environ.get("PG_HOST", "localhost")
    port = os.environ.get("PG_PORT", "5432")
    db = os.environ.get("PG_DB", "palta")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


class Config:
    # El sistema trabaja SIEMPRE con PostgreSQL (modo SaaS multi-tenant con RLS).
    # Por defecto se conecta al PostgreSQL local; DATABASE_URL lo sobreescribe.
    # (SQLite ya NO se usa para la app: queda solo como fuente de migración y, de
    #  forma aislada, para los tests vía su propio TestConfig.)
    _DB_URL = os.environ.get("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_DB_URL) if _DB_URL else _default_pg_url()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "palta-hass-dev-key")

    # True si el backend es PostgreSQL (activa la inyección RLS por request).
    IS_POSTGRES = SQLALCHEMY_DATABASE_URI.startswith("postgresql")

    # Exigir login en /api (modo SaaS multi-tenant). Por defecto activo solo en
    # PostgreSQL; en SQLite (dev/tests single-user) queda desactivado para no
    # romper el flujo local ni la suite de tests. Override: REQUIRE_LOGIN=1/0.
    _RL = os.environ.get("REQUIRE_LOGIN")
    REQUIRE_LOGIN = IS_POSTGRES if _RL is None else _RL not in ("0", "", "false", "False")

    # Ruta al modelo de Machine Learning serializado
    ML_MODEL_PATH = os.path.join(BASE_DIR, "app", "ml", "modelo.pkl")
