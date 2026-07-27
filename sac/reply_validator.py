"""Validador minimalista de reply_schema (JSON Schema, subconjunto stdlib).

Subconjunto suportado: `type` (object/string/number/array), `properties`,
`enum` e `required`. Construtos fora do subconjunto (oneOf, allOf, pattern,
format, $ref...) são rejeitados com "schema não suportado" em vez de
validados — sem dependências externas.
"""
from __future__ import annotations

import json

from .store import StoreError

SUPPORTED_TYPES = ("object", "string", "number", "array")
ALLOWED_KEYS = ("type", "properties", "enum", "required")


class SchemaError(StoreError):
    """reply_schema mal-formado ou fora do subconjunto suportado."""


def _typename(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    return "null"


class ReplyValidator:
    @staticmethod
    def parse_schema(text) -> dict:
        """Parseia e valida o schema contra o subconjunto. Levanta SchemaError."""
        if isinstance(text, dict):
            schema = text
        else:
            try:
                schema = json.loads(text)
            except (json.JSONDecodeError, TypeError) as e:
                raise SchemaError(f"reply_schema inválido: não é JSON ({text!r})") from e
        if not isinstance(schema, dict):
            raise SchemaError("reply_schema inválido: deve ser um objeto JSON")
        ReplyValidator._check_supported(schema, "$")
        return schema

    @staticmethod
    def _check_supported(schema: dict, path: str) -> None:
        for key in schema:
            if key not in ALLOWED_KEYS:
                raise SchemaError(f"schema não suportado: '{key}' em {path}")
        t = schema.get("type")
        if t is not None and t not in SUPPORTED_TYPES:
            raise SchemaError(f"schema não suportado: type '{t}' em {path}")
        req = schema.get("required")
        if req is not None and (
                not isinstance(req, list) or not all(isinstance(r, str) for r in req)):
            raise SchemaError(f"reply_schema inválido: 'required' deve ser lista de strings em {path}")
        enum = schema.get("enum")
        if enum is not None and not isinstance(enum, list):
            raise SchemaError(f"reply_schema inválido: 'enum' deve ser lista em {path}")
        props = schema.get("properties")
        if props is not None:
            if not isinstance(props, dict):
                raise SchemaError(f"reply_schema inválido: 'properties' deve ser objeto em {path}")
            for name, sub in props.items():
                if not isinstance(sub, dict):
                    raise SchemaError(f"reply_schema inválido: schema de '{name}' deve ser objeto em {path}")
                ReplyValidator._check_supported(sub, f"{path}.{name}")

    @staticmethod
    def validate(reply_body: str, schema: dict | None) -> tuple[bool, list[str]]:
        """Valida o corpo da reply contra o schema. Sem schema, sempre passa."""
        if not schema:
            return True, []
        try:
            data = json.loads(reply_body)
        except json.JSONDecodeError:
            return False, [f"reply não é JSON válido: {reply_body[:80]!r}"]
        errors: list[str] = []
        ReplyValidator._validate_value(data, schema, "", errors)
        return (not errors), errors

    @staticmethod
    def _validate_value(value, schema: dict, path: str, errors: list[str]) -> None:
        label = f"campo '{path}'" if path else "reply"
        t = schema.get("type")
        if t is not None:
            if t == "object" and not isinstance(value, dict):
                errors.append(f"{label}: esperado object, recebido {_typename(value)}")
                return
            if t == "string" and not isinstance(value, str):
                errors.append(f"{label}: esperado string, recebido {_typename(value)}")
                return
            if t == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                errors.append(f"{label}: esperado number, recebido {_typename(value)}")
                return
            if t == "array" and not isinstance(value, list):
                errors.append(f"{label}: esperado array, recebido {_typename(value)}")
                return
        if "enum" in schema and value not in schema["enum"]:
            permitidos = ", ".join(str(v) for v in schema["enum"])
            errors.append(f"{label} deve ser um dos valores: {permitidos}; recebido: {value!r}")
        if isinstance(value, dict):
            for req in schema.get("required", []):
                if req not in value:
                    nome = f"{path}.{req}" if path else req
                    errors.append(f"campo obrigatório ausente: '{nome}'")
            for name, sub in schema.get("properties", {}).items():
                if name in value:
                    nome = f"{path}.{name}" if path else name
                    ReplyValidator._validate_value(value[name], sub, nome, errors)
