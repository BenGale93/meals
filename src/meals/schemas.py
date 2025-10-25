"""Module containing all the meal schemas."""

import typing as t

from htmy import Component, Context, component, html
from pydantic import AliasPath, BaseModel, ConfigDict, Field, RootModel, model_validator


class Ingredient(BaseModel):
    """An ingredient found in a recipe."""

    model_config = ConfigDict(from_attributes=True, validate_by_alias=True, validate_by_name=True)

    name: str = Field(validation_alias=AliasPath("ingredient", "name"))
    quantity: float
    unit: str

    @model_validator(mode="before")
    @classmethod
    def from_string(cls, data: t.Any) -> t.Any:
        """Splits a ingredient string into its components."""
        if not isinstance(data, str):
            return data

        *name, quantity, unit = data.split(" ")

        return {
            "name": " ".join(name),
            "quantity": quantity,
            "unit": unit,
        }

    def __str__(self) -> str:
        """The description of the ingredient."""
        return f"{self.name} {self.quantity} {self.unit}"


class Recipe(BaseModel):
    """A recipe with the required instructions and ingredients."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    ingredients: list[Ingredient]
    instructions: str


@component
async def recipe_div(recipe: Recipe, context: Context) -> Component:  # noqa: ARG001
    """A Div representing a recipe."""
    return html.div(
        html.h1(recipe.name, class_="font-bold text-[20px]"),
        html.ul(*[html.li(str(i)) for i in recipe.ingredients], class_="m-3"),
        html.p(recipe.instructions, style="white-space:pre-line;"),
        class_="m-5",
    )


class Recipes(RootModel[list[Recipe]]):
    """A list of recipes."""

    model_config = ConfigDict(from_attributes=True)

    def __iter__(self) -> t.Iterator[Recipe]:  # type: ignore [override]  # noqa: D105
        return iter(self.root)


@component
def recipes_div(recipes: Recipes, context: Context) -> Component:  # noqa: ARG001
    """A Div representing all recipes."""
    return [recipe_div(recipe) for recipe in recipes]
