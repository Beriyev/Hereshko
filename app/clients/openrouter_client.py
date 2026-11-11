"""Clients for OpenRouter's OpenAI-compatible API."""

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import HereshkoError

openrouter_client = OpenAI(api_key=settings.openrouter_api_key.get_secret_value() or "missing-openrouter-api-key",base_url="https://openrouter.ai/api/v1")
async_openrouter_client = AsyncOpenAI(api_key=settings.openrouter_api_key.get_secret_value() or "missing-openrouter-api-key",base_url="https://openrouter.ai/api/v1")


def openrouter_extra_body(*, model: str, require_parameters: bool = False) -> dict:
    body = {"reasoning": {"enabled": False}}
    provider = {}
    if model.lower().startswith("deepseek/"):
        provider["quantizations"] = ["fp4", "mxfp4", "nvfp4", "fp8", "mxfp8"]
    if require_parameters:
        provider["require_parameters"] = True
    if provider:
        body["provider"] = provider
    return body


def structured_options(schema: type[BaseModel], *, model: str) -> dict:
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
        },
        "extra_body": openrouter_extra_body(model=model, require_parameters=True),
    }


def response_text(response, empty_message: str) -> str:
    if not response.choices or not response.choices[0].message.content:
        raise HereshkoError(empty_message)
    return response.choices[0].message.content
