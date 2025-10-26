"""Module containing all the meal schemas."""

import typing as t

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, RootModel, model_validator


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

        *name, quantity, unit = data.split(" ")

        return {
            "name": " ".join(name),
            "quantity": quantity,
            "unit": unit,
        }


class IngredientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str = Field(validation_alias=AliasChoices(AliasPath("name"), AliasPath("ingredient", "name")))
    quantity: float
    unit: str

    def __str__(self) -> str:
        """The description of the ingredient."""
        return f"{self.name} {self.quantity} {self.unit}"


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


class CreateRecipes(RootModel[list[CreateRecipeRequest]]):
    def __iter__(self) -> t.Iterator[CreateRecipeRequest]:  # type: ignore [override]  # noqa: D105
        return iter(self.root)


class Recipes(RootModel[list[RecipeResponse]]):
    """A list of recipes."""

    model_config = ConfigDict(from_attributes=True)

    def __iter__(self) -> t.Iterator[RecipeResponse]:  # type: ignore [override]  # noqa: D105
        return iter(self.root)

    def __len__(self) -> int:  # noqa: D105
        return len(self.root)
