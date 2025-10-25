"""Tables used by the application."""

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meals.database import Base


class StoredRecipe(Base):
    """Table for recipes."""

    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan", uselist=True
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<Recipe(id={self.id}, name={self.name})>"


class StoredIngredient(Base):
    """Table for ingredients used in recipes."""

    __tablename__ = "ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    recipes: Mapped[list[StoredRecipe]] = relationship(
        "RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan", uselist=True
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<Ingredient(id={self.id}, name={self.name})>"


class RecipeIngredient(Base):
    """Table for joining recipes to their ingredients."""

    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    recipe: Mapped[StoredRecipe] = relationship("StoredRecipe", back_populates="ingredients")
    ingredient: Mapped[StoredIngredient] = relationship("StoredIngredient", back_populates="recipes")
