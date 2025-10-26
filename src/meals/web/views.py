"""The page views of the website."""

import typing as t

from htmy import Component, html


def index_page(_: t.Any) -> Component:
    """The HTML of the index page of the app."""
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
            ),
            html.div(hx_get="/recipes", hx_trigger="load", hx_swap="outerHTML"),
        ),
    )
