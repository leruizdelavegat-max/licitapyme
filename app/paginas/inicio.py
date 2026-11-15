"""Inicio: resumen de oportunidades para la empresa y recomendaciones de la IA."""

import streamlit as st

import comun

p = comun.perfil()
df = comun.enriquecer(comun.cargar_convocatorias(), p)
abiertas = df[(df["estado"] == "CONVOCADO") & df["categoria"].isin(p["tipos"])]
para_mi = abiertas[abiertas["coincidencia"] > 0].sort_values(
    ["en_cobertura", "coincidencia", "fecha_publicacion"], ascending=[False, False, False])
ev = comun.evaluaciones()

st.title("📋 LicitaPYME")
st.markdown(
    f"#### Oportunidades del Estado para **{p['nombre']}**\n"
    "Convertimos los datos públicos de contrataciones en oportunidades de negocio que una MYPE puede entender."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Convocatorias abiertas", f"{len(abiertas):,}", help="Estado CONVOCADO en el último corte de datos, del tipo que ofreces.")
c2.metric("Coinciden con tu perfil", f"{len(para_mi):,}")
c3.metric("En tu cobertura", f"{int(para_mi['en_cobertura'].sum()):,}")
verdes = sum(1 for o in para_mi["ocid"] if o in ev and ev[o]["semaforo"] == "verde")
c4.metric("🟢 Recomendadas por la IA", f"{verdes}", help="Evaluadas con alta compatibilidad.")

if para_mi.empty:
    st.info("Ninguna convocatoria coincide con tus palabras clave. Ajusta tu perfil en **🏢 Perfil de mi empresa**.")
    st.stop()

# ------------------------------------------------------------------ recomendaciones IA
st.subheader("🤖 Recomendaciones de la IA")
evaluadas = para_mi[para_mi["ocid"].isin(ev)]
if evaluadas.empty:
    st.caption("La IA aún no evaluó tus oportunidades. Revisa las 5 más relevantes en unos segundos:")
    if comun.hay_ia() and st.button("Evaluar mis 5 mejores coincidencias", type="primary"):
        with st.spinner("La IA está leyendo las convocatorias…"):
            comun.evaluar_varias(para_mi.head(5).to_dict("records"))
        st.rerun()
else:
    top = evaluadas.assign(p=evaluadas["ocid"].map(lambda o: ev[o]["puntaje"])).sort_values("p", ascending=False)
    for c in comun.enriquecer(top, p).head(3).to_dict("records"):
        comun.tarjeta(c, clave="inicio_rec")

# ------------------------------------------------------------------ nuevas
st.subheader("🆕 Nuevas oportunidades compatibles")
st.caption("Las más recientes que coinciden con tu perfil, primero las de tu cobertura.")
nuevas = para_mi[~para_mi["ocid"].isin(ev)].head(5)
for c in nuevas.to_dict("records"):
    comun.tarjeta(c, clave="inicio_new")

# ------------------------------------------------------------------ guía
st.divider()
st.markdown("##### LicitaPYME responde 5 preguntas")
g = st.columns(5)
preguntas = [
    ("🔎", "¿Qué oportunidades existen para mi empresa?", "Buscar convocatorias"),
    ("🗺️", "¿Dónde están?", "Mapa de oportunidades"),
    ("🤖", "¿Qué tan compatible soy?", "Evaluación con IA (7 criterios)"),
    ("📄", "¿Qué necesito para postular?", "Requisitos leídos de las bases"),
    ("📊", "¿Cuál priorizo?", "Comparador + precios y competencia"),
]
for col, (ic, q, dnd) in zip(g, preguntas):
    col.markdown(f"**{ic} {q}**  \n<small>{dnd}</small>", unsafe_allow_html=True)
