"""Quién es el usuario y con qué empresa está trabajando.

Tres modos:
- Nube con inicio de sesión: si los "secrets" tienen la sección [auth], se usa
  st.login() con Google y el usuario es su correo.
- Local: sin [auth] configurado (tu laptop, las pruebas) el usuario es "local".
- Demo: "Explorar con una empresa de ejemplo" crea un usuario demo:<id> con una
  empresa ya configurada, para que se pueda probar sin registrarse.
"""

from __future__ import annotations

import uuid

import streamlit as st

import db


def auth_configurado() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def usuario_id() -> str | None:
    if st.session_state.get("demo_id"):
        return st.session_state["demo_id"]
    if auth_configurado():
        return st.user.email if st.user.is_logged_in else None
    if db.es_nube():
        # Base compartida en la nube sin inicio de sesión: no se usa un usuario común
        # (todos verían las empresas de todos). Solo se permite el modo de ejemplo.
        return None
    return "local"


def es_demo() -> bool:
    return bool(st.session_state.get("demo_id"))


def iniciar_demo(datos_demo: dict):
    demo = f"demo:{uuid.uuid4().hex[:12]}"
    db.asegurar_usuario(demo, "Visitante (demo)")
    db.crear_empresa(demo, datos_demo, estado="confirmado", paso=4)
    st.session_state["demo_id"] = demo
    limpiar_cache()


def salir_demo():
    st.session_state.pop("demo_id", None)
    limpiar_cache()


# ------------------------------------------------------------------ caché por ejecución
def limpiar_cache():
    st.session_state.pop("_cache", None)


def _cache() -> dict:
    return st.session_state.setdefault("_cache", {})


def empresas() -> list[dict]:
    c = _cache()
    if "empresas" not in c:
        uid = usuario_id()
        if uid is None:
            return []
        nombre = getattr(st.user, "name", None) if auth_configurado() and not es_demo() else None
        db.asegurar_usuario(uid, nombre)
        c["empresas"] = db.empresas_de(uid)
    return c["empresas"]


def empresa_actual() -> dict | None:
    c = _cache()
    if "actual" not in c:
        lista = empresas()
        if not lista:
            c["actual"] = None
        else:
            ultima = db.asegurar_usuario(usuario_id())["ultima_empresa_id"]
            c["actual"] = next((e for e in lista if e["id"] == ultima), lista[-1])
    return c["actual"]


def cambiar_empresa(empresa_id: int):
    db.fijar_ultima_empresa(usuario_id(), empresa_id)
    for k in ("palabras_buscar", "palabras_mapa", "comparacion"):
        st.session_state.pop(k, None)
    limpiar_cache()


def nueva_empresa(datos_iniciales: dict) -> int:
    nuevo = db.crear_empresa(usuario_id(), datos_iniciales, estado="borrador", paso=1)
    cambiar_empresa(nuevo)
    return nuevo
