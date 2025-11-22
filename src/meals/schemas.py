"""Module containing all the meal schemas."""

import re
import typing as t
from datetime import date, time  # noqa: TC003

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

    def __str__(self) -> str:  # noqa: D105
        return f"{self.name} {self.quantity} {self.unit}"


class CreateRecipeRequest(BaseModel):
    name: str
    ingredients: list[CreateIngredientRequest]
    instructions: str

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


class PlannedRecipe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str


class PlannedDay(BaseModel):
    day: date
    recipe: PlannedRecipe


class PlannedDayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    day: date
    recipe: PlannedRecipe | None


class DayToPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    recipe: PlannedRecipe | None


class PlannedDays(RootModel[list[DayToPlan]]):
    pass


class RecipeSummary(BaseModel):
    name: str
    count: int
    last_eaten: date | None
