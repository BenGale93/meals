"""The page views of the website."""

import typing as t

from htmy import Component, ComponentType, Context, component, html

from meals.web.components import nav_bar

pages = [("Recipe", "")]


@component
def page(content: ComponentType, _context: Context) -> Component:
    """Core page layout."""
    return (
        html.DOCTYPE.html,
        html.html(
            html.head(
                # Some metadata
                html.title("FastHX + HTMY example"),
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
