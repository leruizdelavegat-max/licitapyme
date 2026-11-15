"""Interpretación del perfil de la empresa con IA.

La IA lee lo que la empresa DECLARÓ y propone cómo buscarla en el SEACE:
actividades, productos y servicios, palabras clave y categorías del catálogo.

Controles para que no invente:
- Solo puede resumir lo declarado: no agrega experiencia ni capacidades.
- Cada palabra sugerida se prueba contra las convocatorias reales: se muestra
  cuántas coinciden y se descartan las que no encuentran nada.
- Cada categoría sugerida se busca en el catálogo CUBSO real: solo quedan las que existen.
- Cobertura y capacidad NO las interpreta la IA: se muestran tal como se declararon.
"""

from __future__ import annotations

from pydantic import BaseModel

from ai.llm import pedir_json


class Interpretacion(BaseModel):
    actividades: list[str]
    productos: list[str]
    servicios: list[str]
    palabras_sugeridas: list[str]
    categorias_sugeridas: list[str]
    observacion: str


SISTEMA = """Ayudas a una MYPE peruana a encontrar contrataciones del Estado (SEACE).
Lee el perfil que la empresa DECLARÓ y responde SOLO con JSON:
{
 "actividades": ["1 a 3 actividades económicas principales, en frases cortas"],
 "productos": ["productos que comercializa, tal como se entienden del perfil"],
 "servicios": ["servicios que ofrece, tal como se entienden del perfil"],
 "palabras_sugeridas": ["8 a 15 palabras o frases cortas (1 a 3 palabras) que usan las entidades públicas
                         para comprar lo que esta empresa vende, en español y en el lenguaje del Estado
                         (ej.: 'útiles de escritorio', 'víveres', 'servicio de limpieza')"],
 "categorias_sugeridas": ["4 a 8 nombres de categorías del catálogo de bienes y servicios del Estado (CUBSO)
                          que correspondan a lo que vende, ej.: 'SERVICIO DE LIMPIEZA DE AREAS ADMINISTRATIVAS U OFICINAS'"],
 "observacion": "una frase: qué información falta en el perfil que ayudaría a encontrar mejores oportunidades"
}
REGLAS: no atribuyas a la empresa actividades, experiencia, certificaciones ni capacidades que no declaró.
Si un campo no se declaró, devuelve una lista vacía para él. No repitas palabras clave que la empresa ya tiene."""


def interpretar(texto_perfil: str, palabras_actuales: list[str]) -> dict | None:
    usuario = f"PERFIL DECLARADO:\n{texto_perfil}\n\nPALABRAS CLAVE QUE YA TIENE: {', '.join(palabras_actuales) or 'ninguna'}"
    r = pedir_json(SISTEMA, usuario, Interpretacion)
    return r.model_dump() if r else None
