"""The websites timing management page."""

import typing as t
from datetime import time

from fastapi import Form
from htmy import Component, html

from meals.database.repository import TimingRepo  # noqa: TC001
from meals.schemas import (
    RecipeStep,
    TimingsCreate,
    TimingsResponse,
    TimingSteps,
)
from meals.web.core import PageRegistry, htmy_renderer, page, router

PAGE_NAME = "Timings"

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


def description_input() -> html.input_:
    """Step description input."""
    return html.input_(
        type="text",
        x_model="step.description",
        placeholder="Step Description",
        class_="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 "
        "focus:ring-green-500 focus:outline-none sm:mb-0",
    )


def offset_input() -> html.input_:
    """Step offset input."""
    return html.input_(
        **{"x-model.number": "step.offset"},
        type="number",
        class_="w-20 p-2 border border-gray-300 rounded-lg focus:ring-2 "
        "focus:ring-green-500 focus:outline-none text-right",
    )


def computed_time() -> html.div:
    """The time compute using the finish time and offset."""
    return html.div(
        html.template(html.span(x_text="calculateTimeString(step.offset)"), x_if="finishTime"),
        class_="text-lg text-gray-700 font-medium sm:w-28 text-center sm:mt-0",
    )


def step_delete() -> html.button:
    """Button to delete a step."""
    return html.button(
        "x",
        **{
            "type": "button",
            "@click": "removeStep(index)",
            "x-show": "steps.length > 1",
            "class": "text-red-500 hover:text-red-700 ml-2 font-bold text-lg",
        },
    )


def steps_div() -> html.div:
    """Timings step div."""
    return html.div(
        html.template(
            html.div(
                description_input(),
                offset_input(),
                computed_time(),
                step_delete(),
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


def timings_div(timings: TimingsResponse) -> html.div:
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


def update_timings_div(_: t.Any) -> html.div:
    """Component returned when an attempt to update the timings succeeds."""
    return html.div(
        "Timing saved successfully", class_="p-4 bg-green-50 border border-green-200 text-green-800 rounded-lg mb-4"
    )


def failed_to_update_timings_div(error: Exception) -> html.div:  # noqa: ARG001
    """Component returned when an attempt to update the timings fails."""
    return html.div("Error saving timings", class_="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg mb-4")


@PageRegistry.register(PAGE_NAME, "/timings.html")
def timings_page(_: t.Any) -> Component:
    """The HTML of the timings page of the app."""
    return page(
        html.main(
            html.h1("Timing Plan", class_="text-2xl font-bold text-green-700 mb-6"),
            html.div(
                html.div("Loading timing data...", class_="test-gray-400 italic"),
                hx_get="/timings",
                hx_trigger="load",
                hx_target="#timing-container",
                hx_swap="innerHTML",
                id="timing-container",
            ),
            class_="max-w-3xl mx-auto p-6 mt-8 bg-white shadow-md rounded-2xl",
        )
    )


@router.get(PageRegistry.route(PAGE_NAME))
@htmy_renderer.page(timings_page)
async def timings() -> None:
    """The timings pag of the application."""


@router.get("/timings")
@htmy_renderer.page(timings_div)
async def get_timings(repo: TimingRepo) -> TimingsResponse:
    """Get the timings as HTML."""
    timings = await repo.get()

    if timings is None:
        return TimingsResponse(
            pk=None,
            finish_time=time(18, 0, 0),
            steps=TimingSteps([RecipeStep(description="Finish", offset=0)]),
        )
    steps = TimingSteps.model_validate_json(timings.steps)

    return TimingsResponse(pk=timings.pk, steps=steps, finish_time=timings.finish_time)


@router.patch("/timings")
@htmy_renderer.page(update_timings_div, error_component_selector=failed_to_update_timings_div)
async def update_timings(
    finish_time: t.Annotated[str, Form()], steps: t.Annotated[str, Form()], repo: TimingRepo
) -> None:
    """Get the timings as HTML."""
    timings_data = TimingsCreate.model_validate(
        {"finish_time": finish_time, "steps": TimingSteps.model_validate_json(steps)}
    )
    await repo.update(timings_data)
