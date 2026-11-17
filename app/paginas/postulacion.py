"""Premium · Preparar postulación: checklist, carta y cotización en un Word, para la convocatoria elegida."""

import pandas as pd
import streamlit as st

import comun
import ui
import word

p = comun.perfil()
emp = comun.empresa()
ev = comun.evaluaciones(solo_vigentes=True)
g = comun.guardadas()

st.html(
    '<div class="lp-enc"><div class="lp-sobre">Premium</div>'
    '<h1>Preparar postulación <span style="background:#FFF4D6;color:#8A5A00;border:1px solid #F2D27A;'
    'font-size:13px;font-weight:700;padding:3px 10px;border-radius:999px;vertical-align:middle;'
    'margin-left:6px;letter-spacing:.04em">PREMIUM</span></h1>'
    '<div class="lp-sub">Elige una convocatoria y LicitaPYME arma tu paquete de borradores: checklist de documentos, '
    'carta de presentación y cotización, en un Word listo para completar y revisar.</div></div>'
)
st.caption("Plan Premium (S/ 49 al mes). En esta versión de demostración está habilitado para todas las cuentas.")

# ------------------------------------------------------------------ elegir convocatoria
df = comun.enriquecer(comun.cargar_convocatorias(), p)
candidatas = df[df["ocid"].isin(set(g) | {o for o, r in ev.items() if r["semaforo"] != "rojo"})].copy()
if candidatas.empty:
    st.info("Primero guarda o evalúa con IA alguna convocatoria compatible. La más compatible aparecerá aquí.",
            icon=":material/info:")
    st.page_link("paginas/buscar.py", label="Ir a Buscar convocatorias", icon=":material/search:")
    st.stop()

candidatas = candidatas.sort_values(["compatibilidad"], ascending=False, na_position="last")
opciones = candidatas["ocid"].tolist()
por_ocid = candidatas.set_index("ocid")


def etiqueta(o: str) -> str:
    c = por_ocid.loc[o]
    compat = f"{int(c['compatibilidad'])} % · " if pd.notna(c["compatibilidad"]) else "sin evaluar · "
    return f"{compat}{c['entidad']} — {str(c['descripcion'])[:70]}"


sel = st.selectbox("Convocatoria (las más compatibles primero)", opciones, format_func=etiqueta)
conv = por_ocid.loc[sel].to_dict() | {"ocid": sel}
r_ev = ev.get(sel)

with st.container(border=True):
    estado = r_ev["semaforo"] if r_ev else "gris"
    texto = f"{r_ev['puntaje']} % · {ui.ESTADOS[estado]['etiqueta']}" if r_ev else "Sin evaluar"
    st.html(ui.pastilla(estado, texto) + f'<div class="lp-titulo" style="margin-top:8px">{ui.e(conv["entidad"])}</div>'
            f'<div class="lp-desc">{ui.e(conv["descripcion"])}</div>'
            + ui.meta([("Procedimiento", f"{conv['metodo']} — {conv['nomenclatura']}"),
                       ("Valor ref.", comun.soles(conv["monto_soles"])), ("Plazo", comun.plazo_txt(conv))]))
    if conv.get("url_bases"):
        st.link_button("Bases oficiales (SEACE)", conv["url_bases"], icon=":material/description:")
    if r_ev and r_ev["semaforo"] == "amarillo":
        st.warning("La IA recomienda revisar condiciones antes de postular a esta convocatoria.", icon=":material/warning:")

# Estado guardado de esta postulación (checklist marcado y carta editada).
todas = dict(comun.preferencias().get("postulacion") or {})
estado_post = dict(todas.get(sel) or {})


def guardar_estado():
    todas[sel] = estado_post
    comun.guardar_preferencia("postulacion", todas)


tab_check, tab_carta, tab_cot, tab_word = st.tabs(
    ["1. Checklist de documentos", "2. Carta de presentación", "3. Cotización", "4. Descargar en Word"],
    key="tabs_postulacion", on_change="rerun")  # recuerda la pestaña activa después de cada acción

# ------------------------------------------------------------------ 1. checklist
with tab_check:
    req = comun.requisitos().get(sel)
    verificados = [r for r in (req or {}).get("requisitos", []) if r.get("verificado")]
    if verificados:
        from ai.requisitos import NOMBRE_CATEGORIA
        fuente = "Requisitos verificados en el PDF de las bases (con su página)."
        filas = [{"clave": f"r{i}", "requisito": r["requisito"], "categoria": NOMBRE_CATEGORIA.get(r["categoria"], r["categoria"]),
                  "obligatorio": {True: "Sí", False: "No / puntaje", None: "No precisa"}[r["obligatorio"]],
                  "fuente": f"Bases, pág. {r['pagina']}"} for i, r in enumerate(verificados)]
    else:
        fuente = ("Aún no subiste las bases de esta convocatoria: el checklist usa lo que la IA recomendó revisar. "
                  "Es menos preciso. Sube el PDF en Mis oportunidades → Requisitos de las bases.")
        sugeridos = (r_ev or {}).get("revisar", [])
        filas = [{"clave": f"s{i}", "requisito": x, "categoria": "A revisar", "obligatorio": "Ver bases",
                  "fuente": "Sugerido por la IA (sin bases)"} for i, x in enumerate(sugeridos)]
    # El RNP vigente siempre es obligatorio para contratar con el Estado.
    filas.insert(0, {"clave": "rnp", "requisito": "Inscripción vigente en el RNP (Registro Nacional de Proveedores)",
                     "categoria": "Participación", "obligatorio": "Sí", "fuente": "Requisito general para contratar con el Estado"})
    marcados = estado_post.get("checklist", {})
    if "rnp" not in marcados and p.get("rnp") == "Sí, vigente":
        marcados["rnp"] = True
    tabla = pd.DataFrame([{**f, "listo": bool(marcados.get(f["clave"]))} for f in filas])
    st.caption(fuente)
    if not verificados:
        st.page_link("paginas/mis_oportunidades.py", label="Subir las bases para un checklist exacto", icon=":material/upload_file:")
    editado = st.data_editor(
        tabla[["listo", "requisito", "categoria", "obligatorio", "fuente", "clave"]], hide_index=True, width="stretch",
        disabled=["requisito", "categoria", "obligatorio", "fuente", "clave"], key=f"check_{sel}",
        column_config={"listo": st.column_config.CheckboxColumn("Lo tengo"), "requisito": st.column_config.TextColumn("Requisito", width="large"),
                       "categoria": "Tipo", "obligatorio": "Obligatorio", "fuente": "Fuente", "clave": None},
    )
    nuevos = {r["clave"]: bool(r["listo"]) for r in editado.to_dict("records")}
    if nuevos != marcados:
        estado_post["checklist"] = nuevos
        guardar_estado()
    listos = sum(nuevos.values())
    st.progress(listos / len(nuevos) if nuevos else 0, text=f"{listos} de {len(nuevos)} listos")

# ------------------------------------------------------------------ 2. carta
with tab_carta:
    st.caption("La IA redacta un borrador solo con los datos de tu perfil. Lo que falte queda como [COMPLETAR: …]. "
               "No reemplaza los anexos ni las declaraciones juradas de las bases.")
    carta = estado_post.get("carta")
    if comun.hay_ia() and st.button("Redactar carta con IA" if not carta else "Volver a redactar con IA",
                                    icon=":material/edit_note:", type="primary" if not carta else "secondary"):
        from ai.documentos import carta_a_texto, redactar_carta
        with st.spinner("Redactando el borrador…"):
            try:
                res = redactar_carta(conv, comun.texto_perfil(p), p.get("ruc", ""))
            except Exception as ex:
                print(f"[IA] carta: {type(ex).__name__}: {ex}")
                res = None
        if res is None:
            st.error("No se pudo redactar la carta. Intenta de nuevo.")
        else:
            estado_post["carta"] = carta_a_texto(res)
            guardar_estado()
            if res.get("numeros_corregidos"):
                st.toast("Se reemplazó un número que no está en tu perfil por [COMPLETAR: RUC].")
            st.rerun()
    if carta:
        texto = st.text_area("Puedes editar el borrador aquí", carta, height=420, key=f"carta_{sel}")
        pendientes = texto.count("[COMPLETAR")
        c1, c2 = st.columns([1, 3], vertical_alignment="center")
        if c1.button("Guardar cambios", icon=":material/save:"):
            estado_post["carta"] = texto
            guardar_estado()
            st.toast("Carta guardada")
        c2.caption(f"Quedan {pendientes} dato(s) por completar." if pendientes else "Sin datos pendientes por completar.")
    elif not comun.hay_ia():
        st.warning("La redacción con IA no está disponible ahora.")

# ------------------------------------------------------------------ 3. cotización
with tab_cot:
    adj = comun.cargar_adjudicaciones()
    items = [x for x in str(conv.get("rubros_cubso") or "").split(" | ") if x]
    filas_cot = []
    for item in items or [str(conv["descripcion"])[:80]]:
        ref = adj[(adj["cubso"] == item) & (adj["fecha"] >= "2025-01-01")]["monto_item"]
        referencia = (f"Mediana S/ {ref.median():,.0f} por ítem ({len(ref)} adjudicaciones desde 2025)"
                      if len(ref) >= 3 else "Sin suficientes adjudicaciones similares")
        filas_cot.append({"item": item, "referencia": referencia})
    st.caption("Ítems según las categorías del catálogo del Estado en la convocatoria. La referencia es la mediana de "
               "contrataciones adjudicadas en la misma categoría: guía de mercado, no garantía de precio. "
               "Cantidades y precios se completan según las bases.")
    st.dataframe(pd.DataFrame(filas_cot).rename(columns={"item": "Ítem (categoría CUBSO)", "referencia": "Referencia histórica"}),
                 hide_index=True, width="stretch")
    st.page_link("paginas/mercado.py", label="Ver el análisis de precios completo", icon=":material/monitoring:")

# ------------------------------------------------------------------ 4. Word
with tab_word:
    lista = editado.to_dict("records")
    carta_final = estado_post.get("carta") or ("[COMPLETAR: redacta la carta en la pestaña 2 o escríbela aquí]")
    pendientes = carta_final.count("[COMPLETAR") + 3 * len(filas_cot) + 2
    st.markdown("El documento incluye la **carta**, el **checklist** con lo que ya marcaste y el **borrador de cotización**. "
                "Los datos por completar van **resaltados en amarillo**.")
    if not estado_post.get("carta"):
        st.info("Todavía no redactaste la carta: el Word la incluirá como pendiente.", icon=":material/info:")
    archivo = word.generar(p["nombre"], conv, carta_final, lista, filas_cot, fuente)
    nombre = f"postulacion_{str(conv['nomenclatura'] or 'convocatoria').replace('/', '-')[:40]}.docx"
    st.download_button("Descargar paquete en Word", archivo, file_name=nombre, type="primary", icon=":material/download:",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.caption("Revisa todo antes de presentarlo. LicitaPYME prepara borradores; la responsabilidad de lo que se presenta "
               "es de la empresa.")
