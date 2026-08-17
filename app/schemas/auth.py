from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ToolInfo(BaseModel):
    tool_key: str
    role: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_admin: bool = False
    must_change_password: bool = False
    usuario_integre: int | None = None
    tools: list[ToolInfo] = []

    model_config = {"from_attributes": True}
