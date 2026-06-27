"""Pydantic schemas used for request validation and API serialization."""

from app.schemas.auth import AccessTokenResponse, LoginRequest, TokenData
from app.schemas.custom_rule import (
    CustomRuleCreate,
    CustomRuleResponse,
    CustomRuleUpdate,
)
from app.schemas.log import LogIngestRequest, LogListResponse, LogResponse
from app.schemas.policy import PolicyCreate, PolicyDetail, PolicyResponse, PolicyUpdate
from app.schemas.policy_binding import PolicyBindingCreate, PolicyBindingResponse
from app.schemas.rule_exclusion import (
    RuleExclusionCreate,
    RuleExclusionResponse,
    RuleExclusionUpdate,
)
from app.schemas.rule_override import (
    RuleOverrideCreate,
    RuleOverrideResponse,
    RuleOverrideUpdate,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.vhost import VHostCreate, VHostDetail, VHostResponse, VHostUpdate

__all__ = [
    # Auth
    "LoginRequest",
    "AccessTokenResponse",
    "TokenData",
    # Logs
    "LogIngestRequest",
    "LogResponse",
    "LogListResponse",
    # Users
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Policies
    "PolicyCreate",
    "PolicyUpdate",
    "PolicyResponse",
    "PolicyDetail",
    "PolicyBindingCreate",
    "PolicyBindingResponse",
    # VHosts
    "VHostCreate",
    "VHostUpdate",
    "VHostResponse",
    "VHostDetail",
    # Rule overrides
    "RuleOverrideCreate",
    "RuleOverrideResponse",
    "RuleOverrideUpdate",
    # Rule exclusions
    "RuleExclusionCreate",
    "RuleExclusionResponse",
    "RuleExclusionUpdate",
    # Custom rules
    "CustomRuleCreate",
    "CustomRuleResponse",
    "CustomRuleUpdate",
]
