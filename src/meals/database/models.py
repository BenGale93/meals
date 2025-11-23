"""Tables used by the application."""

from datetime import date, time  # noqa: TC003

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meals.database.session import Base


class User(Base):
    """Table for users."""

    __tablename__ = "users"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    recipes: Mapped[list[StoredRecipe]] = relationship("StoredRecipe", back_populates="user", cascade="all, delete")
    timings: Mapped[StoredTimings] = relationship("StoredTimings", back_populates="user", cascade="all, delete")
    planned_days: Mapped[list[StoredPlannedDay]] = relationship(
        "StoredPlannedDay", back_populates="user", cascade="all, delete"
    )


class StoredRecipe(Base):
    """Table for recipes."""

    __tablename__ = "recipes"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan", uselist=True, lazy="selectin"
    )

    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.pk"), nullable=False)
    user: Mapped[User] = relationship(back_populates="recipes")

    planned: Mapped[list[StoredPlannedDay]] = relationship(back_populates="recipe")

    def __repr__(self) -> str:  # noqa: D105
        return f"<Recipe(pk={self.pk}, name={self.name})>"


class StoredIngredient(Base):
    """Table for ingredients used in recipes."""

    __tablename__ = "ingredients"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    recipes: Mapped[list[RecipeIngredient]] = relationship(
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

    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.pk"), nullable=False)
    user: Mapped[User] = relationship(back_populates="timings")

    def __repr__(self) -> str:  # noqa: D105
        return f"<StoredTimings(pk={self.pk}, finish_time={self.finish_time})>"


class StoredPlannedDay(Base):
    """Table for planned days."""

    __tablename__ = "planned_days"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, unique=True)

    recipe_pk: Mapped[int] = mapped_column(ForeignKey("recipes.pk"))

    recipe: Mapped[StoredRecipe] = relationship(back_populates="planned")

    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.pk"), nullable=False)
    user: Mapped[User] = relationship(back_populates="planned_days")
