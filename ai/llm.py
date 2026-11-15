"""Cliente LLM compartido: pide JSON y lo valida con Pydantic.

Usamos DeepSeek por su API compatible con OpenAI. El "modo JSON" garantiza
JSON válido pero no los campos exactos, así que cada respuesta se valida con
un modelo Pydantic y se reintenta si no cumple el esquema.
"""

from __future__ import annotations

import json
import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

MODELO = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
T = TypeVar("T", bound=BaseModel)


def cliente() -> OpenAI:
    clave = os.getenv("DEEPSEEK_API_KEY")
    if not clave:
        raise RuntimeError("Falta DEEPSEEK_API_KEY (ver .env.example)")
    return OpenAI(api_key=clave, base_url="https://api.deepseek.com", timeout=120)


def pedir_json(sistema: str, usuario: str, esquema: type[T], intentos: int = 2, max_tokens: int = 4000) -> T | None:
    """Devuelve la respuesta validada contra `esquema`, o None si el modelo no cumplió."""
    c = cliente()
    for _ in range(intentos):
        resp = c.chat.completions.create(
            model=MODELO,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            response_format={"type": "json_object"},
            temperature=0.1,
            # El modelo razona antes de responder y esos tokens cuentan aquí:
            # con un límite bajo el JSON sale cortado.
            max_tokens=max_tokens,
        )
        try:
            return esquema.model_validate(json.loads(resp.choices[0].message.content))
        except (json.JSONDecodeError, ValidationError, TypeError):
            continue
    return None
