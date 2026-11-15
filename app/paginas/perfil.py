"""Perfil de mi empresa: editar sin perder oportunidades guardadas ni historial."""

import json

import streamlit as st

import comun
import db
import formulario_perfil as fp
import sesion
import ui

emp = sesion.empresa_actual()
uid = sesion.usuario_id()
p = comun.perfil()

ui.encabezado("Perfil de mi empresa", "Edita la información de tu empresa. Tus oportunidades guardadas, estados e "
              "historial se conservan; las evaluaciones de IA anteriores se marcan como desactualizadas.",
              sobre=p["nombre"])

if st.session_state.pop("_perfil_guardado", None):
    st.success("Perfil actualizado. Las recomendaciones y búsquedas ya usan la nueva información.", icon=":material/check_circle:")

tab_datos, tab_oferta, tab_cob, tab_ia, tab_datos_exp = st.tabs(
    ["Datos", "Productos y servicios", "Cobertura y capacidad", "Interpretación de la IA", "Mis datos"])


def guardar(nuevos: dict, paso: int):
    errs = fp.errores(paso, {**p, **nuevos})
    if errs:
        for x in errs:
            st.error(x, icon=":material/error:")
        return
    despues = {**p, **nuevos}
    relevante = fp.cambio_relevante(p, despues)
    db.actualizar_empresa(emp["id"], uid, datos=despues, subir_version=relevante)
    if relevante:
        db.reiniciar_analisis(emp["id"], uid)
    db.registrar_evento(emp["id"], "Perfil actualizado")
    sesion.limpiar_cache()
    st.session_state["_perfil_guardado"] = True
    st.rerun()


with tab_datos:
    with st.form("form_datos"):
        nuevos = fp.bloque_datos(p, "ed")
        if st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:"):
            guardar(nuevos, 1)
with tab_oferta:
    with st.form("form_oferta"):
        nuevos = fp.bloque_oferta(p, "ed")
        if st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:"):
            guardar(nuevos, 2)
with tab_cob:
    with st.form("form_cobertura"):
        nuevos = fp.bloque_cobertura(p, "ed")
        if st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:"):
            guardar(nuevos, 3)
with tab_ia:
    st.caption("La IA sugiere palabras clave y categorías del catálogo del Estado a partir de lo que declaraste. "
               "Cada sugerencia se prueba contra las convocatorias reales.")
    resultado = fp.vista_analisis(emp, "Guardar palabras y categorías", automatico=False)
    if resultado:
        guardar(resultado, 2)
with tab_datos_exp:
    st.caption("Tu información está guardada en la base de datos de LicitaPYME"
               + (" (en la nube)." if db.es_nube() else " (en este equipo).")
               + " Puedes descargar una copia completa de esta empresa.")
    copia = {
        "perfil": p,
        "guardadas": comun.guardadas(),
        "evaluaciones": comun.evaluaciones(),
        "historial": db.historial_de(emp["id"]),
    }
    st.download_button("Descargar mis datos (JSON)", json.dumps(copia, ensure_ascii=False, indent=1, default=str),
                       file_name=f"licitapyme_{emp['id']}.json", mime="application/json", icon=":material/download:")
