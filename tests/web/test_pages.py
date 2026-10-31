from typing import TYPE_CHECKING

import pytest
from starlette import status

from meals.web.core import PAGES, Page, PageRegistry

from .assertions import assert_page_shell

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPageRegistry:
    def test_declared_pages_are_registered_in_navigation_order(self):
        assert PageRegistry.pages() == [
            ("Recipes", "/"),
            ("New Recipe", "/new.html"),
            ("Planner", "/plan.html"),
            ("Timings", "/timings.html"),
        ]

    async def test_every_declared_page_is_routed(self, client: AsyncClient):
        for page in PAGES:
            response = await client.get(page.path)

            assert response.status_code == status.HTTP_200_OK

    def test_undeclared_page_cannot_be_registered(self):
        with pytest.raises(ValueError, match="is not declared in PAGES"):
            PageRegistry.register(Page("Missing", "/missing.html"))

    def test_validate_reports_unregistered_pages(self, monkeypatch):
        monkeypatch.setattr(PageRegistry, "_registered", set())

        with pytest.raises(RuntimeError, match="were not registered"):
            PageRegistry.validate()


class TestViewAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/")

        assert_page_shell(response)
        assert 'id="recipe-panel"' in response.text
        assert 'hx-get="/recipes"' in response.text
        assert 'hx-target="#recipe-panel"' in response.text
        assert 'hx-trigger="change"' in response.text
        assert "Add labels to your recipes to filter them" in response.text
        assert 'hx-get="/recipe_list"' not in response.text

    async def test_get_new_recipe(self, client: AsyncClient):
        response = await client.get("/new.html")

        assert_page_shell(response)
        assert "Create a New Recipe" in response.text
        assert 'hx-post="/new_recipe"' in response.text
        assert 'name="name"' in response.text
        assert 'name="ingredients"' in response.text
        assert 'name="instructions"' in response.text

    async def test_page_shells_require_auth(self, bad_client: AsyncClient):
        for path in ["/", "/new.html", "/plan.html", "/timings.html"]:
            response = await bad_client.get(path)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_frontend_assets_are_pinned(self, client: AsyncClient):
        response = await client.get("/")

        assert 'src="https://cdn.tailwindcss.com/3.4.17"' in response.text
        assert 'src="https://unpkg.com/htmx.org@2.0.2/dist/htmx.min.js"' in response.text
        assert 'src="https://unpkg.com/alpinejs@3.17.5/dist/cdn.min.js"' in response.text
