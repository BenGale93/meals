from fastapi.testclient import TestClient

from meals.app import app
from meals.database import Base


def test_lifespan_init_models():
    with TestClient(app):
        assert len(Base.registry.mappers) == 4
