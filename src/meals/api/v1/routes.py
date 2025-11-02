"""The routes for the data API."""

from fastapi import APIRouter, HTTPException, status

from meals import schemas
from meals.database.repository import RecipeRepo  # noqa: TC001
from meals.exceptions import RecipeAlreadyExistsError

router = APIRouter(prefix="/v1", tags=["v1"])


@router.post("/recipes", status_code=status.HTTP_201_CREATED)
async def create_recipe(data: schemas.CreateRecipeRequest, repo: RecipeRepo) -> schemas.RecipeResponse:
    """Creates the recipe in the given database."""
    try:
        new_recipe = await repo.create(data)
    except RecipeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None

    return schemas.RecipeResponse.model_validate(new_recipe)


@router.get("/recipes", status_code=status.HTTP_200_OK)
async def get_recipes(repo: RecipeRepo) -> schemas.Recipes:
    """Get all the recipe in the database."""
    recipes = await repo.get_all()

    return schemas.Recipes.model_validate(recipes)


@router.get("/recipes/{pk}", status_code=status.HTTP_200_OK)
async def get_recipe_by_key(pk: int, repo: RecipeRepo) -> schemas.RecipeResponse:
    """Get the recipe by the primary key of that recipe."""
    recipe = await repo.get(pk)

    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe does not exist.")

    return schemas.RecipeResponse.model_validate(recipe)


@router.get("/recipes/", status_code=status.HTTP_200_OK)
async def get_recipe(name: str, repo: RecipeRepo) -> schemas.RecipeResponse:
    """Get a recipe by name."""
    recipe = await repo.get_by_name(name)

    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe named '{name}' does not exist.")

    return schemas.RecipeResponse.model_validate(recipe)
