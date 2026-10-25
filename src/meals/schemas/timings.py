"""Request and response models for roast timings."""

from datetime import time  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_serializer


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
