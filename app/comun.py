"""Piezas compartidas por todas las páginas: datos, perfil, filtros, tarjetas.

Todo lo que se repite entre páginas vive aquí para no duplicar código.
"""

from __future__ import annotations

import math
import os
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DATA_CONV = RAIZ / "data" / "convocatorias.parquet"
DATA_ADJ = RAIZ / "data" / "adjudicaciones.parquet"
DATA_UBIGEO = RAIZ / "data" / "geo" / "ubigeo_distrito.csv"

# 24 departamentos + Provincia Constitucional del Callao (nombres como vienen en el SEACE)
DEPARTAMENTOS = [
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA", "CALLAO", "CUSCO",
    "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO",
    "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI",
]
TIPOS = ["Bienes", "Servicios", "Obras"]

ESTADOS_SEGUIMIENTO = [
    "Guardada", "Pendiente de evaluación", "En evaluación", "Preparando postulación",
    "Postulada", "Adjudicada", "No adjudicada", "Descartada",
]

SEMAFORO = {
    "verde": {"icono": "🟢", "color": "#2fb344", "texto": "Alta compatibilidad"},
    "amarillo": {"icono": "🟡", "color": "#f59f00", "texto": "Revisar condiciones"},
    "rojo": {"icono": "🔴", "color": "#d63939", "texto": "No cumple un requisito clave"},
    "gris": {"icono": "⚪", "color": "#868e96", "texto": "Sin evaluar"},
}

# ------------------------------------------------------------------ clave de IA
load_dotenv(RAIZ / ".env")
try:  # en Streamlit Cloud la clave va en "Secrets"
    if "DEEPSEEK_API_KEY" in st.secrets:
        os.environ["DEEPSEEK_API_KEY"] = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    pass


def hay_ia() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


# ------------------------------------------------------------------ utilidades
def normalizar(s) -> str:
    """Mayúsculas y sin tildes, para que 'útiles' encuentre 'UTILES'."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.upper())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).split())


def soles(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)) or x == 0:
        return "No publicado"
    if x >= 1e6:
        return f"S/ {x / 1e6:,.2f} M"
    return f"S/ {x:,.0f}"


def fecha(x) -> str:
    return "No disponible" if x is None or pd.isna(x) else f"{x:%d/%m/%Y}"


def distancia_km(lat1, lon1, lat2, lon2) -> float | None:
    """Distancia en línea recta (haversine). Orientativa: no es distancia por carretera."""
    if any(v is None or pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ------------------------------------------------------------------ datos
@st.cache_data(show_spinner="Cargando convocatorias…")
def cargar_convocatorias() -> pd.DataFrame:
    df = pd.read_parquet(DATA_CONV)
    df["texto_desc"] = df["descripcion"].map(normalizar)
    df["texto_rubro"] = (df["rubros_cubso"].fillna("") + " " + df["rubros_unspsc"].fillna("")).map(normalizar)
    return df


@st.cache_data(show_spinner="Cargando adjudicaciones…")
def cargar_adjudicaciones() -> pd.DataFrame:
    df = pd.read_parquet(DATA_ADJ)
    df["texto"] = (df["cubso"].fillna("") + " " + df["item"].fillna("")).map(normalizar)
    return df


@st.cache_data
def cargar_distritos() -> pd.DataFrame:
    d = pd.read_csv(DATA_UBIGEO, dtype={"inei": str}, encoding="utf-8")
    d["etiqueta"] = d["distrito"] + " — " + d["provincia"] + ", " + d["departamento"]
    return d[["inei", "departamento", "provincia", "distrito", "latitude", "longitude", "etiqueta"]]


def fecha_corte() -> datetime:
    return cargar_convocatorias()["fecha_publicacion"].max()


def fecha_referencia() -> datetime:
    """Fecha contra la que se calculan los plazos (corte de datos o hoy)."""
    if st.session_state.get("usar_hoy"):
        return datetime.now()
    return fecha_corte()


# ------------------------------------------------------------------ perfil
PERFIL_DEMO = {
    "nombre": "Limpieza Integral Lima S.A.C. (empresa de ejemplo)",
    "ruc": "",
    "actividad": "Limpieza general de edificios y oficinas (CIIU 8121)",
    "productos": "Servicio de limpieza de oficinas, locales administrativos y áreas comunes; "
    "desinfección; limpieza de vidrios; suministro de personal de limpieza.",
    "palabras_clave": ["servicio de limpieza", "limpieza de oficinas", "limpieza de ambientes"],
    "domicilio_ubigeo": "150113",  # Jesús María, Lima
    "cobertura": ["LIMA", "CALLAO"],
    "tipos": ["Servicios"],
    "monto_max": 1_500_000,
    "facturacion_anual": 1_200_000,
    "experiencia": "4 años de experiencia con clientes privados (oficinas y centros comerciales). "
    "Facturación acumulada en limpieza de aprox. S/ 3.5 millones. Aún no hemos contratado con el Estado.",
    "capacidad": "30 trabajadores en planilla, supervisores por turno, equipos de limpieza industrial propios.",
    "rnp": "Sí, vigente",
}


def perfil() -> dict:
    if "perfil" not in st.session_state:
        st.session_state["perfil"] = dict(PERFIL_DEMO)
    return st.session_state["perfil"]


def domicilio_coords(p: dict) -> tuple[float | None, float | None, str | None]:
    if not p.get("domicilio_ubigeo"):
        return None, None, None
    d = cargar_distritos()
    fila = d[d["inei"] == p["domicilio_ubigeo"]]
    if fila.empty:
        return None, None, None
    r = fila.iloc[0]
    return r["latitude"], r["longitude"], r["etiqueta"]


def texto_perfil(p: dict) -> str:
    """El perfil en texto, tal como lo lee la IA."""
    _, _, dom = domicilio_coords(p)
    return (
        f"Empresa: {p['nombre']}\n"
        f"Actividad económica: {p['actividad']}\n"
        f"Bienes y servicios que ofrece: {p['productos']}\n"
        f"Domicilio fiscal: {dom or 'no indicado'}\n"
        f"Departamentos donde PUEDE atender (cobertura, no es su domicilio): {', '.join(p['cobertura']) or 'no indicado'}\n"
        f"Tipo de contratación: {', '.join(p['tipos'])}\n"
        f"Monto máximo que puede atender por contrato: {soles(p['monto_max'])}\n"
        f"Facturación anual aproximada: {soles(p['facturacion_anual'])}\n"
        f"Experiencia: {p['experiencia']}\n"
        f"Capacidad operativa: {p['capacidad']}\n"
        f"Inscripción en el RNP (Registro Nacional de Proveedores): {p['rnp']}"
    )


# ------------------------------------------------------------------ búsqueda
def selector_palabras(contenedor, clave_widget: str) -> list[str]:
    """Campo "¿Qué buscas?" compartido: Buscar y Mapa usan las mismas palabras.

    Arranca con las palabras del perfil y recuerda lo que la persona escriba
    (en `palabras_busqueda`), aunque cambie de sección.
    """
    p = perfil()
    actuales = st.session_state.setdefault("palabras_busqueda", list(p["palabras_clave"]))
    opciones = sorted(set(p["palabras_clave"]) | set(actuales))
    palabras = contenedor.multiselect(
        "¿Qué buscas? 🔍",
        options=opciones,
        default=actuales,
        accept_new_options=True,
        key=clave_widget,
        placeholder="Escribe una palabra y presiona Enter",
        help="Empieza con las palabras de tu perfil. Escribe otra y presiona Enter para agregarla. "
        "Se mantiene igual en Buscar y en el Mapa.",
    )
    st.session_state["palabras_busqueda"] = palabras
    return palabras


def puntuar_palabras(df: pd.DataFrame, claves: list[str]) -> pd.Series:
    """Coincidir en el rubro oficial (CUBSO/UNSPSC) pesa el doble que en la descripción."""
    claves = [normalizar(c) for c in claves if c and c.strip()]
    if not claves:
        return pd.Series(0, index=df.index)
    return sum(
        2 * df["texto_rubro"].str.contains(c, regex=False) + df["texto_desc"].str.contains(c, regex=False)
        for c in claves
    )


def enriquecer(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Agrega coincidencia, cobertura, distancia, plazo y semáforo (si ya fue evaluada)."""
    df = df.copy()
    df["coincidencia"] = puntuar_palabras(df, p["palabras_clave"])
    df["en_cobertura"] = df["departamento"].isin(p["cobertura"]) if p["cobertura"] else True
    lat0, lon0, _ = domicilio_coords(p)
    confiable = df["precision_geo"] == "distrito"
    df["distancia_km"] = [
        distancia_km(lat0, lon0, la, lo) if ok else None
        for la, lo, ok in zip(df["lat"], df["lon"], confiable)
    ]
    ref = fecha_referencia()
    df["dias_consultas"] = (df["consultas_fin"] - ref).dt.days
    ev = evaluaciones()
    df["semaforo"] = df["ocid"].map(lambda o: ev[o]["semaforo"] if o in ev else "gris")
    df["compatibilidad"] = df["ocid"].map(lambda o: ev[o]["puntaje"] if o in ev else None)
    return df


# ------------------------------------------------------------------ estado de la sesión
def evaluaciones() -> dict:
    return st.session_state.setdefault("evaluaciones", {})


def guardadas() -> dict:
    return st.session_state.setdefault("guardadas", {})


def guardar(ocid: str):
    g = guardadas()
    if ocid not in g:
        g[ocid] = {"estado": "Guardada", "nota": "", "guardada_el": datetime.now().strftime("%d/%m/%Y %H:%M")}


# ------------------------------------------------------------------ evaluación con IA
def _evaluar_puro(conv: dict, p: dict, texto: str, requisitos: list | None) -> dict | None:
    """Solo la llamada a la IA: no toca st.session_state, así puede correr en hilos."""
    from ai.compatibilidad import evaluar as evaluar_ia

    try:
        return evaluar_ia(conv, p, texto, requisitos=requisitos)
    except Exception as e:  # red, cuota, clave… no debe tumbar la app
        print(f"[IA] fallo en {conv.get('ocid')}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def evaluar(conv: dict, requisitos: list | None = None) -> dict | None:
    """Evalúa una convocatoria con la metodología de compatibilidad y guarda el resultado."""
    p = perfil()
    r = _evaluar_puro(conv, p, texto_perfil(p), requisitos)
    if r is not None:
        evaluaciones()[conv["ocid"]] = r
    return r


def evaluar_varias(filas: list[dict]) -> int:
    """Evalúa en paralelo. El estado de la sesión se lee y escribe solo en el hilo principal."""
    from concurrent.futures import ThreadPoolExecutor

    p = perfil()
    texto = texto_perfil(p)
    ev = evaluaciones()
    pendientes = [f for f in filas if f["ocid"] not in ev]
    with ThreadPoolExecutor(max_workers=6) as ex:
        resultados = list(ex.map(lambda c: _evaluar_puro(c, p, texto, None), pendientes))
    for c, r in zip(pendientes, resultados):
        if r is not None:
            ev[c["ocid"]] = r
    return sum(r is not None for r in resultados)


# ------------------------------------------------------------------ componentes visuales
def ubicacion_txt(c: dict) -> str:
    if c.get("precision_geo") == "distrito":
        return f"{str(c['distrito']).title()}, {str(c['provincia']).title()} ({str(c['departamento']).title()})"
    return f"{str(c.get('departamento') or 'Sin dato').title()} (solo se conoce el departamento)"


def plazo_txt(c: dict) -> str:
    d = c.get("dias_consultas")
    if d is None or pd.isna(d):
        return "Cronograma no disponible en datos abiertos"
    if d < 0:
        return f"Consultas cerraron el {fecha(c['consultas_fin'])}"
    return f"Consultas hasta el {fecha(c['consultas_fin'])} ({int(d)} días)"


def tarjeta(c: dict, clave: str, mostrar_evaluacion: bool = True):
    """Tarjeta de una convocatoria con acciones. `clave` evita choques de widgets entre páginas."""
    ev = evaluaciones().get(c["ocid"])
    sem = SEMAFORO[ev["semaforo"]] if ev else SEMAFORO["gris"]
    with st.container(border=True):
        cab, acc = st.columns([5, 2])
        with cab:
            titulo = f"{sem['icono']} **{c['entidad']}**"
            if ev:
                titulo += f" · **{ev['puntaje']} % compatible**"
            st.markdown(titulo)
            st.markdown(f"{c['descripcion']}")
            chips = [
                f"📍 {ubicacion_txt(c)}",
                f"💰 {soles(c['monto_soles'])}",
                f"🗂️ {c['categoria']} · {c['metodo']}",
                f"📅 Publicado {fecha(c['fecha_publicacion'])}",
                f"⏳ {plazo_txt(c)}",
            ]
            if c.get("distancia_km") is not None and not pd.isna(c.get("distancia_km")):
                chips.append(f"🚚 ~{c['distancia_km']:,.0f} km de tu domicilio (línea recta)")
            if not c.get("en_cobertura", True):
                chips.append("⚠️ Fuera de tu cobertura declarada")
            st.caption("  ·  ".join(chips))
        with acc:
            if c["ocid"] in guardadas():
                st.button("⭐ Guardada", key=f"g_{clave}_{c['ocid']}", disabled=True, width="stretch")
            elif st.button("☆ Guardar", key=f"g_{clave}_{c['ocid']}", width="stretch"):
                guardar(c["ocid"])
                st.rerun()
            if hay_ia() and not ev and st.button("🤖 Evaluar con IA", key=f"e_{clave}_{c['ocid']}", width="stretch"):
                with st.spinner("La IA está evaluando…"):
                    if evaluar(c) is None:
                        st.error("No se pudo evaluar. Intenta de nuevo.")
                st.rerun()
            if c.get("url_bases"):
                st.link_button("📄 Bases (SEACE)", c["url_bases"], width="stretch")
        if ev and mostrar_evaluacion:
            with st.expander(f"Ver evaluación · {sem['texto']} · confianza {ev['confianza']} %"):
                mostrar_evaluacion_detalle(ev)


def mostrar_evaluacion_detalle(ev: dict):
    from ai.compatibilidad import CRITERIOS, ETIQUETA_ESTADO

    st.markdown(f"**¿Vale la pena evaluarla?** {ev['vale_la_pena']}")
    st.markdown(f"**Qué compran:** {ev['resumen']}")
    st.markdown(f"**Por qué:** {ev['por_que']}")
    c1, c2 = st.columns(2)
    c1.markdown("**Ventajas**\n" + "\n".join(f"- {x}" for x in ev["ventajas"]) if ev["ventajas"] else "**Ventajas**\n- —")
    c2.markdown("**Dificultades**\n" + "\n".join(f"- {x}" for x in ev["dificultades"]) if ev["dificultades"] else "**Dificultades**\n- —")
    st.markdown("**Revisa con atención en las bases:**\n" + "\n".join(f"- {x}" for x in ev["revisar"]))
    st.markdown("**Cómo se calculó el puntaje**")
    filas = [
        {
            "Criterio": CRITERIOS[k]["nombre"],
            "Peso": f"{CRITERIOS[k]['peso']} %",
            "Resultado": ETIQUETA_ESTADO[v["estado"]],
            "Evidencia": v["evidencia"],
            "Evaluado por": "Regla fija" if CRITERIOS[k]["fuente"] == "regla" else "IA",
        }
        for k, v in ev["criterios"].items()
    ]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption(
        f"Puntaje = suma de (peso × resultado) ÷ pesos con información. Cumple = 1 · Debe acreditar = 0.6 · "
        f"No cumple = 0 · Sin información = no cuenta. Confianza = % del peso total con información "
        f"({ev['confianza']} %). Metodología completa en docs/metodologia.md."
    )
