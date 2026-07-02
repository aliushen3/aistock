"""Agent LUI/GUI — UI Block 协议类型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]
ActionKind = Literal["primary", "default", "danger"]


class UIAction(BaseModel):
    action_id: str
    label: str
    kind: ActionKind = "default"
    api_method: str | None = None
    api_path: str | None = None
    body_template: dict[str, Any] | None = None
    ontology_action: str | None = None
    requires_reason: bool = False
    confirm_text: str | None = None
    required_roles: list[str] = Field(default_factory=list)


class UIBlock(BaseModel):
    block_id: str
    type: str
    title: str
    agent_key: str | None = None
    risk_level: RiskLevel = "low"
    data: dict[str, Any] = Field(default_factory=dict)
    actions: list[UIAction] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)


class IntentRequest(BaseModel):
    message: str = Field(..., min_length=1)
    sector_id: str | None = None
    focus: str | None = None
    workflow_step: int | None = None
    recent_messages: list[str] = Field(default_factory=list)
    use_llm: bool = True


class IntentResponse(BaseModel):
    intent: str
    agent_key: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    assistant_message: str
    suggested_chips: list[str] = Field(default_factory=list)
    clarify: str | None = None
    router: str | None = None


class AgentSessionCreate(BaseModel):
    sector_id: str | None = None
    focus: str | None = None
    workflow_step: int | None = None
    operator: str = "analyst"


class AgentSessionUpdate(BaseModel):
    sector_id: str | None = None
    focus: str | None = None
    workflow_step: int | None = None
    messages: list[dict[str, Any]] | None = None
    ui_blocks: list[dict[str, Any]] | None = None
    chips: list[str] | None = None


class AgentSessionState(BaseModel):
    session_id: str
    operator: str = "analyst"
    sector_id: str | None = None
    focus: str | None = None
    workflow_step: int | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    ui_blocks: list[dict[str, Any]] = Field(default_factory=list)
    chips: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class SessionMessageRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)
    sector_id: str | None = None
    focus: str | None = None
    workflow_step: int | None = None
    recent_messages: list[str] = Field(default_factory=list)
    use_llm: bool = True
    stream_assistant: bool = True
    operator: str = "analyst"
