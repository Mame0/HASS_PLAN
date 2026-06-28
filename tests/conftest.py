"""
Configuracion compartida de pytest.

- Asegura que la raiz del proyecto (sistema_palta/) este en sys.path para importar `app`.
- Fixture `app`: crea la aplicacion con una BD SQLite temporal AISLADA (no toca instance/palta.db).
"""
import os
import sys

import pytest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)

from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    """App de pruebas con BD temporal por test (se descarta al terminar)."""
    class TestConfig:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = "test"
        ML_MODEL_PATH = os.path.join(RAIZ, "app", "ml", "modelo.pkl")

    return create_app(TestConfig)
