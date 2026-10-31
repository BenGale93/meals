"""Tables used by the application."""

from datetime import date, time  # noqa: TC003

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meals.constants import LABEL_LENGTH
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
    __table_args__ = (UniqueConstraint("user_pk", "name", name="uq_recipes_user_pk_name"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan", uselist=True, lazy="selectin"
    )
    labels: Mapped[list[StoredRecipeLabel]] = relationship(
        "StoredRecipeLabel",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="StoredRecipeLabel.sub_category_pk",
    )

    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.pk"), nullable=False)
    user: Mapped[User] = relationship(back_populates="recipes")

    planned: Mapped[list[StoredPlannedDay]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", passive_deletes=True
    )

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
    __table_args__ = (UniqueConstraint("user_pk", "day", name="uq_planned_days_user_pk_day"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    recipe_pk: Mapped[int] = mapped_column(
        ForeignKey("recipes.pk", ondelete="CASCADE", name="fk_planned_days_recipe_pk_recipes")
    )

    recipe: Mapped[StoredRecipe] = relationship(back_populates="planned")

    user_pk: Mapped[int] = mapped_column(Integer, ForeignKey("users.pk"), nullable=False)
    user: Mapped[User] = relationship(back_populates="planned_days")


class Category(Base):
    """Table for label categories."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(LABEL_LENGTH), nullable=False)

    sub_categories: Mapped[list[SubCategory]] = relationship(
        "SubCategory", back_populates="category", cascade="all, delete-orphan"
    )


class SubCategory(Base):
    """Table for label sub-categories, scoped to a category."""

    __tablename__ = "sub_categories"
    __table_args__ = (UniqueConstraint("category_pk", "name", name="uq_sub_categories_category_pk_name"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(LABEL_LENGTH), nullable=False)

    category_pk: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.pk", ondelete="CASCADE", name="fk_sub_categories_category_pk_categories"),
        nullable=False,
    )
    category: Mapped[Category] = relationship("Category", back_populates="sub_categories")

    recipe_labels: Mapped[list[StoredRecipeLabel]] = relationship(
        "StoredRecipeLabel", back_populates="sub_category", cascade="all, delete-orphan"
    )


class StoredRecipeLabel(Base):
    """Table joining recipes to their labels."""

    __tablename__ = "recipe_labels"
    __table_args__ = (
        UniqueConstraint("recipe_pk", "sub_category_pk", name="uq_recipe_labels_recipe_pk_sub_category_pk"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_pk: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recipes.pk", ondelete="CASCADE", name="fk_recipe_labels_recipe_pk_recipes"),
        nullable=False,
    )
    sub_category_pk: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "sub_categories.pk",
            ondelete="CASCADE",
            name="fk_recipe_labels_sub_category_pk_sub_categories",
        ),
        nullable=False,
        index=True,
    )

    recipe: Mapped[StoredRecipe] = relationship("StoredRecipe", back_populates="labels")
    sub_category: Mapped[SubCategory] = relationship("SubCategory", back_populates="recipe_labels")
