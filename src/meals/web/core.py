"""Core web components and pages."""

import typing as t

from fastapi import APIRouter
from fasthx.htmy import HTMY
from htmy import Component, ComponentType, SafeStr, Tag, html

if t.TYPE_CHECKING:
    from meals.schemas import IngredientResponse, RecipeResponse

router = APIRouter()


htmy_renderer = HTMY(
    # Register a request processor that adds a user-agent key to the htmy context.
    request_processors=[
        lambda request: {"user-agent": request.headers.get("user-agent")},
    ]
)

P = t.ParamSpec("P")
PageFunction = t.Callable[P, Component]


class PageRegistry:
    _page_registry: t.ClassVar[dict[str, str]] = {}

    @classmethod
    def register[**P](cls, name: str, path: str) -> t.Callable[[PageFunction[P]], PageFunction[P]]:
        """Register the page with a name and path."""

        def decorator(fn: PageFunction[P]) -> PageFunction[P]:
            cls._page_registry[name] = path
            return fn

        return decorator

    @classmethod
    def pages(cls) -> list[tuple[str, str]]:
        """Return the pages."""
        return [(k, v) for k, v in cls._page_registry.items()]

    @classmethod
    def route(cls, name: str) -> str:
        """Get the route associated with the name."""
        return cls._page_registry[name]


BURGER_SVG = SafeStr("""
<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-green-700" fill="none"
           viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path x-show="!open" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    <path x-show="open" stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
</svg>
""")


def nav_bar(pages: t.Sequence[tuple[str, str]]) -> html.div:
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
    return html.div(
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
    )


def page(content: ComponentType) -> Component:
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
                    nav_bar(PageRegistry.pages()),
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


def ingredient_div(ingredient: IngredientResponse) -> html.div:
    """A Div representing an ingredient."""
    return html.div(f"{ingredient.name} {ingredient.quantity} {ingredient.unit}")


def _common_recipe(recipe: RecipeResponse) -> tuple[list[Tag], dict[str, t.Any]]:
    core_components = [
        html.h2(recipe.name, class_="text-2xl font-bold text-green-700 mb-3"),
        html.ul(*[html.li(ingredient_div(i)) for i in recipe.ingredients], class_="list-disc ml-5 mb-4"),
        html.p(recipe.instructions, style="white-space:pre-line;", class_="pb-3"),
    ]
    properties = {
        "class_": "bg-white rounded-2xl shadow-md p-6",
        "id": recipe.anchor,
    }
    return core_components, properties


def recipe_section(recipe: RecipeResponse) -> html.section:
    """A Section representing a recipe."""
    core_components, properties = _common_recipe(recipe)
    return html.section(*core_components, **properties)


def editable_recipe_section(recipe: RecipeResponse) -> html.section:
    """A Section representing a editable recipe."""
    core_components, properties = _common_recipe(recipe)
    core_components.append(
        html.button(
            "Edit",
            hx_get=f"/recipe/{recipe.pk}/edit",
            class_="px-4 py-1 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition",
        ),
    )
    properties = properties | {"hx_target": "this", "hx_swap": "outerHTML"}

    return html.section(*core_components, **properties)
