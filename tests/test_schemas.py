import pytest
from pydantic import ValidationError

from meals.schemas import CreateIngredientRequest, CreateRecipeRequest


def test_create_ingredient_request_from_string():
    ingredient = CreateIngredientRequest.model_validate("Garlic 1 clove")

    assert ingredient.name == "Garlic"
    assert ingredient.quantity == 1
    assert ingredient.unit == "clove"


def test_ingredient_incorrect_structure():
    with pytest.raises(ValidationError, match=r"Expected ingredient to be in form: 'name quantity unit'"):
        CreateRecipeRequest.model_validate({"name": "Test", "ingredients": ["Test"], "instructions": "Test"})
