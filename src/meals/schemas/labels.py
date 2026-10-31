"""Request, response and filter models for recipe labels.

A label is a ``category::sub_category`` pair, for example ``meat::beef``. The two parts
are normalised independently: surrounding whitespace is trimmed, everything is lowercased,
and internal whitespace runs become single hyphens. Parts may then contain only lowercase
letters, digits, and single hyphens between groups.
"""

import re
import typing as t

from pydantic import AliasPath, BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from meals.constants import LABEL_LENGTH

if t.TYPE_CHECKING:
    from collections.abc import Iterable

#: The separator between a category and its sub-category in a canonical label.
LABEL_SEPARATOR = "::"
LABEL_PART_COUNT = 2
LABEL_PART_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LABEL_PART_ERROR = (
    f"Label parts must be 1-{LABEL_LENGTH} characters long and contain only lowercase "
    "letters, digits, and single hyphens between groups."
)
LABEL_FORM_ERROR = "Expected a label in the form 'category::sub_category'."


def normalise_label_part(value: str) -> str:
    """Normalise and validate one part of a label.

    Args:
        value: The raw category or sub-category name.

    Returns:
        The normalised name.

    Raises:
        ValueError: If the normalised value is empty, too long, or has invalid characters.
    """
    normalised = re.sub(r"\s+", "-", value.strip().lower())
    if not normalised or len(normalised) > LABEL_LENGTH or LABEL_PART_PATTERN.fullmatch(normalised) is None:
        raise ValueError(LABEL_PART_ERROR)
    return normalised


def parse_label(token: str) -> tuple[str, str]:
    """Split a canonical label token into normalised category and sub-category parts.

    Args:
        token: A label such as ``meat::beef``.

    Returns:
        The normalised ``(category, sub_category)`` pair.

    Raises:
        ValueError: If the token is not a single ``category::sub_category`` pair or either
            part is invalid.
    """
    parts = token.split(LABEL_SEPARATOR)
    if len(parts) != LABEL_PART_COUNT:
        msg = f"Invalid label {token!r}: {LABEL_FORM_ERROR}"
        raise ValueError(msg)

    try:
        return normalise_label_part(parts[0]), normalise_label_part(parts[1])
    except ValueError as error:
        msg = f"Invalid label {token!r}: {error}"
        raise ValueError(msg) from None


class CreateLabel(BaseModel):
    """A label supplied when creating or updating a recipe."""

    category: str
    sub_category: str

    @field_validator("category", "sub_category", mode="before")
    @classmethod
    def normalise(cls, value: t.Any) -> t.Any:
        """Normalise the label part before the string field validates it."""
        if not isinstance(value, str):
            return value
        return normalise_label_part(value)


def check_unique_labels(labels: Iterable[CreateLabel]) -> None:
    """Raise if the same normalised label is listed more than once.

    Args:
        labels: The labels to check.

    Raises:
        ValueError: If a label occurs more than once.
    """
    keys = [(label.category, label.sub_category) for label in labels]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        formatted = ", ".join(f"{category}{LABEL_SEPARATOR}{sub_category}" for category, sub_category in duplicates)
        msg = f"Duplicate labels are not allowed: {formatted}."
        raise ValueError(msg)


class LabelResponse(BaseModel):
    """A label as returned by the API, validated directly from a stored recipe label."""

    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    category: str = Field(validation_alias=AliasPath("sub_category", "category", "name"))
    sub_category: str = Field(validation_alias=AliasPath("sub_category", "name"))

    @t.override
    def __str__(self) -> str:
        return f"{self.category}{LABEL_SEPARATOR}{self.sub_category}"


class Labels(RootModel[list[LabelResponse]]):
    """A sorted list of labels."""

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sort_labels(self) -> Labels:
        """Sort the labels by category, then sub-category."""
        self.root.sort(key=lambda label: (label.category, label.sub_category))
        return self

    @t.override
    def __iter__(self) -> t.Iterator[LabelResponse]:  # pyrefly: ignore[bad-override]
        return iter(self.root)


class LabelFilter:
    """A parsed label filter: OR within a category, AND across categories.

    Args:
        labels: Canonical ``category::sub_category`` tokens. Empty or absent labels mean
            no filtering.
    """

    __slots__ = ("_groups",)

    def __init__(self, labels: Iterable[str] = ()) -> None:
        """Parse, normalise, deduplicate and group the given label tokens."""
        grouped: dict[str, set[str]] = {}
        for token in labels:
            category, sub_category = parse_label(token)
            grouped.setdefault(category, set()).add(sub_category)
        self._groups = {category: frozenset(sub_categories) for category, sub_categories in sorted(grouped.items())}

    @property
    def groups(self) -> dict[str, frozenset[str]]:
        """Return the requested sub-categories grouped by category."""
        return dict(self._groups)

    @property
    def tokens(self) -> tuple[str, ...]:
        """Return the canonical, deduplicated tokens in a deterministic order."""
        return tuple(
            f"{category}{LABEL_SEPARATOR}{sub_category}"
            for category, sub_categories in self._groups.items()
            for sub_category in sorted(sub_categories)
        )

    @property
    def category_count(self) -> int:
        """Return the number of distinct categories that must each match."""
        return len(self._groups)

    def __bool__(self) -> bool:
        """Return whether the filter selects on any labels."""
        return bool(self._groups)

    def __contains__(self, token: object) -> bool:
        """Return whether a canonical token is part of the filter."""
        if not isinstance(token, str):
            return False
        try:
            category, sub_category = parse_label(token)
        except ValueError:
            return False
        return sub_category in self._groups.get(category, frozenset())

    def __eq__(self, other: object) -> bool:
        """Compare filters by their grouped labels."""
        if not isinstance(other, LabelFilter):
            return NotImplemented
        return self._groups == other._groups

    def __hash__(self) -> int:
        """Hash the filter by its canonical tokens."""
        return hash(self.tokens)

    def __repr__(self) -> str:
        """Return a debug representation."""
        return f"LabelFilter({list(self.tokens)!r})"
