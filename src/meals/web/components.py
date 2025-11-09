"""HTML components for website elements."""

import typing as t

from htmy import Component, ComponentType, Context, SafeStr, component, html
from pydantic import ValidationError

from meals.exceptions import RecipeAlreadyExistsError

if t.TYPE_CHECKING:
    from datetime import time

    from pydantic_core import ErrorDetails

    from meals.schemas import IngredientResponse, RecipeResponse, Recipes, TimingsResponse


@component
def ingredient_div(ingredient: IngredientResponse, _context: Context) -> Component:
    """A Div representing an ingredient."""
    return html.div(f"{ingredient.name} {ingredient.quantity} {ingredient.unit}")


@component
def recipe_div(recipe: RecipeResponse, _context: Context) -> Component:
    """A Div representing a recipe."""
    return html.section(
        html.h2(recipe.name, class_="text-2xl font-bold text-green-700 mb-3"),
        html.ul(*[html.li(ingredient_div(i)) for i in recipe.ingredients], class_="list-disc ml-5 mb-4"),
        html.p(recipe.instructions, style="white-space:pre-line;"),
        class_="bg-white rounded-2xl shadow-md p-6",
        id=recipe.anchor,
    )


@component
def recipes_div(recipes: Recipes, _context: Context) -> Component:
    """A Div representing all recipes."""
    return html.main(*[recipe_div(recipe) for recipe in recipes], class_="max-w-3xl mx-auto mt-10 p-4 space-y-12")


@component
def recipe_name(recipe: RecipeResponse, _context: Context) -> Component:
    """Link to a full recipe."""
    return html.a(
        recipe.name,
        href=f"#{recipe.anchor}",
        class_="block p-3 bg-white rounded-xl shadow-sm hover:bg-green-50 hover:text-green-700 transition",
    )


@component
def recipe_names(recipes: Recipes, _context: Context) -> Component:
    """Links to the full recipe."""
    return html.section(
        html.h2("Contents", class_="text-xl font-semibold mb-3"),
        html.ul(*[html.li(recipe_name(r)) for r in recipes], class_="space-y-2"),
        class_="max-w-3xl mx-auto mt-6 p-4",
    )


BURGER_SVG = SafeStr("""
<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-green-700" fill="none"
           viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path x-show="!open" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    <path x-show="open" stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
</svg>
""")


@component
def nav_bar(pages: t.Sequence[tuple[str, str]], _context: Context) -> Component:
    """Navigation bar with links for mobile and desktop."""
    mobile_links = [
        html.a(
            name,
            href=href,
            class_="block text-green-700 font-medium p-2 rounded-lg hover:bg-green-50 transition",
        )
        for name, href in pages
    ]
    desktop_links = [
        html.a(name, href=href, class_="text-green-700 hover:text-green-800 font-medium transition")
        for name, href in pages
    ]
    return (
        html.div(
            html.a("My Recipes", href="#", class_="text-2xl font-bold text-green-600"),
            html.button(
                BURGER_SVG,
                class_="md:hidden focus:outline-none",
                **{
                    "@click": "open = !open",
                },
            ),
            html.nav(
                *desktop_links,
                class_="hidden md:flex space-x-6",
            ),
            html.nav(
                html.ul(
                    html.li(*mobile_links),
                    class_="flex flex-col p-4 space-y-2",
                ),
                **{"x-show": "open", "x-transition": ""},
                class_="md:hidden bg-white border-t border-gray-100 shadow-inner",
            ),
            class_="max-w-3xl mx-auto p-4 flex justify-between items-center",
        ),
    )


@component
def new_recipe_error(error: Exception, _context: Context) -> Component:
    """Component returned when an error occurs adding a new recipe."""
    messages: list[ComponentType]
    if isinstance(error, RecipeAlreadyExistsError):
        messages = [error.message]
    elif isinstance(error, ValidationError):
        messages = [html.p(format_new_recipe_error(e)) for e in error.errors()]
        messages = ["❌ Error(s) adding recipe", html.br(), *messages]
    else:  # pragma: no cover # If we knew how to trigger this, we would handle it better
        # TODO: add logging here
        messages = ["Unexpected error adding a recipe"]
    return html.div(
        *messages,
        class_="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg",
    )


def format_new_recipe_error(error: ErrorDetails) -> str:
    """Formats the error message to be more useful to end user."""
    msg = error["msg"].removeprefix("Value error, ")

    match error["loc"]:
        case ("ingredients", number, *_) if isinstance(number, int):
            number = number + 1
            return f"Issue with ingredient {number}: {msg}"
        case _:  # pragma: no cover # If we knew how to trigger this, we would handle it better
            return f"Unknown error: {error}"


TIMINGS_SCRIPT = html.script("""
function timingApp(initial) {
    return {
    finishTime: initial.finish_time || '',
    steps: initial.steps?.length ? initial.steps : [{ description: 'Finish', offset: 0 }],
    init() {
        Alpine.store("finishTime", this.finishTime);
        Alpine.store("steps", this.steps);
    },
    addAboveStep() { this.steps.unshift({ description: '', offset: 0 }) },
    addBelowStep() { this.steps.push({ description: '', offset: 0 }) },
    removeStep(i) { this.steps.splice(i, 1) },
    recalculate() {},
    calculateTimeString(offset) {
        if (!this.finishTime) return '--:--';
        const [hour, minute] = this.finishTime.split(':').map(Number);
        const finish = new Date();
        finish.setHours(hour, minute);
        const start = new Date(finish.getTime() + offset * 60000);
        return start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    }
}
""")


def finish_time_div(finish_time: time) -> html.div:
    """Input for the timings finish time."""
    return html.div(
        html.label("Target Finish Time", class_="block font-semibold mb-1"),
        html.input_(**{"type": "time", "x-model": "finishTime", "@input": "recalculate()", "value": finish_time}),
        class_="mb-6",
    )


def steps_div() -> html.div:
    """Timings step div."""
    return html.div(
        html.template(
            html.div(
                html.input_(
                    type="text",
                    x_model="step.description",
                    placeholder="Step Description",
                    class_="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 "
                    "focus:ring-green-500 focus:outline-none sm:mb-0",
                ),
                html.input_(
                    **{"x-model.number": "step.offset"},
                    type="number",
                    class_="w-20 p-2 border border-gray-300 rounded-lg focus:ring-2 "
                    "focus:ring-green-500 focus:outline-none text-right",
                ),
                html.div(
                    html.template(html.span(x_text="calculateTimeString(step.offset)"), x_if="finishTime"),
                    class_="text-lg text-gray-700 font-medium sm:w-28 text-center sm:mt-0",
                ),
                html.button(
                    "x",
                    **{
                        "type": "button",
                        "@click": "removeStep(index)",
                        "x-show": "steps.length > 1",
                        "class": "text-red-500 hover:text-red-700 ml-2 font-bold text-lg",
                    },
                ),
                class_="flex flex-row items-center space-x-3 bg-gray-50 p-3 rounded-lg border border-gray-200",
            ),
            **{"x-for": "(step, index) in steps", ":key": "index"},
        ),
        class_="space-y-3",
    )


def save_timing() -> html.div:
    """Save timing button."""
    return html.div(
        html.button(
            "Save Timing",
            type="button",
            hx_patch="/timings",
            hx_vals="js:{'finish_time': Alpine.store('finishTime'), 'steps': JSON.stringify(Alpine.store('steps'))}",
            hx_target="#form-result",
            hx_swap="innerHTML",
            hx_ext="json-enc",
            class_="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition",
        ),
        class_="mt-6 text-right",
    )


def add_step(position: t.Literal["Above", "Below"]) -> html.div:
    """Add timing step button.

    Args:
        position: When clicked, whether the button adds the new step above or below.
    """
    return html.div(
        html.button(
            "+ Add Step",
            **{
                "type": "button",
                "@click": f"add{position}Step()",
                "class": "px-3 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
            },
        ),
        class_="mt-4",
    )


@component
def timings_div(timings: TimingsResponse, _context: Context) -> Component:
    """Timing editor component."""
    timing_json = timings.model_dump_json()
    return html.div(
        finish_time_div(timings.finish_time),
        add_step("Above"),
        steps_div(),
        add_step("Below"),
        save_timing(),
        html.div(id="form-result", class_="mt-6"),
        TIMINGS_SCRIPT,
        x_data=f"timingApp({timing_json})",
        x_init="init()",
    )


@component
def update_timings_div(_: t.Any, _context: Context) -> Component:
    """Component returned when an attempt to update the timings succeeds."""
    return html.div(
        "Timing saved successfully", class_="p-4 bg-green-50 border border-green-200 text-green-800 rounded-lg mb-4"
    )


@component
def failed_to_update_timings_div(error: Exception, _context: Context) -> Component:  # noqa: ARG001
    """Component returned when an attempt to update the timings fails."""
    return html.div("Error saving timings", class_="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg mb-4")
