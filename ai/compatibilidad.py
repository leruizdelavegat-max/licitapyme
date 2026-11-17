"""Metodología de compatibilidad empresa ↔ convocatoria.

El porcentaje NO lo inventa el modelo. Se calcula en Python con pesos fijos:

1. Cada uno de 7 criterios recibe un estado:
     cumple (1.0) · debe acreditar (0.6) · no cumple (0.0) · sin información (no cuenta)
2. Dos criterios los decide una REGLA FIJA con datos verificables
   (cobertura geográfica y capacidad económica). Los otros cinco los evalúa la IA,
   que debe citar la evidencia y marcar "sin información" cuando el dato no está.
3. Puntaje = Σ(peso × valor) / Σ(pesos con información) × 100
   Confianza = Σ(pesos con información) / 100
4. Semáforo:
     rojo     → "no cumple" en un criterio excluyente (objeto, experiencia o requisitos)
     verde    → puntaje ≥ 70, confianza ≥ 60 % y ningún excluyente incumplido
     amarillo → todo lo demás (incluida la información insuficiente)
   La falta de información nunca se convierte en verde ni en rojo por sí sola.

Ver docs/metodologia.md.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from ai.llm import pedir_json

Estado = Literal["cumple", "por_acreditar", "no_cumple", "sin_informacion"]
VALOR = {"cumple": 1.0, "por_acreditar": 0.6, "no_cumple": 0.0}
ETIQUETA_ESTADO = {
    "cumple": "Cumple",
    "por_acreditar": "Debe acreditar",
    "no_cumple": "No cumple",
    "sin_informacion": "Sin información",
}

CRITERIOS = {
    "objeto": {"nombre": "Bienes/servicios vs. objeto de la contratación", "peso": 30, "fuente": "ia", "excluyente": True},
    "actividad": {"nombre": "Actividad económica", "peso": 15, "fuente": "ia", "excluyente": False},
    "cobertura": {"nombre": "Cobertura geográfica", "peso": 15, "fuente": "regla", "excluyente": False},
    "capacidad": {"nombre": "Capacidad económica vs. monto", "peso": 15, "fuente": "regla", "excluyente": False},
    "experiencia": {"nombre": "Experiencia solicitada", "peso": 10, "fuente": "ia", "excluyente": True},
    "requisitos": {"nombre": "Requisitos técnicos y documentarios", "peso": 10, "fuente": "ia", "excluyente": True},
    "otras": {"nombre": "Otras condiciones (plazos, entrega, lugar)", "peso": 5, "fuente": "ia", "excluyente": False},
}


class Criterio(BaseModel):
    estado: Estado
    evidencia: str = Field(min_length=3)


class RespuestaIA(BaseModel):
    resumen: str
    objeto: Criterio
    actividad: Criterio
    experiencia: Criterio
    requisitos: Criterio
    otras: Criterio
    por_que: str
    ventajas: list[str]
    dificultades: list[str]
    revisar: list[str]
    vale_la_pena: str


SISTEMA = """Eres un asesor en contrataciones del Estado peruano que ayuda a micro y pequeñas empresas (MYPE).
Evalúas si una convocatoria es compatible con una empresa. Hablas en lenguaje simple, sin jerga legal.

Evalúa SOLO estos 5 criterios (otros los calcula el sistema):
- objeto: ¿lo que la entidad compra coincide con los bienes o servicios que la empresa ofrece?
- actividad: ¿la actividad económica de la empresa corresponde a este tipo de contratación?
- experiencia: ¿la empresa tiene la experiencia que se pediría? Si la convocatoria no indica la experiencia exigida, usa "sin_informacion".
- requisitos: requisitos técnicos y documentarios (incluye RNP vigente, que es obligatorio para contratar con el Estado). Si no hay información de requisitos específicos, usa "sin_informacion" salvo lo que se pueda verificar.
- otras: plazos, lugar o condiciones de entrega o prestación. MUY IMPORTANTE: la sede de la entidad no siempre es
  el lugar de ejecución. Si la descripción dice dónde se entrega o se presta el servicio (p. ej. "agencias en Cusco,
  Puno…", "obra en Ayacucho") y ese lugar está FUERA de los departamentos de cobertura de la empresa, marca
  "no_cumple" y dilo en la evidencia; también menciónalo en "dificultades".

Para cada criterio elige un estado:
- "cumple": hay evidencia de que la empresa cumple.
- "por_acreditar": probablemente cumple pero tendrá que demostrarlo con documentos.
- "no_cumple": hay evidencia clara de que NO cumple.
- "sin_informacion": la convocatoria o el perfil no dan datos suficientes.
REGLAS: La falta de información NO es incumplimiento. No inventes requisitos, montos ni plazos que no estén en los datos.
En "evidencia" cita el dato concreto (de la convocatoria o del perfil) que justifica el estado.
Si te entregan una lista de requisitos extraídos de las bases, úsala y menciona la página.

Responde SOLO con un JSON con exactamente estas claves:
{
 "resumen": "qué compra la entidad, en 2 frases simples",
 "objeto": {"estado": "...", "evidencia": "..."},
 "actividad": {"estado": "...", "evidencia": "..."},
 "experiencia": {"estado": "...", "evidencia": "..."},
 "requisitos": {"estado": "...", "evidencia": "..."},
 "otras": {"estado": "...", "evidencia": "..."},
 "por_que": "por qué es (o no es) compatible, en 1-2 frases",
 "ventajas": ["1 a 3 ventajas concretas para esta empresa"],
 "dificultades": ["1 a 3 dificultades que podría encontrar"],
 "revisar": ["2 a 4 cosas a revisar con atención en las bases"],
 "vale_la_pena": "una frase que empiece con 'Sí', 'Tal vez' o 'No' y diga si conviene evaluarla"
}"""


# ------------------------------------------------------------------ reglas fijas
def regla_cobertura(conv: dict, perfil: dict) -> dict:
    dep = conv.get("departamento")
    if not perfil.get("cobertura"):
        return {"estado": "sin_informacion", "evidencia": "La empresa no declaró su cobertura geográfica."}
    if not dep:
        return {"estado": "sin_informacion", "evidencia": "La convocatoria no indica el departamento."}
    if dep in perfil["cobertura"]:
        return {"estado": "cumple", "evidencia": f"La entidad está en {dep.title()}, dentro de tu cobertura."}
    return {
        "estado": "no_cumple",
        "evidencia": f"La entidad está en {dep.title()}, fuera de tu cobertura declarada "
        f"({', '.join(d.title() for d in perfil['cobertura'])}). No se excluye: puedes ampliar tu cobertura.",
    }


def regla_capacidad(conv: dict, perfil: dict) -> dict:
    monto, maximo = conv.get("monto_soles"), perfil.get("monto_max") or 0
    if monto is None or pd.isna(monto) or monto == 0:
        return {"estado": "sin_informacion", "evidencia": "La entidad no publicó el valor referencial."}
    if not maximo:
        return {"estado": "sin_informacion", "evidencia": "La empresa no indicó el monto máximo que puede atender."}
    if monto <= maximo:
        return {"estado": "cumple", "evidencia": f"Monto S/ {monto:,.0f} ≤ tu máximo S/ {maximo:,.0f}."}
    if monto <= 1.5 * maximo:
        return {
            "estado": "por_acreditar",
            "evidencia": f"Monto S/ {monto:,.0f} supera tu máximo (S/ {maximo:,.0f}) en menos de 50 %: "
            "posible con financiamiento o en consorcio.",
        }
    return {"estado": "no_cumple", "evidencia": f"Monto S/ {monto:,.0f} supera ampliamente tu máximo de S/ {maximo:,.0f}."}


# ------------------------------------------------------------------ cálculo
def calcular(criterios: dict) -> dict:
    con_info = {k: v for k, v in criterios.items() if v["estado"] != "sin_informacion"}
    peso_info = sum(CRITERIOS[k]["peso"] for k in con_info)
    puntaje = round(100 * sum(CRITERIOS[k]["peso"] * VALOR[v["estado"]] for k, v in con_info.items()) / peso_info) if peso_info else 0
    confianza = peso_info  # los pesos suman 100
    excluyente_falla = any(CRITERIOS[k]["excluyente"] and v["estado"] == "no_cumple" for k, v in criterios.items())
    # Si el lugar real de ejecución está fuera de la cobertura, no puede ser "alta compatibilidad".
    fuera_de_zona = criterios.get("otras", {}).get("estado") == "no_cumple"
    if excluyente_falla:
        semaforo = "rojo"
    elif fuera_de_zona:
        semaforo = "amarillo"
    elif puntaje >= 70 and confianza >= 60:
        semaforo = "verde"
    else:
        semaforo = "amarillo"
    return {"puntaje": puntaje, "confianza": confianza, "semaforo": semaforo}


def _mensaje(conv: dict, texto_perfil: str, requisitos: list | None) -> str:
    monto = conv.get("monto_soles")
    monto_txt = f"S/ {monto:,.0f}" if monto and not pd.isna(monto) else "no publicado"
    req = ""
    if requisitos:
        req = "\n\nREQUISITOS EXTRAÍDOS DE LAS BASES (verificados en el PDF):\n" + "\n".join(
            f"- [{r['categoria']}] {r['requisito']} (pág. {r['pagina']})" for r in requisitos
        )
    return f"""PERFIL DE LA EMPRESA:
{texto_perfil}

CONVOCATORIA (datos abiertos del SEACE):
- Entidad: {conv.get('entidad')} — {conv.get('departamento')}, {conv.get('localidad')}
- Procedimiento: {conv.get('metodo')} — {conv.get('nomenclatura')}
- Tipo: {conv.get('categoria')}
- Valor referencial: {monto_txt}
- Descripción: {conv.get('descripcion')}
- Rubros (CUBSO): {conv.get('rubros_cubso')}
- Número de ítems: {conv.get('n_items')}
- Fin de consultas y observaciones: {conv.get('consultas_fin')}{req}"""


def evaluar(conv: dict, perfil: dict, texto_perfil: str, requisitos: list | None = None) -> dict | None:
    r = pedir_json(SISTEMA, _mensaje(conv, texto_perfil, requisitos), RespuestaIA)
    if r is None:
        return None
    criterios = {
        "objeto": r.objeto.model_dump(),
        "actividad": r.actividad.model_dump(),
        "cobertura": regla_cobertura(conv, perfil),
        "capacidad": regla_capacidad(conv, perfil),
        "experiencia": r.experiencia.model_dump(),
        "requisitos": r.requisitos.model_dump(),
        "otras": r.otras.model_dump(),
    }
    return {
        **calcular(criterios),
        "criterios": criterios,
        "resumen": r.resumen,
        "por_que": r.por_que,
        "ventajas": r.ventajas,
        "dificultades": r.dificultades,
        "revisar": r.revisar,
        "vale_la_pena": r.vale_la_pena,
        "con_requisitos_pdf": bool(requisitos),
    }
