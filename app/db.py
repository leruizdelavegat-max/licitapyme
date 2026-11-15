"""Persistencia de LicitaPYME.

Una sola capa de datos para dos motores:
- Local / pruebas: SQLite (archivo data/licitapyme.db, fuera de Git).
- Nube: PostgreSQL (Supabase), con la URL en DATABASE_URL (variable o "secrets" de Streamlit).

Todo lo que pertenece a una empresa (guardadas, historial, evaluaciones, requisitos,
preferencias) lleva su empresa_id: así los datos de varias empresas nunca se mezclan.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent

meta = sa.MetaData()

usuarios = sa.Table(
    "usuarios", meta,
    sa.Column("id", sa.String(320), primary_key=True),  # correo de Google, "local" o "demo:<id>"
    sa.Column("nombre", sa.String(200)),
    sa.Column("ultima_empresa_id", sa.Integer),
    sa.Column("creado", sa.DateTime, nullable=False),
)
empresas = sa.Table(
    "empresas", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("usuario_id", sa.String(320), sa.ForeignKey("usuarios.id"), nullable=False, index=True),
    sa.Column("nombre", sa.String(300), nullable=False),
    sa.Column("datos", sa.Text, nullable=False),          # perfil en JSON
    sa.Column("analisis", sa.Text),                       # interpretación de la IA en JSON
    sa.Column("estado", sa.String(20), nullable=False),   # "borrador" | "confirmado"
    sa.Column("paso", sa.Integer, nullable=False, default=1),
    sa.Column("version", sa.Integer, nullable=False, default=1),  # sube cuando cambia algo relevante
    sa.Column("creado", sa.DateTime, nullable=False),
    sa.Column("actualizado", sa.DateTime, nullable=False),
)
guardadas = sa.Table(
    "guardadas", meta,
    sa.Column("empresa_id", sa.Integer, sa.ForeignKey("empresas.id"), primary_key=True),
    sa.Column("ocid", sa.String(120), primary_key=True),
    sa.Column("estado", sa.String(40), nullable=False),
    sa.Column("nota", sa.Text, nullable=False, default=""),
    sa.Column("guardada_el", sa.DateTime, nullable=False),
)
historial = sa.Table(
    "historial", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("empresa_id", sa.Integer, sa.ForeignKey("empresas.id"), nullable=False, index=True),
    sa.Column("fecha", sa.DateTime, nullable=False),
    sa.Column("ocid", sa.String(120)),
    sa.Column("entidad", sa.String(400)),
    sa.Column("evento", sa.String(400), nullable=False),
)
evaluaciones = sa.Table(
    "evaluaciones", meta,
    sa.Column("empresa_id", sa.Integer, sa.ForeignKey("empresas.id"), primary_key=True),
    sa.Column("ocid", sa.String(120), primary_key=True),
    sa.Column("version_perfil", sa.Integer, nullable=False),
    sa.Column("resultado", sa.Text, nullable=False),
    sa.Column("fecha", sa.DateTime, nullable=False),
)
requisitos = sa.Table(
    "requisitos", meta,
    sa.Column("empresa_id", sa.Integer, sa.ForeignKey("empresas.id"), primary_key=True),
    sa.Column("ocid", sa.String(120), primary_key=True),
    sa.Column("resultado", sa.Text, nullable=False),
    sa.Column("fecha", sa.DateTime, nullable=False),
)
preferencias = sa.Table(
    "preferencias", meta,
    sa.Column("empresa_id", sa.Integer, sa.ForeignKey("empresas.id"), primary_key=True),
    sa.Column("datos", sa.Text, nullable=False),
)


def _url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    if not url:
        return f"sqlite:///{RAIZ / 'data' / 'licitapyme.db'}"
    if url.startswith("postgres://"):  # formato que entregan algunos proveedores
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@st.cache_resource(show_spinner=False)
def _motor(url: str) -> sa.Engine:
    motor = sa.create_engine(url, pool_pre_ping=True, future=True)
    meta.create_all(motor)
    return motor


def motor() -> sa.Engine:
    return _motor(_url())


def es_nube() -> bool:
    return not _url().startswith("sqlite")


def _ahora() -> datetime:
    return datetime.now().replace(microsecond=0)


# ------------------------------------------------------------------ usuarios
def asegurar_usuario(usuario_id: str, nombre: str | None = None) -> dict:
    with motor().begin() as c:
        fila = c.execute(sa.select(usuarios).where(usuarios.c.id == usuario_id)).mappings().first()
        if fila is None:
            c.execute(usuarios.insert().values(id=usuario_id, nombre=nombre, creado=_ahora()))
            fila = c.execute(sa.select(usuarios).where(usuarios.c.id == usuario_id)).mappings().first()
        return dict(fila)


def fijar_ultima_empresa(usuario_id: str, empresa_id: int | None):
    with motor().begin() as c:
        c.execute(usuarios.update().where(usuarios.c.id == usuario_id).values(ultima_empresa_id=empresa_id))


# ------------------------------------------------------------------ empresas
def _empresa(fila) -> dict:
    d = dict(fila)
    d["datos"] = json.loads(d["datos"])
    d["analisis"] = json.loads(d["analisis"]) if d.get("analisis") else None
    return d


def empresas_de(usuario_id: str) -> list[dict]:
    with motor().connect() as c:
        filas = c.execute(
            sa.select(empresas).where(empresas.c.usuario_id == usuario_id).order_by(empresas.c.creado)
        ).mappings().all()
    return [_empresa(f) for f in filas]


def empresa(empresa_id: int, usuario_id: str) -> dict | None:
    """Solo devuelve la empresa si pertenece al usuario."""
    with motor().connect() as c:
        fila = c.execute(
            sa.select(empresas).where(empresas.c.id == empresa_id, empresas.c.usuario_id == usuario_id)
        ).mappings().first()
    return _empresa(fila) if fila else None


def crear_empresa(usuario_id: str, datos: dict, estado: str = "borrador", paso: int = 1) -> int:
    with motor().begin() as c:
        r = c.execute(empresas.insert().values(
            usuario_id=usuario_id, nombre=datos.get("nombre") or "Mi empresa", datos=json.dumps(datos, ensure_ascii=False),
            estado=estado, paso=paso, version=1, creado=_ahora(), actualizado=_ahora(),
        ))
        nuevo = r.inserted_primary_key[0]
    fijar_ultima_empresa(usuario_id, nuevo)
    return nuevo


def actualizar_empresa(empresa_id: int, usuario_id: str, *, datos: dict | None = None, analisis: dict | None = None,
                       estado: str | None = None, paso: int | None = None, subir_version: bool = False):
    valores: dict = {"actualizado": _ahora()}
    if datos is not None:
        valores["datos"] = json.dumps(datos, ensure_ascii=False)
        valores["nombre"] = datos.get("nombre") or "Mi empresa"
    if analisis is not None:
        valores["analisis"] = json.dumps(analisis, ensure_ascii=False)
    if estado is not None:
        valores["estado"] = estado
    if paso is not None:
        valores["paso"] = paso
    if subir_version:
        valores["version"] = empresas.c.version + 1
    with motor().begin() as c:
        c.execute(empresas.update().where(empresas.c.id == empresa_id, empresas.c.usuario_id == usuario_id).values(**valores))


def reiniciar_analisis(empresa_id: int, usuario_id: str):
    """Borra la interpretación de la IA para que se recalcule con el perfil actualizado."""
    with motor().begin() as c:
        c.execute(empresas.update().where(empresas.c.id == empresa_id, empresas.c.usuario_id == usuario_id)
                  .values(analisis=None))


def eliminar_borrador(empresa_id: int, usuario_id: str):
    """Solo se pueden eliminar empresas que nunca se confirmaron (no tienen datos asociados)."""
    with motor().begin() as c:
        c.execute(empresas.delete().where(empresas.c.id == empresa_id, empresas.c.usuario_id == usuario_id,
                                          empresas.c.estado == "borrador"))


# ------------------------------------------------------------------ guardadas e historial
def guardadas_de(empresa_id: int) -> dict:
    with motor().connect() as c:
        filas = c.execute(sa.select(guardadas).where(guardadas.c.empresa_id == empresa_id)).mappings().all()
    return {f["ocid"]: {"estado": f["estado"], "nota": f["nota"], "guardada_el": f["guardada_el"]} for f in filas}


def guardar(empresa_id: int, ocid: str, entidad: str | None):
    with motor().begin() as c:
        existe = c.execute(sa.select(guardadas.c.ocid).where(guardadas.c.empresa_id == empresa_id, guardadas.c.ocid == ocid)).first()
        if existe:
            return
        c.execute(guardadas.insert().values(empresa_id=empresa_id, ocid=ocid, estado="Guardada", nota="", guardada_el=_ahora()))
        c.execute(historial.insert().values(empresa_id=empresa_id, fecha=_ahora(), ocid=ocid, entidad=entidad, evento="Guardada"))


def actualizar_guardada(empresa_id: int, ocid: str, entidad: str | None, *, estado: str | None = None, nota: str | None = None):
    with motor().begin() as c:
        actual = c.execute(sa.select(guardadas).where(guardadas.c.empresa_id == empresa_id, guardadas.c.ocid == ocid)).mappings().first()
        if actual is None:
            return
        valores = {}
        if estado is not None and estado != actual["estado"]:
            valores["estado"] = estado
            c.execute(historial.insert().values(empresa_id=empresa_id, fecha=_ahora(), ocid=ocid, entidad=entidad,
                                                evento=f"{actual['estado']} → {estado}"))
        if nota is not None and nota != actual["nota"]:
            valores["nota"] = nota
        if valores:
            c.execute(guardadas.update().where(guardadas.c.empresa_id == empresa_id, guardadas.c.ocid == ocid).values(**valores))


def quitar_guardada(empresa_id: int, ocid: str, entidad: str | None):
    with motor().begin() as c:
        c.execute(guardadas.delete().where(guardadas.c.empresa_id == empresa_id, guardadas.c.ocid == ocid))
        c.execute(historial.insert().values(empresa_id=empresa_id, fecha=_ahora(), ocid=ocid, entidad=entidad,
                                            evento="Quitada de mis oportunidades"))


def registrar_evento(empresa_id: int, evento: str, ocid: str | None = None, entidad: str | None = None):
    with motor().begin() as c:
        c.execute(historial.insert().values(empresa_id=empresa_id, fecha=_ahora(), ocid=ocid, entidad=entidad, evento=evento))


def historial_de(empresa_id: int) -> list[dict]:
    with motor().connect() as c:
        filas = c.execute(sa.select(historial).where(historial.c.empresa_id == empresa_id)
                          .order_by(historial.c.fecha.desc(), historial.c.id.desc())).mappings().all()
    return [dict(f) for f in filas]


# ------------------------------------------------------------------ evaluaciones y requisitos
def _upsert(c, tabla, claves: dict, valores: dict):
    cond = [tabla.c[k] == v for k, v in claves.items()]
    r = c.execute(tabla.update().where(*cond).values(**valores))
    if r.rowcount == 0:
        c.execute(tabla.insert().values(**claves, **valores))


def evaluaciones_de(empresa_id: int) -> dict:
    with motor().connect() as c:
        filas = c.execute(sa.select(evaluaciones).where(evaluaciones.c.empresa_id == empresa_id)).mappings().all()
    return {f["ocid"]: {**json.loads(f["resultado"]), "version_perfil": f["version_perfil"]} for f in filas}


def guardar_evaluacion(empresa_id: int, ocid: str, version_perfil: int, resultado: dict):
    with motor().begin() as c:
        _upsert(c, evaluaciones, {"empresa_id": empresa_id, "ocid": ocid},
                {"version_perfil": version_perfil, "resultado": json.dumps(resultado, ensure_ascii=False, default=str),
                 "fecha": _ahora()})


def borrar_evaluacion(empresa_id: int, ocid: str):
    with motor().begin() as c:
        c.execute(evaluaciones.delete().where(evaluaciones.c.empresa_id == empresa_id, evaluaciones.c.ocid == ocid))


def requisitos_de(empresa_id: int) -> dict:
    with motor().connect() as c:
        filas = c.execute(sa.select(requisitos).where(requisitos.c.empresa_id == empresa_id)).mappings().all()
    return {f["ocid"]: json.loads(f["resultado"]) for f in filas}


def guardar_requisitos(empresa_id: int, ocid: str, resultado: dict):
    with motor().begin() as c:
        _upsert(c, requisitos, {"empresa_id": empresa_id, "ocid": ocid},
                {"resultado": json.dumps(resultado, ensure_ascii=False), "fecha": _ahora()})


# ------------------------------------------------------------------ preferencias
def preferencias_de(empresa_id: int) -> dict:
    with motor().connect() as c:
        fila = c.execute(sa.select(preferencias.c.datos).where(preferencias.c.empresa_id == empresa_id)).first()
    return json.loads(fila[0]) if fila else {}


def guardar_preferencias(empresa_id: int, datos: dict):
    with motor().begin() as c:
        _upsert(c, preferencias, {"empresa_id": empresa_id}, {"datos": json.dumps(datos, ensure_ascii=False)})
