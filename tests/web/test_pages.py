from typing import TYPE_CHECKING

from inline_snapshot import external
from starlette import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestViewAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/")

        assert response.text == external("uuid:c2fba73d-0743-47cb-93b3-13735fa031f8.txt")

    async def test_get_new_recipe(self, client: AsyncClient):
        response = await client.get("/new.html")

        assert response.text == external("uuid:efb61175-7f7a-4a21-be06-fada95992420.txt")

    async def test_page_shells_require_auth(self, bad_client: AsyncClient):
        for path in ["/", "/new.html", "/plan.html", "/timings.html"]:
            response = await bad_client.get(path)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_frontend_assets_are_pinned(self, client: AsyncClient):
        response = await client.get("/")

        assert 'src="https://cdn.tailwindcss.com/3.4.19"' in response.text
        assert 'src="https://unpkg.com/htmx.org@2.0.2/dist/htmx.min.js"' in response.text
        assert 'src="https://unpkg.com/alpinejs@3.17.5/dist/cdn.min.js"' in response.text
