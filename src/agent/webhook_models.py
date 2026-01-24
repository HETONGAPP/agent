"""
Webhook request/response models
Provides validation for webhook payloads
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from datetime import datetime


class GrafanaWebhookPayload(BaseModel):
    """Validated Grafana webhook payload"""

    version: Optional[str] = Field(None, description="Webhook version")
    groupKey: Optional[str] = Field(None, description="Alert group key")
    status: Optional[str] = Field(None, description="Alert status")
    receiver: Optional[str] = Field(None, description="Receiver name")
    groupLabels: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Group labels")
    commonLabels: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Common labels")
    commonAnnotations: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Common annotations")
    externalURL: Optional[str] = Field(None, description="External URL")
    alerts: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Alert list")
    alert: Optional[Dict[str, Any]] = Field(None, description="Single alert (legacy)")
    state: Optional[str] = Field(None, description="Alert state")
    alertname: Optional[str] = Field(None, description="Alert name")
    timestamp: Optional[Any] = Field(None, description="Timestamp")
    time: Optional[Any] = Field(None, description="Time field")

    @validator("alerts", pre=True)
    def validate_alerts(cls, v):
        """Ensure alerts is a list"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v] if isinstance(v, dict) else []

    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class WebhookResponse(BaseModel):
    """Webhook response model"""

    status: str = Field(..., description="Response status")
    alarms_processed: Optional[int] = Field(None, description="Number of alarms processed")
    results: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Processing results")
    error: Optional[str] = Field(None, description="Error message")
    message: Optional[str] = Field(None, description="Response message")













