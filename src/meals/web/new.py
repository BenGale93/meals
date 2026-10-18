"""The websites new recipe page."""

import typing as t

from fastapi import Form
from htmy import Component, ComponentType, html
from pydantic import ValidationError

from meals.auth import CurrentUser  # noqa: TC001
from meals.exceptions import RecipeAlreadyExistsError
from meals.schemas import CreateRecipeRequest, RecipeResponse
from meals.services import RecipeServiceDep  # noqa: TC001
from meals.web.core import (
    PageRegistry,
    clean_ingredients,
    format_new_recipe_error,
    htmy_renderer,
    page,
    recipe_section,
    router,
)


def new_recipe_error(error: Exception) -> html.div:
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


PAGE_NAME = "New Recipe"


def recipe_name() -> html.div:
    """Input for setting the recipe name."""
    return html.div(
        html.label("Recipe Name", class_="block font-semibold mb-1", **{"for": "name"}),
        html.input_(
            id="name",
            name="name",
            type="text",
            required="",
            class_="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
        ),
    )


def ingredient_details() -> html.div:
    """Details of the ingredient."""
    return html.div(
        html.input_(
            **{
                "type": "text",
                "name": "ingredients",
                "x-model": "ingredients[index]",
                "placeholder": "Flour 2 cups",
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


def add_ingredient() -> html.button:
    """Button to add another ingredient."""
    return html.button(
        "+ Add Ingredient",
        **{"type": "button", "@click": "ingredients.push('')"},
        class_="mt-2 px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
    )


def instructions_input() -> html.div:
    """Input for specifying the recipe's instructions."""
    return html.div(
        html.label("Instructions", class_="block font-semibold mb-1", **{"for": "instructions"}),
        html.textarea(
            id="instructions",
            name="instructions",
            rows="6",
            placeholder="Describe the preparation steps here...",
            class_="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none",
        ),
    )


def save_recipe() -> html.div:
    """Button for saving the recipe."""
    return html.div(
        html.button(
            "Save Recipe",
            type="submit",
            class_="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition",
        ),
        class_="text-right",
    )


def new_recipe_form() -> html.form:
    """Form for submitting a new recipe."""
    return html.form(
        recipe_name(),
        html.div(
            html.label("Ingredients", class_="block font-semibold mb-1"),
            html.template(
                ingredient_details(),
                **{"x-for": "(ingredient, index) in ingredients", ":key": "index"},
            ),
            add_ingredient(),
            instructions_input(),
            save_recipe(),
        ),
        hx_post="/new_recipe",
        hx_target="#form-result",
        hx_swap="innerHTML",
        class_="space-y-6",
        x_data="{ ingredients: [''] }",
    )


@PageRegistry.register(PAGE_NAME, "/new.html")
def new_recipe_page(_: t.Any) -> Component:
    """The HTML of the page for creating new recipes."""
    return page(
        html.main(
            html.h1("Create a New Recipe", class_="text-2xl font-bold text-green-700 mb-6"),
            new_recipe_form(),
            html.div(id="form-result", class_="mt-6"),
            class_="max-w-3xl mx-auto p-6 mt-8 bg-white shadow-md rounded-2xl",
        )
    )


@router.get(PageRegistry.route(PAGE_NAME))
@htmy_renderer.page(new_recipe_page)
async def new(_: CurrentUser) -> None:
    """The new page of the application."""


@router.post("/new_recipe", response_model=None)
@htmy_renderer.page(recipe_section, error_component_selector=new_recipe_error)
async def new_recipe(
    name: t.Annotated[str, Form()],
    instructions: t.Annotated[str, Form()],
    service: RecipeServiceDep,
    ingredients: t.Annotated[list[str], Form(default_factory=list)],
    user: CurrentUser,
) -> RecipeResponse:
    """Create a new recipe using a form."""
    recipe_data = CreateRecipeRequest.model_validate(
        {"name": name, "ingredients": clean_ingredients(ingredients), "instructions": instructions}
    )

    return await service.create(recipe_data, user.pk)
