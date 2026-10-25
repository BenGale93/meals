import html
import json
import re
import typing as t
from typing import TYPE_CHECKING

from starlette import status

from .assertions import assert_page_shell

if TYPE_CHECKING:
    from httpx import AsyncClient, Response


def timing_state(response: Response) -> dict[str, t.Any]:
    """Return the JSON state the Alpine timing component is initialised with."""
    match = re.search(r"""x-data=(?P<quote>['"])timingApp\((?P<state>\{.*?\})\)(?P=quote)""", response.text)
    assert match is not None

    return t.cast("dict[str, t.Any]", json.loads(html.unescape(match["state"])))


class TestTimingsAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/timings.html")

        assert_page_shell(response)
        assert "Timing Plan" in response.text
        assert 'hx-get="/timings"' in response.text
        assert 'id="timing-container"' in response.text
        assert "Loading timing data..." in response.text

    async def test_get_placeholder_timings(self, client: AsyncClient):
        response = await client.get("/timings")

        assert response.status_code == status.HTTP_200_OK
        state = timing_state(response)
        assert state["pk"] is None
        assert state["finish_time"] == "18:00:00"
        assert state["steps"] == [{"description": "Finish", "offset": 0}]
        assert 'x-init="init()"' in response.text

    async def test_save_uses_form_encoding(self, client: AsyncClient):
        response = await client.get("/timings")

        # The PATCH route reads Form() fields, so the button must not ask HTMX for
        # the (unloaded) json-enc extension.
        assert 'hx-patch="/timings"' in response.text
        assert "json-enc" not in response.text
        assert 'hx-vals="js:' in response.text

    async def test_get_existing_timings(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 0}]'}
        response = await client.patch("/timings", data=new_timings)

        response = await client.get("/timings")
        assert response.status_code == status.HTTP_200_OK
        assert "12:00:00" in response.text

        state = timing_state(response)
        assert state["pk"] is not None
        assert state["finish_time"] == "12:00:00"
        assert state["steps"] == [{"description": "End", "offset": 0}]

    async def test_update_timings(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 0}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.status_code == status.HTTP_200_OK
        assert "Timing saved successfully" in response.text

        check = await client.get("/api/v1/timings")
        pk = check.json().get("pk")

        assert pk is not None

    async def test_update_timings_failure(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 10}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.status_code == status.HTTP_200_OK
        assert "Error saving timings" in response.text

    async def test_alpine_component_initial_state(self, client: AsyncClient):
        steps = [
            {"description": 'Bob\'s "special" <start>', "offset": -60},
            {"description": "Finish", "offset": 0},
        ]
        await client.patch("/timings", data={"finish_time": "18:30:00", "steps": json.dumps(steps)})

        response = await client.get("/timings")

        assert response.status_code == status.HTTP_200_OK
        assert 'x-init="init()"' in response.text

        state = timing_state(response)

        assert state["steps"] == steps
        assert state["finish_time"] == "18:30:00"
        assert state["pk"] is not None

    async def test_alpine_component_step_controls(self, client: AsyncClient):
        response = await client.get("/timings")
        text = response.text

        # The component initialises the stores the Save button reads and exposes
        # the add/remove operations bound to the buttons.
        assert 'Alpine.store("finishTime", this.finishTime)' in text
        assert 'Alpine.store("steps", this.steps)' in text
        assert "steps: initial.steps?.length ? initial.steps : [{ description: 'Finish', offset: 0 }]" in text
        assert "addAboveStep() { this.steps.unshift({ description: '', offset: 0 }) }" in text
        assert "addBelowStep() { this.steps.push({ description: '', offset: 0 }) }" in text
        assert "removeStep(i) { this.steps.splice(i, 1) }" in text

        assert 'x-for="(step, index) in steps"' in text
        assert '@click="addAboveStep()"' in text
        assert '@click="addBelowStep()"' in text
        assert '@click="removeStep(index)"' in text
        assert 'x-show="steps.length &gt; 1"' in text

    async def test_alpine_component_time_calculation(self, client: AsyncClient):
        response = await client.get("/timings")
        text = response.text

        # The finish time drives every step's displayed time, with offsets in minutes.
        assert 'x-model="finishTime"' in text
        assert '@input="recalculate()"' in text
        assert 'x-text="calculateTimeString(step.offset)"' in text
        assert "if (!this.finishTime) return '--:--';" in text
        assert "const [hour, minute] = this.finishTime.split(':').map(Number);" in text
        assert "finish.setHours(hour, minute);" in text
        assert "const start = new Date(finish.getTime() + offset * 60000);" in text
        assert "return start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });" in text
