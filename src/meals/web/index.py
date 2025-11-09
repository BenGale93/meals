"""The websites index page."""

import typing as t

from htmy import Component, html

from meals.database.repository import RecipeRepo  # noqa: TC001
from meals.schemas import RecipeResponse, Recipes
from meals.web.core import PageRegistry, htmy_renderer, page, recipe_div, router


def recipes_div(recipes: Recipes) -> html.main:
    """A Div representing all recipes."""
    return html.main(*[recipe_div(recipe) for recipe in recipes], class_="max-w-3xl mx-auto mt-10 p-4 space-y-12")


def recipe_name(recipe: RecipeResponse) -> html.a:
    """Link to a full recipe."""
    return html.a(
        recipe.name,
        href=f"#{recipe.anchor}",
        class_="block p-3 bg-white rounded-xl shadow-sm hover:bg-green-50 hover:text-green-700 transition",
    )


def recipe_names(recipes: Recipes) -> html.section:
    """Links to the full recipe."""
    return html.section(
        html.h2("Contents", class_="text-xl font-semibold mb-3"),
        html.ul(*[html.li(recipe_name(r)) for r in recipes], class_="space-y-2"),
        class_="max-w-3xl mx-auto mt-6 p-4",
    )


PAGE_NAME = "Recipes"


@PageRegistry.register(PAGE_NAME, "/")
def index_page(_: t.Any) -> Component:
    """The HTML of the index page of the app."""
    return page(
        html.div(
            html.div(hx_get="/recipe_list", hx_trigger="load", hx_swap="outerHTML"),
            html.div(hx_get="/recipes", hx_trigger="load", hx_swap="outerHTML"),
        )
    )


@router.get(PageRegistry.route(PAGE_NAME))
@htmy_renderer.page(index_page)
async def index() -> None:
    """The index page of the application."""


@router.get("/recipes")
@htmy_renderer.page(recipes_div)
async def get_recipes(repo: RecipeRepo) -> Recipes:
    """Get the recipes as HTML."""
    recipes = await repo.get_all()

    return Recipes.model_validate(recipes)


@router.get("/recipe_list")
@htmy_renderer.page(recipe_names)
async def recipe_list(repo: RecipeRepo) -> Recipes:
    """Get the recipes as HTML."""
    recipes = await repo.get_all()

    return Recipes.model_validate(recipes)
