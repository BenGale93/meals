"""Tables used by the application."""

from datetime import time  # noqa: TC003

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meals.database.session import Base


class StoredRecipe(Base):
    """Table for recipes."""

    __tablename__ = "recipes"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan", uselist=True, lazy="selectin"
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<Recipe(pk={self.pk}, name={self.name})>"


class StoredIngredient(Base):
    """Table for ingredients used in recipes."""

    __tablename__ = "ingredients"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    recipes: Mapped[list[StoredRecipe]] = relationship(
        "RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan", uselist=True, lazy="selectin"
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<Ingredient(pk={self.pk}, name={self.name})>"


class RecipeIngredient(Base):
    """Table for joining recipes to their ingredients."""

    __tablename__ = "recipe_ingredients"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_pk: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.pk", ondelete="CASCADE"), nullable=False)
    ingredient_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredients.pk", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    recipe: Mapped[StoredRecipe] = relationship("StoredRecipe", back_populates="ingredients", lazy="selectin")
    ingredient: Mapped[StoredIngredient] = relationship("StoredIngredient", back_populates="recipes", lazy="selectin")


class StoredTimings(Base):
    """Table for roast timings."""

    __tablename__ = "timings"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    finish_time: Mapped[time] = mapped_column(Time, nullable=False)
    steps: Mapped[str] = mapped_column(String, nullable=False)
