from inline_snapshot import snapshot as snap

from meals.app import app
from meals.database import Base, get_db


def test_models_are_registered():
    """Every table must be registered on the metadata, since Alembic owns the schema."""
    assert len(Base.registry.mappers) == snap(6)
    assert sorted(Base.metadata.tables) == snap(
        ["ingredients", "planned_days", "recipe_ingredients", "recipes", "timings", "users"]
    )


def test_test_app_fixture_is_isolated_from_the_global_app(test_app):
    """The fixture must not leak dependency overrides into the global app."""
    assert test_app is not app
    assert get_db in test_app.dependency_overrides
    assert get_db not in app.dependency_overrides
