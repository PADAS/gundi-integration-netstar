import pydantic
from .core import PullActionConfiguration, AuthActionConfiguration, ExecutableActionMixin


class NetstarAuthConfig(AuthActionConfiguration, ExecutableActionMixin):
    username: str = pydantic.Field(..., title="Username", description="Netstar portal username")
    password: pydantic.SecretStr = pydantic.Field(..., title="Password", description="Netstar portal password")

    @pydantic.validator("username")
    def validate_username(cls, v):
        return v.strip()


class NetstarPullObservationsConfig(PullActionConfiguration):
    username: str = pydantic.Field(..., title="Username", description="Netstar portal username")
    password: pydantic.SecretStr = pydantic.Field(..., title="Password", description="Netstar portal password")
    reset: bool = pydantic.Field(False, title="Reset", description="If true, returns all vehicle locations even if position hasn't changed since the last call.")

    @pydantic.validator("username")
    def validate_username(cls, v):
        return v.strip()
