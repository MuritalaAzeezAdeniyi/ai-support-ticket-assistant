"""Validated argument and data models for support assistant tools."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Priority = Literal["low", "medium", "high", "critical"]
TicketStatus = Literal["open", "in_progress", "resolved"]


class TicketCreateArgs(BaseModel):
	"""Arguments accepted when requesting creation of a support ticket."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	title: str = Field(min_length=1, max_length=120)
	description: str = Field(min_length=1, max_length=2000)
	priority: Priority
	idempotency_key: str = Field(min_length=1, max_length=128)


class TicketRecord(BaseModel):
	"""A ticket record created and timestamped by the application."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	ticket_id: str = Field(min_length=1)
	title: str = Field(min_length=1, max_length=120)
	description: str = Field(min_length=1, max_length=2000)
	priority: Priority
	status: TicketStatus
	created_at: datetime


class TicketStatusArgs(BaseModel):
	"""Arguments for looking up a ticket's stored status."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	ticket_id: str = Field(min_length=1)


class EmailValidationArgs(BaseModel):
	"""Arguments for checking email syntax, not mailbox existence."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	email: EmailStr


class SimulatedSupportEmailArgs(BaseModel):
	"""Arguments for a validated, simulation-only support email request."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	recipient: EmailStr
	subject: str = Field(min_length=1, max_length=200)
	body: str = Field(min_length=1, max_length=5000)
