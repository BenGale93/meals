"""HTML components for website elements."""

import typing as t

from htmy import Component, Context, component, html

if t.TYPE_CHECKING:
    from meals.schemas import IngredientResponse, RecipeResponse, Recipes


@component
def ingredient_div(ingredient: IngredientResponse, _context: Context) -> Component:
    """A Div representing an ingredient."""
    return html.div(f"{ingredient.name} {ingredient.quantity} {ingredient.unit}")


@component
def recipe_div(recipe: RecipeResponse, _context: Context) -> Component:
    """A Div representing a recipe."""
    return html.div(
        html.h1(recipe.name, class_="font-bold text-[20px]"),
        html.ul(*[html.li(ingredient_div(i)) for i in recipe.ingredients], class_="m-3"),
        html.p(recipe.instructions, style="white-space:pre-line;"),
        class_="m-5",
    )


@component
def recipes_div(recipes: Recipes, _context: Context) -> Component:
    """A Div representing all recipes."""
    return [recipe_div(recipe) for recipe in recipes]
