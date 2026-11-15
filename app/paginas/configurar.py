"""Configuración inicial: la empresa se presenta y la IA interpreta su perfil.

Cada paso se guarda en la base como borrador: si la persona cierra la app a medio
camino, al volver continúa donde se quedó.
"""

import streamlit as st

import comun
import db
import formulario_perfil as fp
import sesion
import ui

emp = sesion.empresa_actual()
uid = sesion.usuario_id()
p = {**comun.PERFIL_VACIO, **(emp["datos"] if emp else {})}
paso = emp["paso"] if emp else 1

if paso < 4:
    ui.encabezado(
        "Comencemos conociendo tu empresa",
        "Cuéntanos qué productos comercializas, qué servicios ofreces y dónde puedes operar. Utilizaremos esta "
        "información para identificar oportunidades de contratación pública compatibles con tu negocio.",
        sobre="Configuración inicial",
    )
else:
    ui.encabezado("Así entendemos tu empresa",
                  "Revisa la interpretación, elige las palabras y categorías con las que buscaremos, y confirma.",
                  sobre="Configuración inicial")
ui.pasos(fp.PASOS, paso)


def guardar_paso(datos_nuevos: dict, siguiente: int):
    datos = {**p, **datos_nuevos}
    if emp is None:
        nuevo = db.crear_empresa(uid, datos, estado="borrador", paso=siguiente)
        sesion.cambiar_empresa(nuevo)
    else:
        db.actualizar_empresa(emp["id"], uid, datos=datos, paso=siguiente)
        if siguiente == 4:  # el perfil cambió: la IA debe volver a interpretarlo
            db.reiniciar_analisis(emp["id"], uid)
    sesion.limpiar_cache()
    st.rerun()


if paso in (1, 2, 3):
    with st.form(f"paso_{paso}", border=True):
        if paso == 1:
            datos = fp.bloque_datos(p, "cfg")
        elif paso == 2:
            datos = fp.bloque_oferta(p, "cfg")
        else:
            datos = fp.bloque_cobertura(p, "cfg")
        st.caption("Los campos con \\* son obligatorios.")
        c1, c2, _ = st.columns([1, 1.4, 3])
        atras = c1.form_submit_button("Atrás", icon=":material/arrow_back:", disabled=paso == 1)
        siguiente = c2.form_submit_button("Analizar mi perfil" if paso == 3 else "Siguiente", type="primary",
                                          icon=":material/auto_awesome:" if paso == 3 else ":material/arrow_forward:")
    if atras and emp:
        db.actualizar_empresa(emp["id"], uid, paso=paso - 1)
        sesion.limpiar_cache()
        st.rerun()
    if siguiente:
        errs = fp.errores(paso, datos)
        if errs:
            for x in errs:
                st.error(x, icon=":material/error:")
        else:
            guardar_paso(datos, paso + 1)
else:
    resultado = fp.vista_analisis(emp, "Confirmar perfil y buscar oportunidades")
    c1, _ = st.columns([1, 4])
    if c1.button("Volver a editar", icon=":material/edit:"):
        db.actualizar_empresa(emp["id"], uid, paso=3)
        sesion.limpiar_cache()
        st.rerun()
    if resultado:
        db.actualizar_empresa(emp["id"], uid, datos={**p, **resultado}, estado="confirmado", paso=4)
        db.registrar_evento(emp["id"], "Perfil confirmado")
        sesion.limpiar_cache()
        st.session_state["_bienvenida"] = True
        st.rerun()

# Si ya tiene otra empresa confirmada, puede cancelar este registro.
otras = [e for e in sesion.empresas() if e["estado"] == "confirmado" and (emp is None or e["id"] != emp["id"])]
if otras:
    st.divider()
    if st.button(f"Cancelar y volver a {otras[-1]['nombre']}", icon=":material/close:"):
        if emp is not None:
            db.eliminar_borrador(emp["id"], uid)
        sesion.cambiar_empresa(otras[-1]["id"])
        st.rerun()
