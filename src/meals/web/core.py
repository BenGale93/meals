"""Core web components and pages."""

import json
import typing as t
from urllib.parse import urlencode

from fastapi import APIRouter
from fasthx.htmy import HTMY
from htmy import Component, ComponentType, SafeStr, html

from meals.schemas import LabelFilter

if t.TYPE_CHECKING:
    from pydantic_core import ErrorDetails

    from meals.schemas import IngredientResponse, LabelResponse, Labels, RecipeResponse


def format_new_recipe_error(error: ErrorDetails) -> str:
    """Formats the error message to be more useful to end user."""
    msg = error["msg"].removeprefix("Value error, ")

    match error["loc"]:
        case ("ingredients", number, *_) if isinstance(number, int):
            number = number + 1
            return f"Issue with ingredient {number}: {msg}"
        case ("labels", number, *_) if isinstance(number, int):
            number = number + 1
            return f"Issue with label {number}: {msg}"
        case ():
            return msg
        case _:
            return f"Issue with {error['loc'][0]}: {msg}"


def clean_ingredients(ingredients: list[str]) -> list[str]:
    """Drop blank ingredient inputs submitted by a form."""
    return [ingredient for ingredient in ingredients if ingredient]


def clean_labels(labels: list[str]) -> list[str]:
    """Drop blank label inputs submitted by a form."""
    return [label for label in labels if label.strip()]


def safe_label_filter(labels: list[str]) -> LabelFilter:
    """Parse filter labels, falling back to no filter for malformed deep links."""
    try:
        return LabelFilter(clean_labels(labels))
    except ValueError:
        return LabelFilter()


def label_chips(labels: list[LabelResponse]) -> ComponentType:
    """The label chips shown on a recipe card."""
    return html.div(
        *[
            html.span(
                str(label),
                class_="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 "
                "text-xs font-medium text-green-800",
            )
            for label in labels
        ],
        class_="mb-4 flex flex-wrap gap-2",
    )


def label_filter_chip(label: LabelResponse, selected: LabelFilter) -> ComponentType:
    """A checkbox for one label in a filter bar."""
    token = str(label)
    attributes: dict[str, t.Any] = {"type": "checkbox", "name": "labels", "value": token}
    if token in selected:
        attributes["checked"] = ""

    return html.label(
        html.input_(**attributes),
        html.span(label.sub_category),
        class_="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-green-200 "
        "bg-green-50 px-3 py-1 text-sm text-green-800",
    )


def filter_url(endpoint: str, tokens: t.Iterable[str]) -> str:
    """Build a filter URL for the given endpoint and label tokens."""
    query = urlencode([("labels", token) for token in tokens])
    return f"{endpoint}?{query}" if query else endpoint


def selected_filter_chip(token: str, remaining: tuple[str, ...], *, endpoint: str, target: str) -> ComponentType:
    """A removable chip for one active filter."""
    return html.span(
        html.span(token),
        html.button(
            "×",  # noqa: RUF001
            type="button",
            hx_get=filter_url(endpoint, remaining),
            hx_target=target,
            hx_swap="outerHTML",
            **{"aria-label": f"Remove filter {token}"},
            class_="ml-1 font-bold text-green-700 hover:text-red-600",
        ),
        class_="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs text-green-800",
    )


def active_filter_summary(selected: LabelFilter, *, endpoint: str, target: str) -> ComponentType:
    """The removable chips summarizing the active filters."""
    tokens = selected.tokens
    return html.div(
        html.span("Active filters:", class_="text-xs font-semibold uppercase tracking-wide text-gray-500"),
        *[
            selected_filter_chip(
                token,
                tuple(other for other in tokens if other != token),
                endpoint=endpoint,
                target=target,
            )
            for token in tokens
        ],
        class_="flex flex-wrap items-center gap-2",
    )


def label_filter_category(category: str, labels: list[LabelResponse], selected: LabelFilter) -> ComponentType:
    """One collapsible category of label checkboxes."""
    selected_count = len(selected.groups.get(category, frozenset()))
    summary_children: list[ComponentType] = [html.span(category, class_="font-semibold text-gray-700")]
    if selected_count:
        summary_children.append(
            html.span(
                f"{selected_count} selected",
                class_="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700",
            )
        )

    return html.details(
        html.summary(*summary_children, class_="flex cursor-pointer items-center justify-between gap-2"),
        html.div(
            *[label_filter_chip(label, selected) for label in labels],
            class_="mt-3 flex flex-wrap gap-2",
        ),
        class_="rounded-xl border border-green-100 bg-green-50/50 p-3",
        **({"open": ""} if selected_count else {}),
    )


def label_filter_controls(labels: Labels, selected: LabelFilter, *, endpoint: str, target: str) -> ComponentType:
    """The collapsible, grouped label checkboxes used by the recipe and summary filters."""
    parts: list[ComponentType] = []
    if selected:
        parts.append(active_filter_summary(selected, endpoint=endpoint, target=target))

    if not labels.root:
        parts.append(html.p("Add labels to your recipes to filter them", class_="text-sm italic text-gray-500"))
    else:
        grouped: dict[str, list[LabelResponse]] = {}
        for label in labels:
            grouped.setdefault(label.category, []).append(label)
        parts.append(
            html.div(
                *[label_filter_category(category, group, selected) for category, group in grouped.items()],
                class_="grid gap-3 md:grid-cols-2 lg:grid-cols-3",
            )
        )

    return html.div(*parts, class_="space-y-3")


def clear_filter_button(endpoint: str, target: str) -> ComponentType:
    """A button that resets the filter by requesting the unfiltered fragment."""
    return html.button(
        "Clear",
        type="button",
        hx_get=endpoint,
        hx_target=target,
        hx_swap="outerHTML",
        class_="rounded-lg bg-green-100 px-3 py-1 text-green-700 hover:bg-green-200 transition",
    )


def label_filter_form(labels: Labels, selected: LabelFilter, *, endpoint: str, target: str) -> ComponentType:
    """A change-triggered form containing the label filter controls."""
    return html.form(
        label_filter_controls(labels, selected, endpoint=endpoint, target=target),
        clear_filter_button(endpoint, target),
        hx_get=endpoint,
        hx_target=target,
        hx_swap="outerHTML",
        hx_trigger="change",
        class_="mb-6 rounded-2xl bg-white p-4 shadow-sm",
    )


LABEL_SCRIPT = html.script(
    SafeStr(r"""
function labelEditor(initial) {
    return {
        labels: initial,
        newLabel: '',
        addLabel() {
            const label = this.newLabel.trim().toLowerCase().replace(/\s+/g, '-');
            if (!label || this.labels.includes(label)) return;
            this.labels.push(label);
            this.newLabel = '';
        },
        removeLabel(label) {
            this.labels = this.labels.filter(item => item !== label);
        }
    }
}
""")
)


def label_editor(initial_labels: list[str], options: Labels) -> ComponentType:
    """The chip editor used by the new and edit recipe forms."""
    return html.div(
        html.label("Labels", class_="block font-semibold mb-1"),
        html.div(
            html.input_(
                **{
                    "type": "text",
                    "x-model": "newLabel",
                    "list": "label-options",
                    "@keydown.enter.prevent": "addLabel()",
                    "placeholder": "meat::beef",
                },
                class_="flex-1 rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-green-500 "
                "focus:outline-none",
            ),
            html.button(
                "Add label",
                **{"type": "button", "@click": "addLabel()"},
                class_="rounded-lg bg-green-100 px-3 py-2 text-green-700 hover:bg-green-200 transition",
            ),
            class_="flex items-center space-x-2",
        ),
        html.div(
            html.template(
                html.span(
                    html.span(**{"x-text": "label"}),
                    html.button(
                        "×",  # noqa: RUF001
                        **{"type": "button", "@click": "removeLabel(label)"},
                        class_="font-bold text-red-500 hover:text-red-700",
                    ),
                    html.input_(**{"type": "hidden", "name": "labels", ":value": "label"}),
                    class_="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 text-sm text-green-800",
                ),
                **{"x-for": "label in labels", ":key": "label"},
            ),
            class_="mt-3 flex flex-wrap gap-2",
        ),
        html.datalist(
            *[html.option(value=str(label)) for label in options],
            id="label-options",
        ),
        x_data=f"labelEditor({json.dumps(initial_labels)})",
        class_="space-y-2",
    )


router = APIRouter()


htmy_renderer = HTMY(
    # Register a request processor that adds a user-agent key to the htmy context.
    request_processors=[
        lambda request: {"user-agent": request.headers.get("user-agent")},
    ]
)

P = t.ParamSpec("P")
PageFunction = t.Callable[P, Component]


class Page(t.NamedTuple):
    """A page linked from the navigation bar."""

    name: str
    path: str


RECIPES_PAGE = Page("Recipes", "/")
NEW_RECIPE_PAGE = Page("New Recipe", "/new.html")
PLANNER_PAGE = Page("Planner", "/plan.html")
TIMINGS_PAGE = Page("Timings", "/timings.html")

#: The single source of truth for the site pages, in navigation order. Declaring
#: the order here (rather than relying on the order in which modules are
#: imported) keeps the navigation bar stable.
PAGES: tuple[Page, ...] = (RECIPES_PAGE, NEW_RECIPE_PAGE, PLANNER_PAGE, TIMINGS_PAGE)


class PageRegistry:
    """Tracks the page modules imported by :mod:`meals.web`.

    Registration is an import-time side effect: a page module is wired up only
    if it is imported from ``meals/web/__init__.py`` and decorated with
    ``@PageRegistry.register(PAGE)``. ``validate()`` (called by
    :func:`meals.app.create_app`) makes a missing import fail loudly at start-up
    instead of silently dropping a page.
    """

    _registered: t.ClassVar[set[Page]] = set()

    @classmethod
    def register[**P](cls, page: Page) -> t.Callable[[PageFunction[P]], PageFunction[P]]:
        """Register the decorated page function for ``page``."""
        if page not in PAGES:
            msg = f"Page {page.name!r} ({page.path!r}) is not declared in PAGES"
            raise ValueError(msg)

        def decorator(fn: PageFunction[P]) -> PageFunction[P]:
            cls._registered.add(page)
            return fn

        return decorator

    @classmethod
    def pages(cls) -> list[tuple[str, str]]:
        """Return the declared pages in navigation order."""
        return [(page.name, page.path) for page in PAGES]

    @classmethod
    def validate(cls) -> None:
        """Raise if a page declared in :data:`PAGES` was never imported."""
        missing = [page.name for page in PAGES if page not in cls._registered]
        if missing:
            msg = (
                f"Page(s) {', '.join(missing)} declared in PAGES were not registered; "
                "import their modules from meals/web/__init__.py"
            )
            raise RuntimeError(msg)


BURGER_SVG = SafeStr("""
<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-green-700" fill="none"
           viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path x-show="!open" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    <path x-show="open" stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
</svg>
""")


def nav_bar(pages: t.Sequence[tuple[str, str]]) -> ComponentType:
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
                html.Meta.charset(),
                html.Meta.viewport(),
                # TailwindCSS (Play CDN; the path pins the exact version)
                html.script(src="https://cdn.tailwindcss.com/3.4.17"),
                # HTMX
                html.script(src="https://unpkg.com/htmx.org@2.0.2/dist/htmx.min.js"),
                # Alpine
                html.script(src="https://unpkg.com/alpinejs@3.17.5/dist/cdn.min.js", defer=""),
                # Shared Alpine components available to HTMX-loaded fragments.
                LABEL_SCRIPT,
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


def ingredient_div(ingredient: IngredientResponse) -> ComponentType:
    """A Div representing an ingredient."""
    return html.div(f"{ingredient.name} {ingredient.quantity} {ingredient.unit}")


def _common_recipe(recipe: RecipeResponse) -> tuple[list[ComponentType], dict[str, t.Any]]:
    core_components: list[ComponentType] = [html.h2(recipe.name, class_="text-2xl font-bold text-green-700 mb-3")]
    if recipe.labels:
        core_components.append(label_chips(recipe.labels))
    core_components.extend(
        [
            html.ul(*[html.li(ingredient_div(i)) for i in recipe.ingredients], class_="list-disc ml-5 mb-4"),
            html.p(recipe.instructions, style="white-space:pre-line;", class_="pb-3"),
        ]
    )
    properties: dict[str, t.Any] = {
        "class_": "bg-white rounded-2xl shadow-md p-6",
        "id": recipe.anchor,
    }
    return core_components, properties


def recipe_section(recipe: RecipeResponse) -> ComponentType:
    """A Section representing a recipe."""
    core_components, properties = _common_recipe(recipe)
    return html.section(*core_components, **properties)


def editable_recipe_section(recipe: RecipeResponse) -> ComponentType:
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
