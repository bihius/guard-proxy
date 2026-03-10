"""Schematy Pydantic — walidacja requestów i serializacja odpowiedzi API."""

from app.schemas.auth import LoginRequest, Token, TokenData
from app.schemas.policy import PolicyCreate, PolicyDetail, PolicyResponse, PolicyUpdate
from app.schemas.rule_override import RuleOverrideCreate, RuleOverrideResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.vhost import VHostCreate, VHostDetail, VHostResponse, VHostUpdate

__all__ = [
    # Auth
    "LoginRequest",
    "Token",
    "TokenData",
    # Users
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Policies
    "PolicyCreate",
    "PolicyUpdate",
    "PolicyResponse",
    "PolicyDetail",
    # VHosts
    "VHostCreate",
    "VHostUpdate",
    "VHostResponse",
    "VHostDetail",
    # Rule Overrides
    "RuleOverrideCreate",
    "RuleOverrideResponse",
]
