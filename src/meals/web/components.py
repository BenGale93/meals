"""HTML components for website elements."""

import typing as t

from htmy import Component, Context, SafeStr, component, html

if t.TYPE_CHECKING:
    from meals.schemas import IngredientResponse, RecipeResponse, Recipes


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
