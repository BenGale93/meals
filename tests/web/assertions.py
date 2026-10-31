"""Assertion helpers for rendered HTML pages."""

import html
import re
from typing import TYPE_CHECKING

from starlette import status

if TYPE_CHECKING:
    from httpx import Response


def assert_page_shell(response: Response) -> None:
    """Assert the shared page frame and navigation."""
    assert response.status_code == status.HTTP_200_OK
    assert "<!DOCTYPE html>" in response.text
    assert "<title" in response.text
    assert "Meal Manager" in response.text

    for path in ["/", "/new.html", "/plan.html", "/timings.html"]:
        assert f'href="{path}"' in response.text

    assert 'id="topButton"' in response.text


def assert_meal_options(response: Response, expected: list[str]) -> None:
    """Assert the meal datalist contains exactly the expected options."""
    assert response.status_code == status.HTTP_200_OK
    assert "<datalist" in response.text
    assert response.text.count("<option ") == len(expected)

    for meal in expected:
        assert f'<option value="{meal}"></option>' in response.text


def label_checkbox(text: str, value: str) -> str:
    """Return the rendered checkbox with the given label value."""
    for match in re.finditer(r"<input[^>]*>", text):
        tag = match.group(0)
        if 'name="labels"' in tag and f'value="{value}"' in tag:
            return tag
    msg = f"No label checkbox for {value!r}"
    raise AssertionError(msg)


def assert_summary_rows(response: Response, expected: list[tuple[str, int, str]]) -> None:
    """Assert the parsed rows of the recipe summary table."""
    assert response.status_code == status.HTTP_200_OK
    assert 'id="recipe-summary"' in response.text
    assert "Recipe Summary" in response.text

    body = re.search(r"<tbody[^>]*>(?P<rows>.*?)</tbody>", response.text, re.DOTALL)
    assert body is not None

    rows = re.findall(r"<tr[^>]*>(?P<cells>.*?)</tr>", body["rows"], re.DOTALL)
    parsed: list[tuple[str, int, str]] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(?P<value>.*?)</td>", row, re.DOTALL)
        assert len(cells) == 3

        name, count, last_eaten = (html.unescape(re.sub("<[^>]+>", "", cell)).strip() for cell in cells)
        parsed.append((name, int(count), last_eaten))

    assert parsed == expected
