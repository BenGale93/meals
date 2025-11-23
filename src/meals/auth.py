"""Module for user authentication."""

import typing as t

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from meals import schemas
from meals.database.repository import UserRepo  # noqa: TC001

security = HTTPBasic()


async def get_current_user(
    credentials: t.Annotated[HTTPBasicCredentials, Depends(security)], repo: UserRepo
) -> schemas.UserResponse | None:
    """Gets the current user by their user name.

    Note:
        Obviously this should be via a token.
    """
    user = await repo.get_by_name(credentials.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return schemas.UserResponse.model_validate(user)


CurrentUser = t.Annotated[schemas.UserResponse, Depends(get_current_user)]
