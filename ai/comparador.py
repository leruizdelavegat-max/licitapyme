"""Conclusión comparativa entre varias convocatorias para una misma empresa."""

from __future__ import annotations

from pydantic import BaseModel

from ai.llm import pedir_json


class Posicion(BaseModel):
    codigo: str
    razon: str


class Comparacion(BaseModel):
    ranking: list[Posicion]
    conclusion: str
    advertencia: str


SISTEMA = """Eres un asesor de contrataciones públicas para MYPES en Perú. Compara varias convocatorias
para UNA empresa y recomienda cuál priorizar.
REGLAS: el mayor monto NO es la mayor rentabilidad. Considera compatibilidad, requisitos, experiencia exigida,
capacidad operativa, distancia/cobertura, plazos y costos probables. No inventes datos que no estén.
Responde SOLO con JSON:
{"ranking": [{"codigo": "C1", "razon": "una frase"}, ...],   // de la más conveniente a la menos
 "conclusion": "2-3 frases simples: cuál priorizar y por qué",
 "advertencia": "qué información falta o qué verificar antes de decidir"}"""


def comparar(texto_perfil: str, fichas: list[dict]) -> dict | None:
    """`fichas`: dicts con 'codigo' (C1, C2…) y los datos de cada convocatoria y su evaluación."""
    bloques = []
    for f in fichas:
        bloques.append("\n".join(f"- {k}: {v}" for k, v in f.items()))
    usuario = f"PERFIL DE LA EMPRESA:\n{texto_perfil}\n\nCONVOCATORIAS:\n\n" + "\n\n".join(bloques)
    r = pedir_json(SISTEMA, usuario, Comparacion)
    if r is None:
        return None
    validos = {f["codigo"] for f in fichas}
    r.ranking = [x for x in r.ranking if x.codigo in validos]  # descarta códigos inventados
    return r.model_dump()
