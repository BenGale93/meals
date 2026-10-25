"""The websites index page."""

import typing as t

from fastapi import Form, HTTPException, status
from htmy import Component, ComponentType, html
from pydantic import ValidationError

from meals.auth import CurrentUser  # noqa: TC001
from meals.exceptions import RecipeDoesNotExistError
from meals.schemas import IngredientResponse, RecipeResponse, Recipes, UpdateRecipeRequest
from meals.services import RecipeServiceDep  # noqa: TC001
from meals.web.core import (
    RECIPES_PAGE,
    PageRegistry,
    clean_ingredients,
    editable_recipe_section,
    format_new_recipe_error,
    htmy_renderer,
    page,
    router,
)


def recipes_div(recipes: Recipes) -> ComponentType:
    """A Div representing all recipes."""
    return html.main(
        *[editable_recipe_section(recipe) for recipe in recipes], class_="max-w-3xl mx-auto mt-10 p-4 space-y-12"
    )


def recipe_name(recipe: RecipeResponse) -> ComponentType:
    """Link to a full recipe."""
    return html.a(
        recipe.name,
        href=f"#{recipe.anchor}",
        class_="block p-3 bg-white rounded-xl shadow-sm hover:bg-green-50 hover:text-green-700 transition",
    )


def recipe_names(recipes: Recipes) -> ComponentType:
    """Links to the full recipe."""
    return html.section(
        html.h2("Contents", class_="text-xl font-semibold mb-3"),
        html.ul(*[html.li(recipe_name(r)) for r in recipes], class_="space-y-2"),
        class_="max-w-3xl mx-auto mt-6 p-4",
    )


def update_recipe_error(error: Exception) -> ComponentType:
    """Component returned when an error occurs updating a recipe."""
    messages: list[ComponentType]
    if isinstance(error, ValidationError):
        messages = [
            "❌ Error(s) updating recipe",
            html.br(),
            *[html.p(format_new_recipe_error(e)) for e in error.errors()],
        ]
    else:
        messages = [f"Error updating recipe: {error}"]
    return html.div(*messages, class_="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg mb-4")


def edit_recipe_name(current_name: str) -> ComponentType:
    """Input for setting the recipe name."""
    return html.div(
        html.label("Recipe Name", class_="block font-semibold mb-1", **{"for": "name"}),
        html.input_(
            value=current_name,
            id="name",
            name="name",
            type="text",
            required="",
            class_="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
        ),
    )


def ingredient_details(ingredient: IngredientResponse) -> ComponentType:
    """Details of the ingredient."""
    return html.div(
        html.input_(
            **{
                "value": str(ingredient),
                "type": "text",
                "name": "ingredients",
                "x-model": "ingredients[index]",
            },
            class_="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
        ),
        html.button(
            "×",  # noqa: RUF001
            **{
                "type": "button",
                "@click": "ingredients.splice(index, 1)",
                "x-show": "ingredients.length > 1",
            },
            class_="text-red-500 hover:text-red-700 font-bold text-xl",
        ),
        class_="flex items-center mb-2 space-x-2",
    )


def add_ingredient() -> ComponentType:
    """Button to add another ingredient."""
    return html.button(
        "+ Add Ingredient",
        **{"type": "button", "@click": "ingredients.push('')"},
        class_="mt-2 px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
    )


def edit_instructions_input(current_instructions: str) -> ComponentType:
    """Input for specifying the recipe's instructions."""
    return html.div(
        html.label("Instructions", class_="block font-semibold mb-1", **{"for": "instructions"}),
        html.textarea(
            current_instructions,
            id="instructions",
            name="instructions",
            rows="6",
            required="",
            class_="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
        ),
    )


def edit_recipe_div(recipe: RecipeResponse) -> ComponentType:
    """Component for editing recipes."""
    ingredient_data = [str(i) for i in recipe.ingredients]
    return html.form(
        edit_recipe_name(recipe.name),
        html.div(
            html.label("Ingredients", class_="block font-semibold mb-1"),
            html.template(
                *[ingredient_details(i) for i in recipe.ingredients],
                **{
                    "x-for": "(ingredient, index) in ingredients",
                    ":key": "index",
                },
            ),
            add_ingredient(),
            **{
                "x-data": f"{{ingredients: {ingredient_data} }}",
            },
        ),
        edit_instructions_input(recipe.instructions),
        html.button(
            "Submit",
            type="submit",
            class_="px-4 py-1 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition",
        ),
        html.button(
            "Cancel",
            hx_get=f"/recipe/{recipe.pk}",
            class_="px-4 py-1 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition",
        ),
        hx_post=f"/update_recipe/{recipe.pk}",
        hx_target="this",
        hx_swap="outerHTML",
        class_="bg-white rounded-2xl shadow-md p-6",
    )


@PageRegistry.register(RECIPES_PAGE)
def index_page(_: t.Any) -> Component:
    """The HTML of the index page of the app."""
    return page(
        html.div(
            html.div(hx_get="/recipe_list", hx_trigger="load", hx_swap="outerHTML"),
            html.div(hx_get="/recipes", hx_trigger="load", hx_swap="outerHTML"),
        )
    )


@router.get(RECIPES_PAGE.path)
@htmy_renderer.page(index_page)
async def index(_: CurrentUser) -> None:
    """The index page of the application."""


@router.get("/recipes")
@htmy_renderer.page(recipes_div)
async def get_recipes(service: RecipeServiceDep, user: CurrentUser) -> Recipes:
    """Get the recipes as HTML."""
    return await service.list(user.pk)


@router.get("/recipe_list")
@htmy_renderer.page(recipe_names)
async def recipe_list(service: RecipeServiceDep, user: CurrentUser) -> Recipes:
    """Get the recipes as HTML."""
    return await service.list(user.pk)


@router.post("/update_recipe/{pk}", response_model=None)
@htmy_renderer.page(editable_recipe_section, error_component_selector=update_recipe_error)
async def update_recipe(  # noqa: PLR0913, PLR0917
    pk: int,
    service: RecipeServiceDep,
    user: CurrentUser,
    ingredients: t.Annotated[list[str], Form()],
    name: t.Annotated[str, Form()] = "",
    instructions: t.Annotated[str, Form()] = "",
) -> RecipeResponse:
    """Create a new recipe using a form."""
    recipe_data = UpdateRecipeRequest.model_validate(
        {"pk": pk, "name": name, "ingredients": clean_ingredients(ingredients), "instructions": instructions}
    )

    return await service.update(recipe_data, user.pk)


@router.get("/recipe/{pk}/edit", response_model=None)
@htmy_renderer.page(edit_recipe_div)
async def edit_recipe(pk: int, service: RecipeServiceDep, user: CurrentUser) -> RecipeResponse:
    """Create a new recipe using a form."""
    try:
        return await service.get(pk, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None


@router.get("/recipe/{pk}", response_model=None)
@htmy_renderer.page(editable_recipe_section)
async def get_recipe(pk: int, service: RecipeServiceDep, user: CurrentUser) -> RecipeResponse:
    """Create a new recipe using a form."""
    try:
        return await service.get(pk, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None
