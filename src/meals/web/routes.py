"""Routes for HTML pages and HTMX partials."""

import typing as t

from fastapi import APIRouter, Form
from fasthx.htmy import HTMY

from meals import schemas
from meals.database.repository import RecipeRepo  # noqa: TC001
from meals.web import views
from meals.web.components import new_recipe_error, recipe_div, recipe_names, recipes_div

router = APIRouter()


htmy = HTMY(
    # Register a request processor that adds a user-agent key to the htmy context.
    request_processors=[
        lambda request: {"user-agent": request.headers.get("user-agent")},
    ]
)


@router.get(views.pages[0][1])
@htmy.page(views.index_page)
async def index() -> None:
    """The index page of the application."""


@router.get(views.pages[1][1])
@htmy.page(views.new_recipe_page)
async def new() -> None:
    """The new page of the application."""


@router.get("/recipes")
@htmy.page(recipes_div)
async def get_recipes(repo: RecipeRepo) -> schemas.Recipes:
    """Get the recipes as HTML."""
    recipes = await repo.get_all()

    return schemas.Recipes.model_validate(recipes)


@router.get("/recipe_list")
@htmy.page(recipe_names)
async def recipe_list(repo: RecipeRepo) -> schemas.Recipes:
    """Get the recipes as HTML."""
    recipes = await repo.get_all()

    return schemas.Recipes.model_validate(recipes)


@router.post("/new_recipe", response_model=None)
@htmy.page(recipe_div, error_component_selector=new_recipe_error)
async def new_recipe(
    name: t.Annotated[str, Form()],
    instructions: t.Annotated[str, Form()],
    repo: RecipeRepo,
    ingredients: t.Annotated[list[str], Form()],
) -> schemas.RecipeResponse:
    """Create a new recipe using a form."""
    recipe_data = schemas.CreateRecipeRequest.model_validate(
        {"name": name, "ingredients": ingredients, "instructions": instructions}
    )
    recipe = await repo.create(recipe_data)

    return schemas.RecipeResponse.model_validate(recipe)
