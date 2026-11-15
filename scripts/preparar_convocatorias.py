"""Convierte el archivo OCDS crudo (data/raw/<anio>.jsonl.gz) en dos tablas
livianas que usa la app:

- data/convocatorias.parquet  : un proceso por fila (lo que una PYME necesita para decidir)
- data/adjudicaciones.parquet : un ítem adjudicado por fila (quién ganó, qué y por cuánto)

Ubicación: OCDS solo trae la dirección de la ENTIDAD COMPRADORA (departamento y
distrito), no el lugar de ejecución ni coordenadas. Cruzamos con la tabla de
ubigeos (data/geo/, licencia MIT) y asignamos coordenadas de distrito SOLO si el
nombre del distrito es único dentro del departamento. Si no, la ubicación queda
a nivel de departamento. Nunca inventamos coordenadas.

Uso:
    python scripts/preparar_convocatorias.py                 # año actual, desde 2026-08
    python scripts/preparar_convocatorias.py --desde 2026-09
"""

import argparse
import gzip
import json
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
GEO_DIR = ROOT / "data" / "geo"
SALIDA_CONV = ROOT / "data" / "convocatorias.parquet"
SALIDA_ADJ = ROOT / "data" / "adjudicaciones.parquet"

CATEGORIAS = {"goods": "Bienes", "services": "Servicios", "works": "Obras"}


def norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.upper().strip())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).split())


# ---------------------------------------------------------------- geografía
def cargar_geo():
    dist = pd.read_csv(GEO_DIR / "ubigeo_distrito.csv", dtype={"inei": str}, encoding="utf-8")
    dep = pd.read_csv(GEO_DIR / "ubigeo_departamento.csv", dtype={"inei": str}, encoding="utf-8")
    dist["k_dep"], dist["k_dis"] = dist["departamento"].map(norm), dist["distrito"].map(norm)
    # Solo los distritos cuyo nombre es único dentro de su departamento son ubicables sin ambigüedad.
    conteo = dist.groupby(["k_dep", "k_dis"])["inei"].transform("count")
    unicos = dist[conteo == 1].set_index(["k_dep", "k_dis"])
    deps = {norm(r.departamento): (r.latitude, r.longitude) for r in dep.itertuples()}
    return unicos, deps


def ubicar(departamento, localidad, unicos, deps) -> dict:
    kd, kl = norm(departamento), norm(localidad)
    if (kd, kl) in unicos.index:
        r = unicos.loc[(kd, kl)]
        return {"provincia": r["provincia"], "distrito": r["distrito"], "ubigeo": r["inei"],
                "lat": r["latitude"], "lon": r["longitude"], "precision_geo": "distrito"}
    lat, lon = deps.get(kd, (None, None))
    return {"provincia": None, "distrito": None, "ubigeo": None, "lat": lat, "lon": lon,
            "precision_geo": "departamento" if lat is not None else "sin_ubicacion"}


# ---------------------------------------------------------------- aplanado
def _comprador(release: dict) -> tuple[str | None, str | None]:
    buyer_id = (release.get("buyer") or {}).get("id")
    for p in release.get("parties", []):
        if p.get("id") == buyer_id or "buyer" in p.get("roles", []):
            addr = p.get("address") or {}
            return addr.get("department") or addr.get("region"), addr.get("locality")
    return None, None


def _fecha(periodo: dict | None, clave: str) -> str | None:
    return (periodo or {}).get(clave)


def aplanar_convocatoria(release: dict) -> dict:
    t = release.get("tender") or {}
    items = t.get("items") or []
    estados = [i.get("statusDetails") for i in items if i.get("statusDetails")]
    rubros = sorted({(i.get("classification") or {}).get("description") for i in items} - {None})
    unspsc = sorted(
        {
            c.get("description")
            for i in items
            for c in i.get("additionalClassifications") or []
            if c.get("scheme") == "UNSPSC" and c.get("description")
        }
    )
    bases = next(
        (d.get("url") for d in t.get("documents") or [] if d.get("documentType") == "biddingDocuments"),
        None,
    )
    departamento, localidad = _comprador(release)
    valor = t.get("value") or {}
    return {
        "ocid": release.get("ocid"),
        "nomenclatura": t.get("title"),
        "descripcion": t.get("description"),
        "entidad": (release.get("buyer") or {}).get("name"),
        "departamento": departamento,
        "localidad": localidad,
        "metodo": t.get("procurementMethodDetails"),
        "categoria": CATEGORIAS.get(t.get("mainProcurementCategory"), t.get("mainProcurementCategory")),
        # 0 en OCDS significa "no publicado" (valor reservado), no "gratis".
        "monto_soles": valor.get("amount_PEN", valor.get("amount")) or None,
        "fecha_publicacion": t.get("datePublished"),
        "consultas_fin": _fecha(t.get("enquiryPeriod"), "endDate"),
        "ofertas_inicio": _fecha(t.get("tenderPeriod"), "startDate"),
        "ofertas_fin": _fecha(t.get("tenderPeriod"), "endDate"),
        "estado": max(set(estados), key=estados.count) if estados else None,
        "n_items": len(items),
        "rubros_cubso": " | ".join(rubros),
        "rubros_unspsc": " | ".join(unspsc),
        "n_postores": t.get("numberOfTenderers"),
        "url_bases": bases,
        "mes": (release.get("dataSegmentation") or {}).get("id"),
    }


def aplanar_adjudicaciones(release: dict) -> list[dict]:
    """Un registro por ítem adjudicado, solo en soles y con monto > 0."""
    t = release.get("tender") or {}
    departamento, localidad = _comprador(release)
    filas = []
    for a in release.get("awards") or []:
        sup = a.get("suppliers") or []
        rucs = [(s.get("id") or "").replace("PE-RUC-", "") for s in sup]
        nombres = [s.get("name") for s in sup]
        for it in a.get("items") or []:
            v = it.get("totalValue") or {}
            if v.get("currency") != "PEN" or not v.get("amount"):
                continue
            clas = it.get("classification") or {}
            filas.append({
                "ocid": release.get("ocid"),
                "fecha": a.get("date"),
                "entidad": (release.get("buyer") or {}).get("name"),
                "departamento": departamento,
                "localidad": localidad,
                "categoria": CATEGORIAS.get(t.get("mainProcurementCategory"), t.get("mainProcurementCategory")),
                "metodo": t.get("procurementMethodDetails"),
                "item": it.get("description"),
                "cubso_id": clas.get("id"),
                "cubso": clas.get("description"),
                "cantidad": it.get("quantity"),
                "unidad": (it.get("unit") or {}).get("name"),
                "monto_item": v["amount"],
                "ruc_proveedor": " | ".join(rucs),
                "proveedor": " | ".join(n for n in nombres if n),
                "n_postores": t.get("numberOfTenderers"),
            })
    return filas


# ---------------------------------------------------------------- main
def preparar(anio: int, desde: str):
    origen = RAW_DIR / f"{anio}.jsonl.gz"
    conv, adj = [], []
    with gzip.open(origen, "rt", encoding="utf-8") as f:
        for linea in f:
            release = json.loads(linea)
            adj.extend(aplanar_adjudicaciones(release))
            mes = (release.get("dataSegmentation") or {}).get("id") or ""
            if mes >= desde:
                conv.append(aplanar_convocatoria(release))

    unicos, deps = cargar_geo()

    df = pd.DataFrame(conv)
    geo = pd.DataFrame([ubicar(d, l, unicos, deps) for d, l in zip(df["departamento"], df["localidad"])])
    df = pd.concat([df, geo], axis=1)
    for col in ["fecha_publicacion", "consultas_fin", "ofertas_inicio", "ofertas_fin"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_convert("America/Lima").dt.tz_localize(None)
    df["monto_soles"] = pd.to_numeric(df["monto_soles"], errors="coerce")
    df = df.drop_duplicates("ocid").sort_values("fecha_publicacion", ascending=False).reset_index(drop=True)

    da = pd.DataFrame(adj)
    geo_a = pd.DataFrame([ubicar(d, l, unicos, deps) for d, l in zip(da["departamento"], da["localidad"])])
    da = pd.concat([da, geo_a[["provincia", "distrito", "precision_geo"]]], axis=1)
    da["fecha"] = pd.to_datetime(da["fecha"], errors="coerce", utc=True).dt.tz_convert("America/Lima").dt.tz_localize(None)
    # Solo adjudicaciones recientes: precios de hace 10 años no sirven como referencia.
    da = da[da["fecha"] >= "2024-01-01"].reset_index(drop=True)
    da["precio_unitario"] = da["monto_item"] / da["cantidad"].where(da["cantidad"] > 0)
    da = da.drop_duplicates(["ocid", "fecha", "item", "ruc_proveedor", "monto_item"]).reset_index(drop=True)
    return df, da


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--anio", type=int, default=date.today().year)
    p.add_argument("--desde", default="2026-08", help="mes mínimo AAAA-MM para convocatorias")
    args = p.parse_args()

    conv, adj = preparar(args.anio, args.desde)
    conv.to_parquet(SALIDA_CONV, index=False)
    adj.to_parquet(SALIDA_ADJ, index=False)
    print(f"{len(conv):,} convocatorias -> {SALIDA_CONV.name} ({SALIDA_CONV.stat().st_size / 1e6:.1f} MB)")
    print(conv["precision_geo"].value_counts().to_string())
    print(f"{len(adj):,} ítems adjudicados -> {SALIDA_ADJ.name} ({SALIDA_ADJ.stat().st_size / 1e6:.1f} MB)")
    print(f"periodo adjudicaciones: {adj['fecha'].min():%d/%m/%Y} - {adj['fecha'].max():%d/%m/%Y}")
