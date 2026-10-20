"""Small environment configuration helpers for the Gemini agent."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_TOOL_CALL_ROUNDS = 3


def load_project_environment() -> None:
	"""Load local .env values without overriding existing environment values."""
	load_dotenv(PROJECT_ROOT / ".env", override=False)


def get_gemini_api_key() -> str | None:
	load_project_environment()
	return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def get_gemini_model() -> str:
	load_project_environment()
	return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def get_tool_call_round_limit() -> int:
	load_project_environment()
	value = os.environ.get("GEMINI_TOOL_CALL_ROUNDS", str(DEFAULT_TOOL_CALL_ROUNDS))
	try:
		limit = int(value)
	except ValueError as error:
		raise ValueError("GEMINI_TOOL_CALL_ROUNDS must be a positive integer.") from error
	if limit < 1:
		raise ValueError("GEMINI_TOOL_CALL_ROUNDS must be a positive integer.")
	return limit