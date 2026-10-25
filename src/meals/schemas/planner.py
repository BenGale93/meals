"""Request and response models for the meal planner and recipe summary."""

from datetime import date  # noqa: TC003

from pydantic import BaseModel, ConfigDict, RootModel, field_serializer


class PlannedRecipe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    name: str


class PlannedDay(BaseModel):
    day: date
    recipe: PlannedRecipe

    @field_serializer("day", mode="plain")
    def day_to_str(self, value: date) -> str:
        """Formats the day as a string."""
        return value.isoformat()


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
