import pytest
from pydantic import ValidationError

from meals.schemas import CreateIngredientRequest, CreateRecipeRequest


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
