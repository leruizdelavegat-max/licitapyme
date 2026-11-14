"""Análisis de una convocatoria con un LLM y salida estructurada.

El LLM (DeepSeek, vía su API compatible con OpenAI) lee la convocatoria y el
perfil de la PYME y devuelve un JSON. Ese JSON se valida con Pydantic: si no
trae los campos correctos, se reintenta una vez y si falla se descarta.
Así la app nunca muestra una respuesta mal formada.
"""

from __future__ import annotations

import json
import os

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

MODELO = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")


class Analisis(BaseModel):
    resumen: str = Field(description="Qué compra la entidad, en 2 o 3 frases simples")
    encaje: int = Field(ge=0, le=100, description="0-100: qué tan bien encaja con la PYME")
    razon_encaje: str = Field(description="Por qué ese puntaje, en una frase")
    que_revisar: list[str] = Field(description="2 a 4 cosas a revisar en las bases antes de postular")
    alerta: str | None = Field(default=None, description="Riesgo importante, o null si no hay")


SISTEMA = """Eres un asesor experto en contrataciones del Estado peruano (SEACE, Ley 32069).
Ayudas a PYMES a decidir si les conviene postular a una convocatoria.
Responde SOLO con un objeto JSON con exactamente estas claves:
{
  "resumen": "qué compra la entidad, en 2 o 3 frases simples, sin jerga",
  "encaje": entero de 0 a 100 (qué tan bien encaja con lo que vende la PYME, su región y su capacidad),
  "razon_encaje": "una frase que explique el puntaje",
  "que_revisar": ["2 a 4 cosas concretas a revisar en las bases antes de postular"],
  "alerta": "un riesgo importante (plazo, monto fuera de su capacidad, lejanía, experiencia exigida) o null"
}
Sé honesto: si no encaja, pon un puntaje bajo. No inventes datos que no estén en la convocatoria."""


def _cliente() -> OpenAI:
    clave = os.getenv("DEEPSEEK_API_KEY")
    if not clave:
        raise RuntimeError("Falta DEEPSEEK_API_KEY (ver .env.example)")
    return OpenAI(api_key=clave, base_url="https://api.deepseek.com")


def _mensaje_usuario(conv: dict, perfil: str) -> str:
    monto = conv.get("monto_soles")
    monto_txt = f"S/ {monto:,.0f}" if monto else "no publicado"
    return f"""PERFIL DE LA PYME:
{perfil}

CONVOCATORIA:
- Entidad: {conv.get('entidad')} ({conv.get('departamento')}, {conv.get('localidad')})
- Procedimiento: {conv.get('metodo')} — {conv.get('nomenclatura')}
- Tipo: {conv.get('categoria')}
- Monto referencial: {monto_txt}
- Publicada: {conv.get('fecha_publicacion')}
- Descripción: {conv.get('descripcion')}
- Rubros (CUBSO): {conv.get('rubros_cubso')}
- Número de ítems: {conv.get('n_items')}"""


def analizar(conv: dict, perfil: str, intentos: int = 2) -> Analisis | None:
    """Devuelve el análisis validado, o None si el modelo no respondió bien."""
    cliente = _cliente()
    for _ in range(intentos):
        resp = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": _mensaje_usuario(conv, perfil)},
            ],
            response_format={"type": "json_object"},  # modo JSON de DeepSeek
            temperature=0.2,
            # El modelo razona antes de responder y esos tokens cuentan aquí:
            # con un límite bajo el JSON sale cortado.
            max_tokens=2500,
        )
        try:
            return Analisis.model_validate(json.loads(resp.choices[0].message.content))
        except (json.JSONDecodeError, ValidationError, TypeError):
            continue
    return None


if __name__ == "__main__":
    # Prueba rápida: python ai/analizar.py
    from pathlib import Path

    import pandas as pd
    from dotenv import load_dotenv

    raiz = Path(__file__).resolve().parent.parent
    load_dotenv(raiz / ".env")
    df = pd.read_parquet(raiz / "data" / "convocatorias.parquet")
    fila = df[df["descripcion"].str.contains("LIMPIEZA", na=False)].iloc[0].to_dict()
    perfil = "Vendemos productos de limpieza en Lima y Callao. Facturamos S/ 400 mil al año."
    print(fila["descripcion"])
    print(analizar(fila, perfil))
