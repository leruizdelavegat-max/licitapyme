"""Borrador de carta de presentación para una convocatoria (función Premium).

Reglas para que no invente:
- Solo usa datos que la empresa declaró en su perfil y datos de la convocatoria.
- Todo dato que falte (RUC, representante legal, dirección, teléfono, montos, plazos) se deja como
  [COMPLETAR: ...] para que la empresa lo llene.
- No redacta declaraciones juradas ni anexos oficiales: esos tienen formatos legales fijos en las bases.
- Después de generarla, se verifica que no aparezcan RUC u otros números de 11 dígitos que la empresa no declaró.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from ai.llm import pedir_json


class Carta(BaseModel):
    lugar_fecha: str
    destinatario: str
    asunto: str
    parrafos: list[str]
    despedida: str
    firma: list[str]


SISTEMA = """Redactas BORRADORES de cartas de presentación de una MYPE peruana dirigidas a una entidad pública
que realiza una contratación. Español formal, claro y breve (3 a 5 párrafos cortos).

REGLAS ESTRICTAS:
- Usa SOLO los datos del perfil de la empresa y de la convocatoria que te doy. No inventes experiencia, clientes,
  certificaciones, montos, plazos, cantidades ni números de documento.
- Si un dato necesario no está (RUC, representante legal, dirección, teléfono, correo, fecha, número del
  procedimiento si falta), escribe exactamente [COMPLETAR: descripción del dato].
- No es una declaración jurada ni un anexo oficial: no afirmes que la empresa "cumple todos los requisitos";
  di que presenta su interés y que adjuntará la documentación solicitada en las bases.
- Menciona la nomenclatura del procedimiento y el objeto tal como vienen en la convocatoria.

Responde SOLO con JSON:
{"lugar_fecha": "...", "destinatario": "Señores: ... (entidad)", "asunto": "...",
 "parrafos": ["...", "..."], "despedida": "Atentamente,", "firma": ["[COMPLETAR: nombre del representante legal]", "...", "..."]}"""


def _mensaje(conv: dict, texto_perfil: str, ruc: str) -> str:
    return f"""PERFIL DE LA EMPRESA (lo único que puedes afirmar sobre ella):
{texto_perfil}
RUC declarado: {ruc or 'NO DECLARADO'}

CONVOCATORIA:
- Entidad: {conv.get('entidad')}
- Procedimiento / nomenclatura: {conv.get('metodo')} — {conv.get('nomenclatura')}
- Objeto: {conv.get('descripcion')}
- Departamento de la entidad: {conv.get('departamento')}"""


def verificar_numeros(texto: str, ruc_declarado: str) -> list[str]:
    """Números de 11 dígitos (como un RUC) que aparecen en la carta pero la empresa no declaró."""
    return [n for n in re.findall(r"\b\d{11}\b", texto) if n != (ruc_declarado or "")]


def redactar_carta(conv: dict, texto_perfil: str, ruc: str) -> dict | None:
    r = pedir_json(SISTEMA, _mensaje(conv, texto_perfil, ruc), Carta)
    if r is None:
        return None
    carta = r.model_dump()
    texto = "\n".join([carta["lugar_fecha"], carta["destinatario"], carta["asunto"], *carta["parrafos"], *carta["firma"]])
    sospechosos = verificar_numeros(texto, ruc)
    for n in sospechosos:  # si la IA puso un RUC que no existe en el perfil, se reemplaza por un espacio a completar
        for campo in ("lugar_fecha", "destinatario", "asunto", "despedida"):
            carta[campo] = carta[campo].replace(n, "[COMPLETAR: RUC]")
        carta["parrafos"] = [p.replace(n, "[COMPLETAR: RUC]") for p in carta["parrafos"]]
        carta["firma"] = [f.replace(n, "[COMPLETAR: RUC]") for f in carta["firma"]]
    carta["numeros_corregidos"] = len(sospechosos)
    return carta


def carta_a_texto(carta: dict) -> str:
    partes = [carta["lugar_fecha"], "", carta["destinatario"], "", f"Asunto: {carta['asunto']}", ""]
    partes += [p + "\n" for p in carta["parrafos"]]
    partes += [carta["despedida"], "", "", *carta["firma"]]
    return "\n".join(partes)
