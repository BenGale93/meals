from inline_snapshot import snapshot as snap

from meals.app import app  # noqa: F401 - importing the app registers the models
from meals.database import Base


def test_models_are_registered():
    """Every table must be registered on the metadata, since Alembic owns the schema."""
    assert len(Base.registry.mappers) == snap(6)
    assert sorted(Base.metadata.tables) == snap(
        ["ingredients", "planned_days", "recipe_ingredients", "recipes", "timings", "users"]
    )
