"""The meal planner page."""

import typing as t
from datetime import date, timedelta

from fastapi import Form, Query, Response
from htmy import Component, ComponentType, html

from meals.auth import CurrentUser  # noqa: TC001
from meals.schemas import DayToPlan, LabelFilter, Labels, PlannedDays, RecipeSummary  # noqa: TC001
from meals.services import PlanServiceDep, RecipeServiceDep  # noqa: TC001
from meals.web.core import (
    PLANNER_PAGE,
    PageRegistry,
    clear_filter_button,
    htmy_renderer,
    label_filter_controls,
    page,
    router,
    safe_label_filter,
)

if t.TYPE_CHECKING:
    from meals.services import PlanService

PLANNER_SCRIPT = html.script("""
function checkUserKeydown(event) {
  return event instanceof KeyboardEvent
}

document.body.addEventListener('show-success', function(evt) {
    const button = evt.detail.elt;
    const originalText = button.innerHTML;
    button.innerHTML = 'Updated!';
    button.classList.remove('bg-green-100', 'text-green-700', 'hover:bg-green-200');
    button.classList.add('bg-blue-100', 'text-blue-700');
    setTimeout(function() {
        button.innerHTML = originalText;
        button.classList.remove('bg-blue-100', 'text-blue-700');
        button.classList.add('bg-green-100', 'text-green-700', 'hover:bg-green-200');
    }, 2000);
});

document.body.addEventListener('show-error', function(evt) {
    const button = evt.detail.elt;
    const originalText = button.innerHTML;
    button.innerHTML = 'Error!';
    button.classList.remove('bg-green-100', 'text-green-700', 'hover:bg-green-200');
    button.classList.add('bg-red-100', 'text-red-700');
    setTimeout(function() {
        button.innerHTML = originalText;
        button.classList.remove('bg-red-100', 'text-red-700');
        button.classList.add('bg-green-100', 'text-green-700', 'hover:bg-green-200');
    }, 2000);
});
""")


class PlannerWindow(t.NamedTuple):
    """The rolling seven-day window rendered by the planner."""

    start: date
    days: PlannedDays
    today: date

    @property
    def end(self) -> date:
        """The last day in the window."""
        return self.start + timedelta(days=6)

    @property
    def starts_today(self) -> bool:
        """Whether the window starts on today."""
        return self.start == self.today


def meal_input(meal_for_day: str, i: int) -> ComponentType:
    """Takes the name of the meal for the given day."""
    return html.input_(
        list=f"meal-list-{i}",
        name="meal",
        value=meal_for_day,
        hx_get="/meals",
        hx_target=f"#meal-list-{i}",
        hx_trigger="keyup[checkUserKeydown.call(this, event)] changed delay:25ms",
        class_="flex-grow p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
    )


def day_plan(meal_for_day: str, i: int, start: date) -> ComponentType:
    """Plan for a given day."""
    controls: list[ComponentType] = [
        meal_input(meal_for_day, i),
        html.datalist(id=f"meal-list-{i}"),
        html.button(
            "Update",
            type="submit",
            class_="px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
            hx_post=f"/planned_day?start={start.isoformat()}",
            hx_target="#week-panel",
            hx_swap="outerHTML",
            hx_include="closest tr",
        ),
    ]
    if meal_for_day:
        controls.append(
            html.button(
                "Clear",
                type="button",
                class_="px-3 py-1 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition",
                hx_post=f"/planned_day/clear?start={start.isoformat()}",
                hx_target="#week-panel",
                hx_swap="outerHTML",
                hx_include="closest tr",
            )
        )

    return html.div(*controls, class_="flex items-center space-x-2")


def today_control(window: PlannerWindow) -> ComponentType:
    """A link back to the today-at-top window, or a label when already there."""
    if window.starts_today:
        return html.span(
            "Today",
            **{"aria-disabled": "true"},
            class_="px-3 py-1 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed",
        )

    return html.a(
        "Today",
        href="/plan.html",
        hx_get=f"/weeks_plan?start={window.today.isoformat()}",
        hx_target="#week-panel",
        hx_swap="outerHTML",
        hx_push_url="/plan.html",
        class_="px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
    )


def window_nav(window: PlannerWindow) -> ComponentType:
    """Previous/next seven-day navigation and a jump back to today."""
    previous = window.start - timedelta(days=7)
    next_ = window.start + timedelta(days=7)
    link_class = "px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition"
    return html.div(
        html.a(
            "Previous 7 days",
            href=f"/plan.html?start={previous.isoformat()}",
            hx_get=f"/weeks_plan?start={previous.isoformat()}",
            hx_target="#week-panel",
            hx_swap="outerHTML",
            hx_push_url=f"/plan.html?start={previous.isoformat()}",
            class_=link_class,
        ),
        today_control(window),
        html.a(
            "Next 7 days",
            href=f"/plan.html?start={next_.isoformat()}",
            hx_get=f"/weeks_plan?start={next_.isoformat()}",
            hx_target="#week-panel",
            hx_swap="outerHTML",
            hx_push_url=f"/plan.html?start={next_.isoformat()}",
            class_=link_class,
        ),
        class_="flex flex-wrap items-center gap-2",
    )


def window_header(window: PlannerWindow) -> ComponentType:
    """The window date range and navigation controls."""
    return html.div(
        html.h2(
            f"{window.start.strftime('%d %b %Y')} - {window.end.strftime('%d %b %Y')}",
            class_="text-lg font-semibold text-gray-800",
        ),
        window_nav(window),
        class_="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
    )


def planned_day_row(planned_day: DayToPlan, i: int, window: PlannerWindow) -> ComponentType:
    """One row of the planned window."""
    is_today = planned_day.day == window.today
    date_cell: list[ComponentType] = [
        html.div(planned_day.day.strftime("%A"), class_="font-medium"),
        html.div(planned_day.day.strftime("%d %b"), class_="text-xs text-gray-500"),
        html.input_(value=planned_day.day.isoformat(), name="day", type="hidden"),
    ]
    if is_today:
        date_cell.insert(
            1,
            html.span(
                "Today",
                class_="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700",
            ),
        )

    attributes: dict[str, t.Any] = {}
    if is_today:
        attributes["aria-current"] = "date"

    meal_for_day = planned_day.recipe.name if planned_day.recipe else ""
    return html.tr(
        html.td(*date_cell, class_="px-4 py-3"),
        html.td(day_plan(meal_for_day, i, window.start), class_="px-4 py-3"),
        class_="bg-green-50" if is_today else "hover:bg-gray-50",
        **attributes,
    )


def planned_week_div(window: PlannerWindow) -> ComponentType:
    """The rolling seven-day plan table."""
    table_rows = [planned_day_row(planned_day, i, window) for i, planned_day in enumerate(window.days.root)]

    return html.section(
        window_header(window),
        html.table(
            html.thead(
                html.tr(
                    html.th("Date", class_="px-4 py-2 text-left text-gray-600"),
                    html.th("Meal", class_="px-4 py-2 text-left text-gray-600"),
                ),
                class_="bg-gray-100",
            ),
            html.tbody(*table_rows, class_="divide-y divide-gray-200"),
            class_="min-w-full bg-white border border-gray-300 rounded-lg shadow-sm",
        ),
        id="week-panel",
        class_="space-y-3",
    )


def meal_options(meal_names: list[str]) -> ComponentType:
    """Meal options for the drop down."""
    return html.datalist(*[html.option(value=m) for m in meal_names])


class SummaryPanel(t.NamedTuple):
    """The data rendered by the recipe summary panel."""

    summaries: list[RecipeSummary]
    labels: Labels
    selected: LabelFilter


def summary_table(panel: SummaryPanel) -> ComponentType:
    """The filterable summary table for the meals."""
    table_rows = []
    for summary in panel.summaries:
        last_eaten = summary.last_eaten.strftime("%Y-%m-%d") if summary.last_eaten else "Never"
        table_rows.append(
            html.tr(
                html.td(summary.name, class_="px-4 py-3"),
                html.td(str(summary.count), class_="px-4 py-3"),
                html.td(last_eaten, class_="px-4 py-3"),
                class_="hover:bg-gray-50",
            )
        )

    return html.form(
        html.div(
            html.h2("Recipe Summary", class_="text-xl font-semibold text-gray-800 mb-4"),
            html.button(
                "Refresh",
                type="button",
                hx_get="/summary",
                hx_target="#recipe-summary",
                hx_swap="outerHTML",
                hx_include="closest form",
                class_="px-3 py-1 mb-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
            ),
            class_="flex justify-between",
        ),
        label_filter_controls(panel.labels, panel.selected, endpoint="/summary", target="#recipe-summary"),
        clear_filter_button("/summary", "#recipe-summary"),
        html.table(
            html.thead(
                html.tr(
                    html.th("Recipe", class_="px-4 py-2 text-left text-gray-600"),
                    html.th("Count", class_="px-4 py-2 text-left text-gray-600"),
                    html.th("Last Eaten", class_="px-4 py-2 text-left text-gray-600"),
                ),
                class_="bg-gray-100",
            ),
            html.tbody(*table_rows, class_="divide-y divide-gray-200"),
            class_="min-w-full bg-white border border-gray-300 rounded-lg shadow-sm",
        ),
        hx_get="/summary",
        hx_swap="outerHTML",
        hx_target="#recipe-summary",
        hx_trigger="change",
        class_="max-w-3xl mx-auto mt-6 p-4",
        id="recipe-summary",
    )


async def _window_for(service: PlanService, user_pk: int, start: date | None = None) -> PlannerWindow:
    """Build the planner window for a request, defaulting to today."""
    today = date.today()
    first_day = start or today
    days = await service.week(user_pk, first_day)
    return PlannerWindow(start=first_day, days=days, today=today)


@PageRegistry.register(PLANNER_PAGE)
def plan_page(window: PlannerWindow) -> Component:
    """The HTML of the plan page of the app."""
    return page(
        html.div(
            html.main(
                html.h1("Weekly Meal Plan", class_="text-2xl font-bold text-green-700 mb-6"),
                planned_week_div(window),
                html.div(hx_get="/summary", hx_trigger="load", hx_swap="outerHTML"),
                class_="max-w-3xl mx-auto p-6 mt-8 bg-white shadow-md rounded-2xl",
            ),
            PLANNER_SCRIPT,
        )
    )


@router.get(PLANNER_PAGE.path)
@htmy_renderer.page(plan_page)
async def plan(
    service: PlanServiceDep,
    user: CurrentUser,
    start: t.Annotated[date | None, Query()] = None,
) -> PlannerWindow:
    """The index page of the application."""
    return await _window_for(service, user.pk, start)


@router.get("/weeks_plan", response_model=None)
@htmy_renderer.page(planned_week_div)
async def weeks_plan(
    service: PlanServiceDep,
    user: CurrentUser,
    start: t.Annotated[date | None, Query()] = None,
) -> PlannerWindow:
    """Gets the rolling seven-day plan."""
    return await _window_for(service, user.pk, start)


@router.get("/meals", response_model=None)
@htmy_renderer.page(meal_options)
async def meals_like(meal: str, service: RecipeServiceDep, user: CurrentUser) -> list[str]:
    """Return meals like the string provided."""
    meals = await service.like(meal, user.pk)

    return [m.name for m in meals]


@router.post("/planned_day", response_model=None)
@htmy_renderer.page(planned_week_div)
async def update_planned_day(  # noqa: PLR0913, PLR0917
    response: Response,
    day: t.Annotated[date, Form()],
    service: PlanServiceDep,
    user: CurrentUser,
    start: t.Annotated[date | None, Query()] = None,
    meal: t.Annotated[str, Form()] = "",
) -> PlannerWindow:
    """Plan a meal and re-render the viewed window."""
    planned_day = await service.plan_by_meal_name(meal, day, user.pk)
    if planned_day is None:
        response.headers["HX-Trigger"] = "show-error"
        response.headers["HX-Reswap"] = "none"
    else:
        response.headers["HX-Trigger"] = "show-success"

    return await _window_for(service, user.pk, start)


@router.post("/planned_day/clear", response_model=None)
@htmy_renderer.page(planned_week_div)
async def clear_planned_day(
    day: t.Annotated[date, Form()],
    start: t.Annotated[date, Query()],
    service: PlanServiceDep,
    user: CurrentUser,
) -> PlannerWindow:
    """Clear the plan for a day and re-render the viewed window."""
    await service.clear(day, user.pk)
    return await _window_for(service, user.pk, start)


@router.get("/summary", response_model=None)
@htmy_renderer.page(summary_table)
async def get_summary_table(
    service: PlanServiceDep,
    recipe_service: RecipeServiceDep,
    user: CurrentUser,
    labels: t.Annotated[list[str], Query(default_factory=list)],
) -> SummaryPanel:
    """Gets the filtered summary table of the recipes."""
    selected = safe_label_filter(labels)
    return SummaryPanel(
        summaries=await service.summary(user.pk, label_filter=selected),
        labels=await recipe_service.labels(),
        selected=selected,
    )
