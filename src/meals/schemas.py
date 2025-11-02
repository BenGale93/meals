"""Module containing all the meal schemas."""

import re
import typing as t

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, RootModel, model_validator

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


class CreateRecipes(RootModel[list[CreateRecipeRequest]]):
    """A list of recipes to create."""


class Recipes(RootModel[list[RecipeResponse]]):
    """A list of recipes."""

    model_config = ConfigDict(from_attributes=True)

    def __iter__(self) -> t.Iterator[RecipeResponse]:  # type: ignore [override]  # noqa: D105
        return iter(self.root)


class RecipeStep(BaseModel):
    step: str
    offset: int = Field(le=0)


class TimingSteps(RootModel[list[RecipeStep]]):
    pass


class TimingsResponse(BaseModel):
    pk: int
    steps: TimingSteps
