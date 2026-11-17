"""Perfil de mi empresa: todo en una sola página y un solo botón.

La persona completa datos, productos y servicios, y cobertura y capacidad; al guardar, la IA lee
todo junto y complementa el perfil (palabras clave, categorías y, si faltan, productos y servicios).
Las oportunidades guardadas, estados e historial se conservan.
"""

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

ui.encabezado("Perfil de mi empresa", "Completa la información de tu empresa y guarda: la IA la lee completa y "
              "complementa tu perfil automáticamente. Tus oportunidades guardadas e historial se conservan.",
              sobre=p["nombre"])

# ------------------------------------------------------------------ resultado del último guardado
guardado = st.session_state.pop("_perfil_guardado", None)
if guardado:
    msg = "Perfil guardado. Las recomendaciones y búsquedas ya usan la nueva información."
    if isinstance(guardado, dict):
        if guardado.get("completados"):
            msg += f" La IA completó: {', '.join(guardado['completados'])}."
        if guardado["agregadas"]:
            msg += f" Agregó estas palabras clave: {', '.join(guardado['agregadas'])}."
        if guardado["quitadas"]:
            msg += f" Quitó las que ya no corresponden a tu actividad: {', '.join(guardado['quitadas'])}."
    st.success(msg, icon=":material/check_circle:")
    if isinstance(guardado, dict) and guardado.get("desactualizados"):
        st.warning("Los productos y servicios que tienes registrados no corresponden a tu actividad (parecen de tu "
                   "rubro anterior). Corrígelos abajo, en **Productos y servicios**, y vuelve a guardar.",
                   icon=":material/warning:")


def guardar(nuevos: dict, reinterpretar: bool = True):
    despues = {**p, **nuevos}
    errs = fp.errores(1, despues) + fp.errores(3, despues)
    if errs:
        for x in errs:
            st.error(x, icon=":material/error:")
        return
    relevante = fp.cambio_relevante(p, despues)
    analisis, resumen = None, True
    # Si cambió algo importante, la IA vuelve a leer TODO el perfil y lo complementa.
    if relevante and reinterpretar and comun.hay_ia():
        cambio_actividad = p.get("actividad") if p.get("actividad") != despues.get("actividad") else None
        with st.spinner("La IA está leyendo tu perfil y completándolo…"):
            analisis = fp.ejecutar_interpretacion(despues, actividad_anterior=cambio_actividad)
        if analisis:
            sel = fp.seleccion_automatica(despues, analisis)
            despues["palabras_clave"], despues["categorias"] = sel["palabras_clave"], sel["categorias"]
            completados = []
            # Si la persona dejó vacíos productos o servicios, la IA los completa con lo típico de su actividad.
            if not despues.get("productos", "").strip() and analisis.get("productos"):
                despues["productos"] = ", ".join(analisis["productos"])
                completados.append("productos")
            if not despues.get("servicios", "").strip() and analisis.get("servicios"):
                despues["servicios"] = ", ".join(analisis["servicios"])
                completados.append("servicios")
            resumen = {**sel, "completados": completados,
                       "desactualizados": bool(analisis.get("productos_servicios_desactualizados")) and not completados}
    db.actualizar_empresa(emp["id"], uid, datos=despues, subir_version=relevante, analisis=analisis)
    if relevante and not analisis and reinterpretar:
        db.reiniciar_analisis(emp["id"], uid)
    db.registrar_evento(emp["id"], "Perfil actualizado")
    sesion.limpiar_cache()
    st.session_state["_perfil_guardado"] = resumen
    st.session_state["_form_perfil_n"] = st.session_state.get("_form_perfil_n", 0) + 1
    st.rerun()


# Cada guardado renueva las claves del formulario: así los campos muestran lo que completó la IA
# (Streamlit conserva lo escrito en un formulario mientras sus claves no cambien).
clave = f"ed{st.session_state.get('_form_perfil_n', 0)}"


# ------------------------------------------------------------------ formulario único
with st.form("form_perfil_completo", border=False):
    with st.container(border=True):
        st.markdown("**1. Datos de la empresa**")
        datos = fp.bloque_datos(p, clave)
    with st.container(border=True):
        st.markdown("**2. Productos y servicios**")
        oferta = fp.bloque_oferta(p, clave)
    with st.container(border=True):
        st.markdown("**3. Cobertura y capacidad**")
        cobertura = fp.bloque_cobertura(p, clave)
    enviar = st.form_submit_button("Guardar y completar con IA", type="primary", icon=":material/auto_awesome:")
if enviar:
    guardar({**datos, **oferta, **cobertura})

# ------------------------------------------------------------------ lo que completó la IA
ui.seccion("Perfil completado por la IA", "Cada sugerencia se prueba contra las convocatorias reales")
resultado = fp.vista_analisis(emp, "Guardar ajustes de palabras y categorías", automatico=False)
if resultado:
    guardar(resultado, reinterpretar=False)  # son elecciones explícitas: no se vuelven a cambiar

with st.expander("Mis datos", icon=":material/download:"):
    st.caption("Tu información está guardada en la base de datos de LicitaPYME"
               + (" (en la nube)." if db.es_nube() else " (en este equipo).")
               + " Puedes descargar una copia completa de esta empresa.")
    copia = {"perfil": p, "guardadas": comun.guardadas(), "evaluaciones": comun.evaluaciones(),
             "historial": db.historial_de(emp["id"])}
    st.download_button("Descargar mis datos (JSON)", json.dumps(copia, ensure_ascii=False, indent=1, default=str),
                       file_name=f"licitapyme_{emp['id']}.json", mime="application/json", icon=":material/download:")
