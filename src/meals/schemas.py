"""Module containing all the meal schemas."""

import re
import typing as t
from datetime import time  # noqa: TC003

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, RootModel, field_serializer, model_validator

INGREDIENT_REGEX = re.compile(r"([a-zA-Z ]+)([\d.]+)([a-zA-Z ]+)")


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

        match = INGREDIENT_REGEX.search(data)
        if match is None:
            msg = "Expected ingredient to be in form: 'name quantity unit'. Where quantity is a number."
            raise ValueError(msg) from None

        return {
            "name": match.group(1).strip(),
            "quantity": match.group(2),
            "unit": match.group(3).strip(),
        }


class IngredientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str = Field(validation_alias=AliasChoices(AliasPath("name"), AliasPath("ingredient", "name")))
    quantity: float
    unit: str


class CreateRecipeRequest(BaseModel):
    name: str
    ingredients: list[CreateIngredientRequest]
    instructions: str


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

    def get_ingredient(self, name: str) -> CreateIngredientRequest | None:
        """Get the ingredient by name."""
        for i in self.ingredients:
            if i.name == name:
                return i
        return None


class CreateRecipes(RootModel[list[CreateRecipeRequest]]):
    """A list of recipes to create."""

    def __iter__(self) -> t.Iterator[CreateRecipeRequest]:  # type: ignore [override]  # noqa: D105 # pragma: no cover
        return iter(self.root)


class Recipes(RootModel[list[RecipeResponse]]):
    """A list of recipes."""

    model_config = ConfigDict(from_attributes=True)

    def __iter__(self) -> t.Iterator[RecipeResponse]:  # type: ignore [override]  # noqa: D105
        return iter(self.root)


class RecipeStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    offset: int = Field(le=0)


class TimingSteps(RootModel[list[RecipeStep]]):
    model_config = ConfigDict(from_attributes=True)


class TimingsCreate(BaseModel):
    steps: TimingSteps
    finish_time: time

    @field_serializer("finish_time", mode="plain")
    def time_to_str(self, value: time) -> str:
        """Formats the time as a string."""
        return value.isoformat()


class TimingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int | None
    steps: TimingSteps
    finish_time: time
