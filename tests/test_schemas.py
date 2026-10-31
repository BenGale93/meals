import pytest
from pydantic import ValidationError

from meals.schemas import (
    LABEL_LENGTH,
    CreateIngredientRequest,
    CreateLabel,
    CreateRecipeRequest,
    CreateRecipes,
    LabelFilter,
    LabelResponse,
    Labels,
    UpdateRecipeRequest,
    check_unique_labels,
    normalise_label_part,
    parse_label,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Garlic 1 clove", ("Garlic", 1.0, "clove")),
        ("Beef 1.5 kg", ("Beef", 1.5, "kg")),
        ("Sugar 1/2 cup", ("Sugar", 0.5, "cup")),
        ("500g beef", ("beef", 500.0, "g")),
        ("2 tins tomatoes", ("tomatoes", 2.0, "tins")),
        ("1/2 cup sugar", ("sugar", 0.5, "cup")),
        ("1.5 kg beef", ("beef", 1.5, "kg")),
    ],
)
def test_create_ingredient_request_from_string(raw: str, expected: tuple[str, float, str]):
    ingredient = CreateIngredientRequest.model_validate(raw)

    assert (ingredient.name, ingredient.quantity, ingredient.unit) == expected


@pytest.mark.parametrize("raw", ["Salt", "Flour 2", "2 tins", "1/2 cup", "Flour x cups"])
def test_ingredient_rejects_incomplete_forms(raw: str):
    with pytest.raises(ValidationError, match=r"Examples: 'Flour 2 cups', '500g beef', '1/2 cup sugar'"):
        CreateIngredientRequest.model_validate(raw)


def test_ingredient_incorrect_structure():
    with pytest.raises(ValidationError, match=r"Expected ingredient to be in form: 'name quantity unit'"):
        CreateRecipeRequest.model_validate({"name": "Test", "ingredients": ["Test"], "instructions": "Test"})


def test_create_recipes_is_iterable():
    recipes = CreateRecipes.model_validate([{"name": "Test", "ingredients": [], "instructions": ""}])

    assert [recipe.name for recipe in recipes] == ["Test"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Meat ", "meat"),
        ("Toddler Approved", "toddler-approved"),
        ("already-hyphenated", "already-hyphenated"),
        ("UPPER", "upper"),
        ("multi   space", "multi-space"),
        ("a" * LABEL_LENGTH, "a" * LABEL_LENGTH),
    ],
)
def test_normalise_label_part(raw: str, expected: str):
    assert normalise_label_part(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "a" * (LABEL_LENGTH + 1),
        "bad_name",
        "bad!name",
        "-leading",
        "trailing-",
        "double--hyphen",
    ],
)
def test_normalise_label_part_rejects_invalid_values(raw: str):
    with pytest.raises(ValueError, match="Label parts must be"):
        normalise_label_part(raw)


def test_create_label_normalises_both_parts():
    label = CreateLabel(category=" Meat ", sub_category=" Ground   Beef ")

    assert (label.category, label.sub_category) == ("meat", "ground-beef")


def test_create_label_accepts_a_canonical_token():
    label = CreateLabel.model_validate(" Meat :: Ground Beef ")

    assert (label.category, label.sub_category) == ("meat", "ground-beef")


def test_create_label_rejects_a_malformed_token():
    with pytest.raises(ValidationError, match="Invalid label 'not-a-label'"):
        CreateLabel.model_validate("not-a-label")


def test_create_label_rejects_non_string_parts():
    with pytest.raises(ValidationError):
        CreateLabel.model_validate({"category": 1, "sub_category": "beef"})


def test_parse_label_normalises_both_parts():
    assert parse_label(" Meat :: Ground Beef ") == ("meat", "ground-beef")


@pytest.mark.parametrize(
    "token",
    ["meat", "meat:beef", "meat::beef::extra", "::beef", "meat::", "bad_name::beef"],
)
def test_parse_label_rejects_malformed_tokens(token: str):
    with pytest.raises(ValueError, match="Invalid label"):
        parse_label(token)


def test_create_recipe_accepts_and_normalises_labels():
    recipe = CreateRecipeRequest.model_validate(
        {
            "name": "Test",
            "ingredients": [],
            "instructions": "",
            "labels": [{"category": " Meat ", "sub_category": " Ground Beef "}],
        }
    )

    assert [(label.category, label.sub_category) for label in recipe.labels] == [("meat", "ground-beef")]


@pytest.mark.parametrize("model", [CreateRecipeRequest, UpdateRecipeRequest])
def test_recipe_requests_reject_duplicate_labels_after_normalisation(
    model: type[CreateRecipeRequest | UpdateRecipeRequest],
):
    with pytest.raises(ValidationError, match="Duplicate labels are not allowed: meat::beef"):
        model.model_validate(
            {
                "pk": 1,
                "name": "Test",
                "ingredients": [],
                "instructions": "",
                "labels": [
                    {"category": "Meat", "sub_category": "Beef"},
                    {"category": "meat", "sub_category": "beef"},
                ],
            }
        )


def test_check_unique_labels_accepts_unique_labels():
    labels = [
        CreateLabel(category="meat", sub_category="beef"),
        CreateLabel(category="meat", sub_category="chicken"),
    ]

    check_unique_labels(labels)


def test_label_response_uses_canonical_string():
    label = LabelResponse(category="meat", sub_category="beef")

    assert str(label) == "meat::beef"


def test_labels_are_sorted_and_iterable():
    labels = Labels.model_validate(
        [
            {"category": "time", "sub_category": "quick"},
            {"category": "meat", "sub_category": "chicken"},
            {"category": "meat", "sub_category": "beef"},
        ]
    )

    assert [str(label) for label in labels] == ["meat::beef", "meat::chicken", "time::quick"]


def test_label_filter_parses_normalises_deduplicates_and_groups():
    label_filter = LabelFilter([" Meat :: Beef ", "meat::beef", "meat::chicken", "time::quick", "Time::QUICK"])

    assert label_filter.groups == {
        "meat": frozenset({"beef", "chicken"}),
        "time": frozenset({"quick"}),
    }
    assert label_filter.tokens == ("meat::beef", "meat::chicken", "time::quick")
    assert label_filter.category_count == 2
    assert label_filter
    assert "Meat::Beef" in label_filter
    assert "meat::lamb" not in label_filter
    assert "not-a-label" not in label_filter
    assert 1 not in label_filter


def test_empty_label_filter_selects_nothing():
    label_filter = LabelFilter()

    assert not label_filter
    assert label_filter.groups == {}
    assert label_filter.tokens == ()
    assert label_filter.category_count == 0


def test_label_filter_equality_hash_and_repr():
    first = LabelFilter(["meat::beef"])
    second = LabelFilter(["Meat::Beef"])

    assert first == second
    assert first != LabelFilter(["meat::chicken"])
    assert first != "meat::beef"
    assert hash(first) == hash(second)
    assert repr(first) == "LabelFilter(['meat::beef'])"


def test_label_filter_rejects_malformed_tokens():
    with pytest.raises(ValueError, match="Invalid label 'not-a-label'"):
        LabelFilter(["not-a-label"])
