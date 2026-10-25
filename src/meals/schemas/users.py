"""Request and response models for users and authentication."""

import base64

from pydantic import BaseModel, ConfigDict


class CreateUserRequest(BaseModel):
    user_name: str

    def auth_headers(self) -> dict[str, str]:
        """Returns auth headers for the user."""
        return {"Authorization": "Basic " + base64.b64encode(f"{self.user_name}:test".encode()).decode()}


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    user_name: str
