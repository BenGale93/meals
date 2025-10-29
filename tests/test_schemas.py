from meals.schemas import CreateIngredientRequest


def test_create_ingredient_request_from_string():
    ingredient = CreateIngredientRequest.model_validate("Garlic 1 clove")

    assert ingredient.name == "Garlic"
    assert ingredient.quantity == 1
    assert ingredient.unit == "clove"
