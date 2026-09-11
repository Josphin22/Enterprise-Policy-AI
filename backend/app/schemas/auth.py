import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="Corporate email address")
    username: str = Field(..., min_length=2, max_length=100, description="Username or full name")
    password: str = Field(..., min_length=6, max_length=128, description="Account password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address format.")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Corporate email address")
    password: str = Field(..., description="Account password")


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="New role: ADMIN, MANAGER, or USER")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("ADMIN", "MANAGER", "USER"):
            raise ValueError("Role must be one of: 'ADMIN', 'MANAGER', or 'USER'.")
        return v


class UserStatusUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="Active status of the user account")
