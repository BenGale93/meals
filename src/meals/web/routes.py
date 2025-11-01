"""Routes for HTML pages and HTMX partials."""

from fastapi import APIRouter
from fasthx.htmy import HTMY

from meals import schemas
from meals.database.repository import RecipeRepo  # noqa: TC001
from meals.web import views
from meals.web.components import recipe_names, recipes_div

router = APIRouter()


htmy = HTMY(
    # Register a request processor that adds a user-agent key to the htmy context.
    request_processors=[
        lambda request: {"user-agent": request.headers.get("user-agent")},
    ]
)


@router.get("/")
@htmy.page(views.index_page)
async def index() -> None:
    """The index page of the application."""


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
