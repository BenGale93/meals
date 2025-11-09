"""The page views of the website."""

import typing as t

from htmy import Component, ComponentType, Context, component, html

from meals.web.components import nav_bar

pages = [("Recipes", "/"), ("New Recipe", "/new.html"), ("Timings", "/timings.html")]


@component
def page(content: ComponentType, _context: Context) -> Component:
    """Core page layout."""
    return (
        html.DOCTYPE.html,
        html.html(
            html.head(
                # Some metadata
                html.title("Meal Manager"),
                html.meta.charset(),
                html.meta.viewport(),
                # TailwindCSS
                html.script(src="https://cdn.tailwindcss.com"),
                # HTMX
                html.script(src="https://unpkg.com/htmx.org@2.0.2"),
                # Apline
                html.script(src="https://unpkg.com/alpinejs@3.x.x", defer=""),
            ),
            html.body(
                html.header(
                    nav_bar(pages),
                    class_="bg-white shadow-md sticky top-0 z-10",
                    **{"x-data": "{ open: false }"},
                ),
                content,
                html.button(
                    "↑",
                    id="topButton",
                    class_="fixed bottom-6 right-6 bg-green-600 text-white p-3 "
                    "rounded-full shadow-lg hover:bg-green-700 transition z-50",
                    **{
                        "x-show": "showTop",
                        "x-transition": "",
                        "@click": "window.scrollTo({ top: 0, behavior: 'smooth' })",
                    },
                ),
                class_="bg-gray-50 text-gray-800 font-sans",
                **{
                    "x-data": "{ showTop: false }",
                    "@scroll.window": "showTop = (window.scrollY > 300)",
                },
            ),
        ),
    )


def index_page(_: t.Any) -> Component:
    """The HTML of the index page of the app."""
    return page(
        html.div(
            html.div(hx_get="/recipe_list", hx_trigger="load", hx_swap="outerHTML"),
            html.div(hx_get="/recipes", hx_trigger="load", hx_swap="outerHTML"),
        )
    )


def new_recipe_page(_: t.Any) -> Component:
    """The HTML of the page for creating new recipes."""
    return page(
        html.main(
            html.h1("Create a New Recipe", class_="text-2xl font-bold text-green-700 mb-6"),
            html.form(
                html.div(
                    html.label("Recipe Name", class_="block font-semibold mb-1", **{"for": "name"}),
                    html.input_(
                        id="name",
                        name="name",
                        type="text",
                        required="",
                        class_="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 "
                        "focus:ring-green-500 focus:outline-none",
                    ),
                ),
                html.div(
                    html.label("Ingredients", class_="block font-semibold mb-1"),
                    html.template(
                        html.div(
                            html.input_(
                                **{
                                    "type": "text",
                                    "name": "ingredients",
                                    "x-model": "ingredients[index]",
                                    "placeholder": "Flour 2 cups",
                                },
                                class_="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 "
                                "focus:ring-green-500 focus:outline-none",
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
                        ),
                        **{"x-for": "(ingredient, index) in ingredients", ":key": "index"},
                    ),
                    html.button(
                        "+ Add Ingredient",
                        **{"type": "button", "@click": "ingredients.push('')"},
                        class_="mt-2 px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition",
                    ),
                    html.div(
                        html.label("Instructions", class_="block font-semibold mb-1", **{"for": "instructions"}),
                        html.textarea(
                            id="instructions",
                            name="instructions",
                            rows="6",
                            required="",
                            placeholder="Describe the preparation steps here...",
                            class_="w-full p-3 border border-gray-300 rounded-lg"
                            " focus:ring-2 focus:ring-green-500 focus:outline-none",
                        ),
                    ),
                    html.div(
                        html.button(
                            "Save Recipe",
                            type="submit",
                            class_="px-6 py-3 bg-green-600 text-white rounded-lg"
                            " font-medium hover:bg-green-700 transition",
                        ),
                        class_="text-right",
                    ),
                ),
                hx_post="/new_recipe",
                hx_target="#form-result",
                hx_swap="innerHTML",
                class_="space-y-6",
                x_data="{ ingredients: [''] }",
            ),
            html.div(id="form-result", class_="mt-6"),
            class_="max-w-3xl mx-auto p-6 mt-8 bg-white shadow-md rounded-2xl",
        )
    )


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
