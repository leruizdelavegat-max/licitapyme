"""Interpretación del perfil de la empresa con IA.

La IA lee lo que la empresa DECLARÓ y propone cómo buscarla en el SEACE:
actividades, productos y servicios típicos de su giro, palabras clave y
categorías del catálogo. También señala qué palabras clave ya no corresponden
a la actividad declarada (por ejemplo, si la empresa cambió de rubro).

Controles para que no invente:
- No agrega experiencia, certificaciones ni capacidades: eso solo lo declara la empresa.
- Los productos deducidos del giro ("una tienda de abarrotes vende arroz, azúcar…") se usan
  solo para BUSCAR convocatorias, y se muestran como sugeridos.
- Cada palabra sugerida se prueba contra las convocatorias reales: se descartan las que no encuentran nada.
- Cada categoría sugerida se busca en el catálogo CUBSO real: solo quedan las que existen.
- Cobertura y capacidad NO las interpreta la IA: se muestran tal como se declararon.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ai.llm import pedir_json


class Interpretacion(BaseModel):
    actividades: list[str]
    productos: list[str]
    servicios: list[str]
    palabras_sugeridas: list[str]
    palabras_no_relacionadas: list[str] = Field(default_factory=list)
    productos_servicios_desactualizados: bool = False
    categorias_sugeridas: list[str]
    observacion: str


SISTEMA = """Ayudas a una MYPE peruana a encontrar contrataciones del Estado (SEACE).
Lee el perfil que la empresa DECLARÓ. Lo más importante es su ACTIVIDAD: de ella deduce qué vende normalmente
ese tipo de negocio, aunque la empresa no lo haya listado (ej.: "tienda de abarrotes" → arroz, azúcar, aceite,
fideos, menestras, conservas, víveres).

Responde SOLO con JSON:
{
 "actividades": ["1 a 3 actividades económicas principales, en frases cortas"],
 "productos": ["productos que vende: los declarados y, si no declaró, los típicos de su actividad"],
 "servicios": ["servicios que ofrece: los declarados y, si no declaró, los típicos de su actividad (o lista vacía)"],
 "palabras_sugeridas": ["10 a 15 palabras o frases cortas (1 a 3 palabras) con las que las entidades públicas
                         compran lo que esta empresa vende, en el lenguaje del Estado (ej.: 'víveres', 'arroz',
                         'útiles de escritorio', 'servicio de limpieza'). Deben corresponder a su ACTIVIDAD."],
 "palabras_no_relacionadas": ["palabras clave que la empresa ya tiene pero que NO corresponden a su actividad
                              declarada (ej.: 'servicio de limpieza' en una tienda de abarrotes). Lista vacía si todas sirven."],
 "productos_servicios_desactualizados": true si los productos o servicios declarados NO corresponden a la actividad
                              (por ejemplo, quedaron de un rubro anterior); false si son coherentes,
 "categorias_sugeridas": ["4 a 8 nombres de categorías del catálogo de bienes y servicios del Estado (CUBSO)
                          que correspondan a lo que vende, ej.: 'ARROZ PILADO SUPERIOR', 'ACEITE VEGETAL COMESTIBLE'"],
 "observacion": "una frase: qué información falta en el perfil que ayudaría a encontrar mejores oportunidades"
}
REGLAS: no atribuyas a la empresa experiencia, certificaciones, clientes ni capacidades que no declaró.
No repitas en palabras_sugeridas las palabras que la empresa ya tiene.
Si la ACTIVIDAD y los productos/servicios declarados se contradicen, manda la ACTIVIDAD: sugiere palabras y
categorías de la actividad, no de los productos/servicios contradictorios."""


def interpretar(texto_perfil: str, palabras_actuales: list[str], actividad_anterior: str | None = None) -> dict | None:
    usuario = f"PERFIL DECLARADO:\n{texto_perfil}\n\nPALABRAS CLAVE QUE YA TIENE: {', '.join(palabras_actuales) or 'ninguna'}"
    if actividad_anterior:
        usuario += (f"\n\nATENCIÓN: la empresa acaba de CAMBIAR su actividad. Antes era: '{actividad_anterior}'. "
                    "Los productos, servicios y palabras clave pueden haber quedado del rubro anterior: si no "
                    "corresponden a la actividad nueva, ignóralos y márcalos como no relacionados/desactualizados.")
    r = pedir_json(SISTEMA, usuario, Interpretacion)
    return r.model_dump() if r else None
