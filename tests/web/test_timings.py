import html
import json
import re
from typing import TYPE_CHECKING

from inline_snapshot import external
from starlette import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestTimingsAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/timings.html")

        assert response.text == external("uuid:4f1d948c-f93c-45aa-8a23-9f6313ce0029.txt")

    async def test_get_placeholder_timings(self, client: AsyncClient):
        response = await client.get("/timings")
        assert response.text == external("uuid:c7fc40cc-df47-4d31-b9d6-8e854e9042f3.txt")
        assert response.status_code == status.HTTP_200_OK

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
        assert response.text == external("uuid:d2116b7b-a0d7-4b66-8e69-b8a6e91a77d1.txt")
        assert response.status_code == status.HTTP_200_OK
        assert "12:00:00" in response.text

    async def test_update_timings(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 0}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.text == external("uuid:2646a836-6c9e-4f73-a93c-b47f075457f0.txt")
        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/timings")
        pk = check.json().get("pk")

        assert pk is not None

    async def test_update_timings_failure(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 10}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.text == external("uuid:f577cc02-d394-4019-b6fa-50584bbebff0.txt")
        assert "Error" in response.text

    async def test_alpine_component_initial_state(self, client: AsyncClient):
        steps = [
            {"description": 'Bob\'s "special" <start>', "offset": -60},
            {"description": "Finish", "offset": 0},
        ]
        await client.patch("/timings", data={"finish_time": "18:30:00", "steps": json.dumps(steps)})

        response = await client.get("/timings")

        assert response.status_code == status.HTTP_200_OK
        assert 'x-init="init()"' in response.text

        match = re.search(r"""x-data=(?P<quote>['"])timingApp\((?P<state>\{.*?\})\)(?P=quote)""", response.text)
        assert match is not None

        state = json.loads(html.unescape(match["state"]))

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
