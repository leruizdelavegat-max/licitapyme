"""Piezas compartidas por todas las páginas: datos, perfil de la empresa activa,
estado persistente (guardadas, evaluaciones, preferencias), búsqueda y tarjetas.

El estado ya no vive en la sesión: se lee y escribe en la base de datos (db.py),
siempre con el id de la empresa activa (sesion.py).
"""

from __future__ import annotations

import math
import os
import re
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

import db  # noqa: E402
import sesion  # noqa: E402
import ui  # noqa: E402

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
RNP_OPCIONES = ["Sí, vigente", "En trámite", "No", "No sé"]

ESTADOS_SEGUIMIENTO = [
    "Guardada", "Pendiente de evaluación", "En evaluación", "Preparando postulación",
    "Postulada", "Adjudicada", "No adjudicada", "Descartada",
]

SEMAFORO = {k: {"color": v["color"], "texto": v["etiqueta"]} for k, v in ui.ESTADOS.items()}

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


@st.cache_data
def catalogo_cubso() -> pd.DataFrame:
    """Categorías CUBSO reales con cuántas convocatorias abiertas y adjudicaciones tienen."""
    conv = cargar_convocatorias()
    abiertas = conv[conv["estado"] == "CONVOCADO"]["rubros_cubso"].dropna().str.split(" | ", regex=False).explode()
    adj = cargar_adjudicaciones()["cubso"].dropna()
    cat = pd.DataFrame({"abiertas": abiertas.value_counts(), "adjudicadas": adj.value_counts()}).fillna(0).astype(int)
    cat.index.name = "cubso"
    cat = cat.reset_index()
    cat["norm"] = cat["cubso"].map(normalizar)
    return cat


def fecha_corte() -> datetime:
    return cargar_convocatorias()["fecha_publicacion"].max()


def fecha_referencia() -> datetime:
    """Fecha contra la que se calculan los plazos (corte de datos o hoy)."""
    if st.session_state.get("usar_hoy"):
        return datetime.now()
    return fecha_corte()


# ------------------------------------------------------------------ perfil de la empresa activa
PERFIL_VACIO = {
    "nombre": "", "ruc": "", "actividad": "", "productos": "", "servicios": "", "palabras_clave": [], "categorias": [],
    "domicilio_ubigeo": None, "cobertura": [], "tipos": [], "monto_max": 0, "facturacion_anual": 0,
    "experiencia": "", "capacidad": "", "rnp": "No sé",
}

PERFIL_DEMO = {
    "nombre": "Limpieza Integral Lima S.A.C. (empresa de ejemplo)",
    "ruc": "",
    "actividad": "Limpieza general de edificios y oficinas (CIIU 8121)",
    "productos": "",
    "servicios": "Servicio de limpieza de oficinas, locales administrativos y áreas comunes; "
    "desinfección; limpieza de vidrios; suministro de personal de limpieza.",
    "palabras_clave": ["servicio de limpieza", "limpieza de oficinas", "limpieza de ambientes"],
    "categorias": ["SERVICIO DE LIMPIEZA DE AREAS ADMINISTRATIVAS U OFICINAS."],
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


def empresa() -> dict | None:
    return sesion.empresa_actual()


def empresa_id() -> int:
    return empresa()["id"]


def perfil() -> dict:
    emp = empresa()
    datos = {**PERFIL_VACIO, **(emp["datos"] if emp else {})}
    # Compatibilidad con perfiles antiguos que tenían un solo campo "productos".
    datos.setdefault("servicios", "")
    return datos


def perfil_version() -> int:
    emp = empresa()
    return emp["version"] if emp else 0


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
        f"Productos que comercializa: {p.get('productos') or 'no indicó'}\n"
        f"Servicios que ofrece: {p.get('servicios') or 'no indicó'}\n"
        f"Domicilio fiscal: {dom or 'no indicado'}\n"
        f"Departamentos donde PUEDE atender (cobertura, no es su domicilio): {', '.join(p['cobertura']) or 'no indicado'}\n"
        f"Tipo de contratación: {', '.join(p['tipos']) or 'no indicado'}\n"
        f"Monto máximo que puede atender por contrato: {soles(p['monto_max'])}\n"
        f"Facturación anual aproximada: {soles(p['facturacion_anual'])}\n"
        f"Experiencia: {p['experiencia'] or 'no indicó'}\n"
        f"Capacidad operativa: {p['capacidad'] or 'no indicó'}\n"
        f"Inscripción en el RNP (Registro Nacional de Proveedores): {p['rnp']}"
    )


# ------------------------------------------------------------------ estado persistente de la empresa
def _cache() -> dict:
    return st.session_state.setdefault("_cache", {})


def evaluaciones(solo_vigentes: bool = False) -> dict:
    c = _cache()
    if "evaluaciones" not in c:
        c["evaluaciones"] = db.evaluaciones_de(empresa_id())
    if not solo_vigentes:
        return c["evaluaciones"]
    v = perfil_version()
    return {o: r for o, r in c["evaluaciones"].items() if r["version_perfil"] == v}


def guardadas() -> dict:
    c = _cache()
    if "guardadas" not in c:
        c["guardadas"] = db.guardadas_de(empresa_id())
    return c["guardadas"]


def requisitos() -> dict:
    c = _cache()
    if "requisitos" not in c:
        c["requisitos"] = db.requisitos_de(empresa_id())
    return c["requisitos"]


def preferencias() -> dict:
    c = _cache()
    if "preferencias" not in c:
        c["preferencias"] = db.preferencias_de(empresa_id())
    return c["preferencias"]


def guardar_preferencia(clave: str, valor):
    pref = dict(preferencias())
    if pref.get(clave) == valor:
        return
    pref[clave] = valor
    db.guardar_preferencias(empresa_id(), pref)
    _cache()["preferencias"] = pref


def invalidar(*claves: str):
    c = _cache()
    for k in claves:
        c.pop(k, None)


def guardar(ocid: str, entidad: str | None = None):
    db.guardar(empresa_id(), ocid, entidad)
    invalidar("guardadas")


# ------------------------------------------------------------------ búsqueda
def selector_palabras(contenedor, clave_widget: str) -> list[str]:
    """Campo "¿Qué buscas?" compartido: Buscar y Mapa usan las mismas palabras.

    Arranca con las palabras del perfil y recuerda lo que la persona escriba
    (en las preferencias de la empresa, en la base de datos).
    """
    p = perfil()
    actuales = preferencias().get("palabras_busqueda") or list(p["palabras_clave"])
    opciones = sorted(set(p["palabras_clave"]) | set(actuales))
    palabras = contenedor.multiselect(
        "Palabras clave",
        options=opciones,
        default=actuales,
        accept_new_options=True,
        key=clave_widget,
        placeholder="Escribe una palabra y presiona Enter",
        help="Empieza con las palabras de tu perfil. Escribe otra y presiona Enter para agregarla. "
        "Se mantiene igual en Buscar y en el Mapa, y se recuerda para tu próxima visita.",
    )
    guardar_preferencia("palabras_busqueda", palabras)
    return palabras


def contiene(serie: pd.Series, clave: str) -> pd.Series:
    """¿El texto contiene la palabra al INICIO de una palabra?

    Evita falsos positivos como "arroz" dentro de "carrozable", pero permite plurales:
    "computadora" encuentra "computadoras". `serie` y `clave` deben estar normalizadas.
    """
    return serie.str.contains(r"(?<![A-Z0-9])" + re.escape(clave), regex=True)


def puntuar_palabras(df: pd.DataFrame, claves: list[str]) -> pd.Series:
    """Coincidir en el rubro oficial (CUBSO/UNSPSC) pesa el doble que en la descripción."""
    claves = [normalizar(c) for c in claves if c and c.strip()]
    if not claves:
        return pd.Series(0, index=df.index)
    return sum(2 * contiene(df["texto_rubro"], c) + contiene(df["texto_desc"], c) for c in claves)


def enriquecer(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Agrega coincidencia, cobertura, distancia, plazo y semáforo (solo con evaluaciones vigentes)."""
    df = df.copy()
    # Palabras clave + categorías CUBSO confirmadas en el análisis del perfil.
    df["coincidencia"] = puntuar_palabras(df, list(p["palabras_clave"]) + list(p.get("categorias") or []))
    df["en_cobertura"] = df["departamento"].isin(p["cobertura"]) if p["cobertura"] else True
    lat0, lon0, _ = domicilio_coords(p)
    confiable = df["precision_geo"] == "distrito"
    df["distancia_km"] = [
        distancia_km(lat0, lon0, la, lo) if ok else None
        for la, lo, ok in zip(df["lat"], df["lon"], confiable)
    ]
    ref = fecha_referencia()
    df["dias_consultas"] = (df["consultas_fin"] - ref).dt.days
    ev = evaluaciones(solo_vigentes=True)
    df["semaforo"] = df["ocid"].map(lambda o: ev[o]["semaforo"] if o in ev else "gris")
    df["compatibilidad"] = df["ocid"].map(lambda o: ev[o]["puntaje"] if o in ev else None)
    # Orden de prioridad: compatibles primero, luego sin evaluar y al final las descartadas por la IA.
    df["prioridad"] = df["semaforo"].map(PRIORIDAD)
    return df


PRIORIDAD = {"verde": 0, "amarillo": 1, "gris": 2, "rojo": 3}


# ------------------------------------------------------------------ evaluación con IA
def _evaluar_puro(conv: dict, p: dict, texto: str, requisitos: list | None) -> dict | None:
    """Solo la llamada a la IA: no toca st.session_state ni la base, así puede correr en hilos."""
    from ai.compatibilidad import evaluar as evaluar_ia

    try:
        return evaluar_ia(conv, p, texto, requisitos=requisitos)
    except Exception as ex:  # red, cuota, clave… no debe tumbar la app
        print(f"[IA] fallo en {conv.get('ocid')}: {type(ex).__name__}: {ex}", file=sys.stderr)
        return None


def evaluar(conv: dict, requisitos: list | None = None) -> dict | None:
    """Evalúa una convocatoria con la metodología de compatibilidad y guarda el resultado."""
    p = perfil()
    r = _evaluar_puro(conv, p, texto_perfil(p), requisitos)
    if r is not None:
        db.guardar_evaluacion(empresa_id(), conv["ocid"], perfil_version(), r)
        invalidar("evaluaciones")
    return r


def evaluar_varias(filas: list[dict]) -> int:
    """Evalúa en paralelo. La sesión y la base se tocan solo en el hilo principal."""
    from concurrent.futures import ThreadPoolExecutor

    p = perfil()
    texto = texto_perfil(p)
    vigentes = evaluaciones(solo_vigentes=True)
    pendientes = [f for f in filas if f["ocid"] not in vigentes]
    with ThreadPoolExecutor(max_workers=6) as ex:
        resultados = list(ex.map(lambda c: _evaluar_puro(c, p, texto, None), pendientes))
    eid, v = empresa_id(), perfil_version()
    for c, r in zip(pendientes, resultados):
        if r is not None:
            db.guardar_evaluacion(eid, c["ocid"], v, r)
    invalidar("evaluaciones")
    return sum(r is not None for r in resultados)


# ------------------------------------------------------------------ componentes de convocatoria
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


def tarjeta(c: dict, clave: str, mostrar_evaluacion: bool = True, compacta: bool = False):
    """Tarjeta de una convocatoria con acciones. `clave` evita choques de widgets entre páginas."""
    todas = evaluaciones()
    ev = todas.get(c["ocid"])
    vigente = ev is not None and ev["version_perfil"] == perfil_version()
    with st.container(border=True):
        cab, acc = st.columns([5, 1.6], vertical_alignment="top")
        with cab:
            estado = ev["semaforo"] if vigente else "gris"
            texto = f"{ev['puntaje']} % · {ui.ESTADOS[estado]['etiqueta']}" if vigente else "Sin evaluar"
            cab.html(f'{ui.pastilla(estado, texto)}<div class="lp-titulo" style="margin-top:8px">{ui.e(c["entidad"])}</div>'
                     f'<div class="lp-desc">{ui.e(c["descripcion"])}</div>')
            items = [
                ("Ubicación", ubicacion_txt(c)),
                ("Valor ref.", soles(c["monto_soles"])),
                ("Tipo", f"{c['categoria']} · {c['metodo']}"),
                ("Publicado", fecha(c["fecha_publicacion"])),
                ("Plazo", plazo_txt(c)),
            ]
            if c.get("distancia_km") is not None and not pd.isna(c.get("distancia_km")):
                items.append(("Distancia", f"~{c['distancia_km']:,.0f} km (línea recta)"))
            cab.html(ui.meta(items))
            if not c.get("en_cobertura", True):
                cab.html('<div class="lp-aviso">Fuera de tu cobertura declarada</div>')
            if ev and not vigente:
                cab.html('<div class="lp-aviso">Hay una evaluación anterior a tu último cambio de perfil: vuelve a evaluarla.</div>')
        with acc:
            if c["ocid"] in guardadas():
                st.button("Guardada", key=f"g_{clave}_{c['ocid']}", disabled=True, icon=":material/bookmark_added:", width="stretch")
            elif st.button("Guardar", key=f"g_{clave}_{c['ocid']}", icon=":material/bookmark_add:", width="stretch"):
                guardar(c["ocid"], c.get("entidad"))
                st.rerun()
            if hay_ia() and not vigente and st.button("Evaluar con IA", key=f"e_{clave}_{c['ocid']}",
                                                      icon=":material/auto_awesome:", type="primary", width="stretch"):
                with st.spinner("La IA está evaluando…"):
                    if evaluar(c) is None:
                        st.error("No se pudo evaluar. Intenta de nuevo.")
                st.rerun()
            if c.get("url_bases"):
                st.link_button("Bases (SEACE)", c["url_bases"], icon=":material/description:", width="stretch")
        if vigente and mostrar_evaluacion and not compacta:
            with st.expander(f"Ver análisis completo · confianza {ev['confianza']} %", icon=":material/insights:"):
                mostrar_evaluacion_detalle(ev)


def mostrar_evaluacion_detalle(ev: dict):
    from ai.compatibilidad import CRITERIOS, ETIQUETA_ESTADO

    st.markdown(f"**¿Vale la pena evaluarla?** {ev['vale_la_pena']}")
    st.markdown(f"**Qué compran:** {ev['resumen']}")
    st.markdown(f"**Por qué:** {ev['por_que']}")
    c1, c2 = st.columns(2)
    c1.markdown("**Ventajas**\n" + ("\n".join(f"- {x}" for x in ev["ventajas"]) if ev["ventajas"] else "\n- —"))
    c2.markdown("**Dificultades**\n" + ("\n".join(f"- {x}" for x in ev["dificultades"]) if ev["dificultades"] else "\n- —"))
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
