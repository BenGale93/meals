import datetime as dt
from typing import TYPE_CHECKING, override

import time_machine

from meals.database.repository import PlanRepository, RecipeRepository
from meals.services import PlanService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from meals.database.models import StoredPlannedDay


class RecordingPlanRepository(PlanRepository):
    """Plan repository that records the range requested by the service."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the repository with its session and an empty call log."""
        super().__init__(session)
        self.range_calls: list[tuple[dt.date, dt.date, int]] = []

    @override
    async def get_range(self, start_date: dt.date, end_date: dt.date, user_pk: int) -> list[StoredPlannedDay]:
        """Record the requested range before delegating to the real query."""
        self.range_calls.append((start_date, end_date, user_pk))
        return await super().get_range(start_date, end_date, user_pk)


@time_machine.travel(dt.date(2024, 5, 8))
async def test_week_defaults_to_today_and_queries_seven_days(db_session: AsyncSession):
    repo = RecordingPlanRepository(db_session)
    service = PlanService(repo, RecipeRepository(db_session))

    week = await service.week(1)

    assert repo.range_calls == [(dt.date(2024, 5, 8), dt.date(2024, 5, 14), 1)]
    assert [day.day for day in week.root] == [dt.date(2024, 5, 8) + dt.timedelta(days=offset) for offset in range(7)]


async def test_week_uses_the_exact_start_date(db_session: AsyncSession):
    repo = RecordingPlanRepository(db_session)
    service = PlanService(repo, RecipeRepository(db_session))

    week = await service.week(1, dt.date(2020, 1, 1))

    assert repo.range_calls == [(dt.date(2020, 1, 1), dt.date(2020, 1, 7), 1)]
    assert [day.day for day in week.root] == [dt.date(2020, 1, 1) + dt.timedelta(days=offset) for offset in range(7)]
