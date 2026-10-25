"""Request and response models for recipes and their ingredients.

Ingredients are parsed from the human-friendly strings the forms and seed files use
(``"Flour 2 cups"`` / ``"500g beef"``); the parsed name, quantity and unit are what the API
and database store.
"""

import re
import typing as t
from fractions import Fraction

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, RootModel, model_validator

QUANTITY = r"\d+(?:\.\d+)?|\d+/\d+"
QUANTITY_FIRST_REGEX = re.compile(
    rf"\s*(?P<quantity>{QUANTITY})\s*(?P<unit>[a-zA-Z]+)\s+(?P<name>[a-zA-Z][a-zA-Z '&-]*?)\s*"
)
NAME_FIRST_REGEX = re.compile(
    rf"\s*(?P<name>[a-zA-Z][a-zA-Z '&-]*?)\s+(?P<quantity>{QUANTITY})\s+(?P<unit>[a-zA-Z]+)\s*"
)
INGREDIENT_ERROR = (
    "Expected ingredient to be in form: 'name quantity unit' or 'quantity unit name', "
    "where quantity is a number or fraction. Examples: 'Flour 2 cups', '500g beef', '1/2 cup sugar'."
)


class CreateIngredientRequest(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    name: str = Field(validation_alias=AliasPath("ingredient", "name"))
    quantity: float
    unit: str

    @model_validator(mode="before")
    @classmethod
    def from_string(cls, data: t.Any) -> t.Any:
        """Splits a ingredient string into its components."""
        if not isinstance(data, str):
            return data

        match = QUANTITY_FIRST_REGEX.fullmatch(data) or NAME_FIRST_REGEX.fullmatch(data)
        if match is None:
            raise ValueError(INGREDIENT_ERROR) from None

        return {
            "name": match.group("name").strip(),
            "quantity": float(Fraction(match.group("quantity"))),
            "unit": match.group("unit").strip(),
        }


class IngredientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str = Field(validation_alias=AliasChoices(AliasPath("name"), AliasPath("ingredient", "name")))
    quantity: float
    unit: str

    @t.override
    def __str__(self) -> str:
        return f"{self.name} {self.quantity} {self.unit}"


def check_unique_ingredient_names(ingredients: list[CreateIngredientRequest]) -> None:
    """Raise if the same ingredient name is listed more than once."""
    names = [ingredient.name for ingredient in ingredients]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        msg = f"Duplicate ingredients are not allowed: {', '.join(duplicates)}."
        raise ValueError(msg)


class CreateRecipeRequest(BaseModel):
    name: str
    ingredients: list[CreateIngredientRequest]
    instructions: str

    @model_validator(mode="after")
    def ingredients_are_unique(self) -> CreateRecipeRequest:
        """Ensure each ingredient is listed at most once."""
        check_unique_ingredient_names(self.ingredients)
        return self

    @model_validator(mode="after")
    def both_or_neither_ingredients_and_instructions(self) -> CreateRecipeRequest:
        """Validator to ensure we have all or none of the ingredients and instructions."""
        if bool(self.ingredients) ^ bool(self.instructions):
            msg = "Either both ingredients and instructions are required, or neither."
            raise ValueError(msg)
        return self


class RecipeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str
    ingredients: list[IngredientResponse]
    instructions: str

    @property
    def anchor(self) -> str:
        """Returns the name as a HTML anchor."""
        return f"{self.name.replace(' ', '-')}"


class UpdateRecipeRequest(BaseModel):
    pk: int
    name: str
    ingredients: list[CreateIngredientRequest]
    instructions: str

    @model_validator(mode="after")
    def ingredients_are_unique(self) -> UpdateRecipeRequest:
        """Ensure each ingredient is listed at most once."""
        check_unique_ingredient_names(self.ingredients)
        return self


class CreateRecipes(RootModel[list[CreateRecipeRequest]]):
    """A list of recipes to create."""

    @t.override
    def __iter__(self) -> t.Iterator[CreateRecipeRequest]:  # pyrefly: ignore[bad-override]
        return iter(self.root)


class Recipes(RootModel[list[RecipeResponse]]):
    """A list of recipes."""

    model_config = ConfigDict(from_attributes=True)

    @t.override
    def __iter__(self) -> t.Iterator[RecipeResponse]:  # pyrefly: ignore[bad-override]
        return iter(self.root)
