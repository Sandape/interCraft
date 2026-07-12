"""Strict parser for untrusted model structured output."""
from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ValueError):
    def __init__(self, code: str, contract: str, message: str) -> None:
        self.code = code
        self.contract = contract
        super().__init__(message)


def parse_strict_output(payload: str | dict[str, object], model: type[T], *, contract: str) -> T:
    try:
        if isinstance(payload, str):
            decoder = json.JSONDecoder()
            raw = payload.strip()
            value, offset = decoder.raw_decode(raw)
            if raw[offset:].strip():
                raise StructuredOutputError(
                    "MULTIPLE_JSON_OBJECTS",
                    contract,
                    "Model returned trailing or multiple JSON values.",
                )
        else:
            value = payload
        return model.model_validate(value)
    except StructuredOutputError:
        raise
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise StructuredOutputError(
            "STRUCTURED_OUTPUT_INVALID", contract, "Model output failed strict validation."
        ) from exc
