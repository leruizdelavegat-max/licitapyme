"""Extrae requisitos de las bases (PDF) de una convocatoria, con su página.

Flujo:
1. pypdf saca el texto de cada página (Document AI). Si el PDF es escaneado
   (casi sin texto) se avisa: haría falta OCR.
2. La IA lee el texto marcado con [PÁGINA n] y devuelve requisitos con una
   cita literal corta y la página.
3. Verificación anti-invención: cada cita se busca en el texto real del PDF.
   Si aparece, el requisito queda "verificado" (y se corrige la página si hacía
   falta). Si no aparece, se marca "no verificado" y se muestra aparte.

Las bases se suben a mano: el SEACE no permite descargas automáticas.
"""

from __future__ import annotations

import io
import unicodedata
from typing import Literal

from pydantic import BaseModel
from pypdf import PdfReader

from ai.llm import pedir_json

MAX_CARACTERES = 150_000  # ~40 mil tokens: alcanza para bases de 60-100 páginas

Categoria = Literal[
    "participacion", "experiencia", "documentacion", "tecnico", "entrega", "plazos", "garantias", "otros"
]
NOMBRE_CATEGORIA = {
    "participacion": "Requisitos de participación",
    "experiencia": "Experiencia requerida",
    "documentacion": "Documentación obligatoria",
    "tecnico": "Características técnicas",
    "entrega": "Condiciones de entrega o prestación",
    "plazos": "Plazos",
    "garantias": "Garantías y exigencias económicas",
    "otros": "Otros",
}


class Requisito(BaseModel):
    categoria: Categoria
    requisito: str
    obligatorio: bool | None = None
    pagina: int
    cita: str


class Respuesta(BaseModel):
    requisitos: list[Requisito]


SISTEMA = """Eres un especialista en contrataciones del Estado peruano. Lees las bases de una convocatoria
y extraes los requisitos que una MYPE debe cumplir para postular, en lenguaje simple.

Categorías: participacion, experiencia, documentacion, tecnico, entrega, plazos, garantias, otros.

REGLAS ESTRICTAS:
- Extrae SOLO lo que está escrito en el texto. No inventes requisitos.
- "cita" debe ser un fragmento LITERAL y corto (8 a 25 palabras) copiado exactamente del texto.
- "pagina" es el número que aparece en la marca [PÁGINA n] donde está la cita.
- "obligatorio": true si el texto lo exige, false si es opcional o para puntaje, null si no está claro.
- Prioriza: experiencia del postor (montos y años), documentos para la oferta y para el contrato,
  personal clave, requisitos técnicos mínimos, plazo de ejecución, lugar de entrega, garantías y penalidades.
- Entre 8 y 25 requisitos, sin repetir.

Responde SOLO con JSON: {"requisitos": [{"categoria": "...", "requisito": "...", "obligatorio": true, "pagina": 12, "cita": "..."}]}"""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def leer_pdf(datos: bytes) -> list[str]:
    """Texto de cada página del PDF."""
    lector = PdfReader(io.BytesIO(datos))
    return [(p.extract_text() or "") for p in lector.pages]


def es_escaneado(paginas: list[str]) -> bool:
    return sum(len(p.strip()) for p in paginas) < 200 * max(1, len(paginas)) * 0.2


def _verificar(req: Requisito, paginas_norm: list[str]) -> tuple[bool, int]:
    cita = _norm(req.cita)
    if len(cita) < 15:
        return False, req.pagina
    idx = req.pagina - 1
    if 0 <= idx < len(paginas_norm) and cita in paginas_norm[idx]:
        return True, req.pagina
    for i, texto in enumerate(paginas_norm):  # la cita existe pero en otra página
        if cita in texto:
            return True, i + 1
    return False, req.pagina


def extraer(datos: bytes) -> dict:
    paginas = leer_pdf(datos)
    if es_escaneado(paginas):
        return {"ok": False, "motivo": "El PDF parece escaneado (imágenes sin texto). Haría falta OCR.",
                "n_paginas": len(paginas), "requisitos": []}

    texto, truncado = "", False
    for i, p in enumerate(paginas, start=1):
        bloque = f"\n[PÁGINA {i}]\n{p}"
        if len(texto) + len(bloque) > MAX_CARACTERES:
            truncado = True
            break
        texto += bloque

    r = pedir_json(SISTEMA, f"TEXTO DE LAS BASES:\n{texto}", Respuesta, max_tokens=8000)
    if r is None:
        return {"ok": False, "motivo": "La IA no devolvió una respuesta válida. Intenta de nuevo.",
                "n_paginas": len(paginas), "requisitos": []}

    paginas_norm = [_norm(p) for p in paginas]
    salida = []
    for req in r.requisitos:
        ok, pag = _verificar(req, paginas_norm)
        salida.append({**req.model_dump(), "pagina": pag, "verificado": ok})
    return {"ok": True, "n_paginas": len(paginas), "truncado": truncado, "requisitos": salida}
