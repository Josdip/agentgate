"""Persistent agent inventory metadata; permissions are derived from policy."""

from pydantic import Field, model_validator

from .policy import StrictModel


class ModelConnection(StrictModel):
    provider: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._/-]*$")
    model: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._:/-]*$")


class ProfileUpdate(StrictModel):
    revision: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=500)
    model_connections: list[ModelConnection] = Field(max_length=10)

    @model_validator(mode="after")
    def unique_connections(self):
        keys = [
            (item.provider.casefold(), item.model.casefold()) for item in self.model_connections
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate model connections")
        if not self.display_name.strip():
            raise ValueError("Display name cannot be blank")
        return self
