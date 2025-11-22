"""The meal planner page."""

import typing as t
from datetime import date, timedelta

from fastapi import Form, Response
from htmy import Component, html

from meals.database.repository import PlanRepo, RecipeRepo  # noqa: TC001
from meals.schemas import DayToPlan, PlannedDay, PlannedDays, PlannedRecipe, RecipeSummary
from meals.web.core import PageRegistry, htmy_renderer, page, router

PAGE_NAME = "Planner"

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


def meal_input(meal_for_day: str, i: int) -> html.input_:
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


def day_plan(meal_for_day: str, i: int) -> html.div:
    """Plan for a given day."""
    return html.div(
        meal_input(meal_for_day, i),
        html.datalist(id=f"meal-list-{i}"),
        html.button(
            "Update",
            type="submit",
            class_="px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
            hx_post="/planned_day",
            hx_swap="none",
            hx_include="closest tr",
        ),
        class_="flex items-center space-x-2",
    )


def planned_week_div(current_plan: PlannedDays) -> html.table:
    """The planned week table."""
    table_rows = []
    for i, planned_day in enumerate(current_plan.root):
        current_date = planned_day.day.strftime("%Y-%m-%d")
        current_day = planned_day.day.strftime("%A")
        meal_for_day = planned_day.recipe.name if planned_day.recipe else ""
        table_rows.append(
            html.tr(
                html.td(current_day, html.input_(value=current_date, name="day", type="hidden"), class_="px-4 py-3"),
                html.td(
                    day_plan(meal_for_day, i),
                    class_="px-4 py-3",
                ),
                class_="hover:bg-gray-50",
            )
        )

    return html.table(
        html.thead(
            html.tr(
                html.th("Date", class_="px-4 py-2 text-left text-gray-600"),
                html.th("Meal", class_="px-4 py-2 text-left text-gray-600"),
            ),
            class_="bg-gray-100",
        ),
        html.tbody(*table_rows, class_="divide-y divide-gray-200"),
        class_="min-w-full bg-white border border-gray-300 rounded-lg shadow-sm",
    )


def meal_options(meal_names: list[str]) -> html.datalist:
    """Meal options for the drop down."""
    return html.datalist(*[html.option(value=m) for m in meal_names])


def summary_table(summaries: list[RecipeSummary]) -> html.section:
    """The summary table for the meals."""
    table_rows = []
    for summary in summaries:
        last_eaten = summary.last_eaten.strftime("%Y-%m-%d") if summary.last_eaten else "Never"
        table_rows.append(
            html.tr(
                html.td(summary.name, class_="px-4 py-3"),
                html.td(str(summary.count), class_="px-4 py-3"),
                html.td(last_eaten, class_="px-4 py-3"),
                class_="hover:bg-gray-50",
            )
        )

    return html.section(
        html.div(
            html.h2("Recipe Summary", class_="text-xl font-semibold text-gray-800 mb-4"),
            html.button(
                "Refresh",
                type="submit",
                class_="px-3 py-1 mb-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
                hx_get="/summary",
                hx_swap="outerHTML",
                hx_target="#recipe-summary",
            ),
            class_="flex justify-between",
        ),
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
        class_="max-w-3xl mx-auto mt-6 p-4",
        id="recipe-summary",
    )


@PageRegistry.register(PAGE_NAME, "/plan.html")
def plan_page(_: t.Any) -> Component:
    """The HTML of the plan page of the app."""
    return page(
        html.div(
            html.main(
                html.h1("Weekly Meal Plan", class_="text-2xl font-bold text-green-700 mb-6"),
                html.div(hx_get="/weeks_plan", hx_trigger="load", hx_swap="outerHTML"),
                html.div(hx_get="/summary", hx_trigger="load", hx_swap="outerHTML"),
                class_="max-w-3xl mx-auto p-6 mt-8 bg-white shadow-md rounded-2xl",
            ),
            PLANNER_SCRIPT,
        )
    )


@router.get(PageRegistry.route(PAGE_NAME))
@htmy_renderer.page(plan_page)
async def plan() -> None:
    """The index page of the application."""


@router.get("/weeks_plan", response_model=None)
@htmy_renderer.page(planned_week_div)
async def weeks_plan(repo: PlanRepo) -> PlannedDays:
    """Gets the plan for the week."""
    today = date.today()

    next_week = today + timedelta(days=7)

    raw_plan = await repo.get_range(today, next_week)

    days_to_plan = []
    for i in range(7):
        day = today + timedelta(days=i)
        planned_day = DayToPlan(day=day, recipe=None)
        for raw_day in raw_plan:
            if day != raw_day.day:
                continue
            planned_day.recipe = PlannedRecipe(pk=raw_day.recipe_pk, name=raw_day.recipe.name)
            break
        days_to_plan.append(planned_day)

    return PlannedDays(days_to_plan)


@router.get("/meals", response_model=None)
@htmy_renderer.page(meal_options)
async def meals_like(meal: str, repo: RecipeRepo) -> list[str]:
    """Return meals like the string provided."""
    meals = await repo.is_like(meal)

    return [m.name for m in meals]


@router.post("/planned_day", response_model=None)
async def update_planned_day(
    response: Response,
    meal: t.Annotated[str, Form()],
    day: t.Annotated[date, Form()],
    plan_repo: PlanRepo,
    recipe_repo: RecipeRepo,
) -> None:
    """Return meals like the string provided."""
    recipe = await recipe_repo.get_by_name(meal)
    if recipe is None:
        response.headers["HX-Trigger"] = "show-error"
        return

    planned_day = PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name))
    await plan_repo.update(planned_day)
    response.headers["HX-Trigger"] = "show-success"


@router.get("/summary", response_model=None)
@htmy_renderer.page(summary_table)
async def get_summary_table(repo: PlanRepo) -> list[RecipeSummary]:
    """Gets the summary table of the recipes."""
    summary = await repo.summarise()

    return [RecipeSummary(name=s[0], count=s[1], last_eaten=s[2]) for s in summary]
