"""Convierte el archivo OCDS crudo (data/raw/<anio>.jsonl.gz) en una tabla
liviana de convocatorias (data/convocatorias.parquet) que usa la app.

Cada línea del archivo es un proceso de contratación (release compilado).
Nos quedamos solo con los campos que necesita una PYME para decidir si postula.

Uso:
    python scripts/preparar_convocatorias.py                 # año actual, desde 2026-08
    python scripts/preparar_convocatorias.py --desde 2026-09
"""

import argparse
import gzip
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SALIDA = ROOT / "data" / "convocatorias.parquet"

CATEGORIAS = {"goods": "Bienes", "services": "Servicios", "works": "Obras"}


def _region_comprador(release: dict) -> tuple[str | None, str | None]:
    """Departamento y localidad de la entidad que compra (está en 'parties')."""
    buyer_id = (release.get("buyer") or {}).get("id")
    for p in release.get("parties", []):
        if p.get("id") == buyer_id or "buyer" in p.get("roles", []):
            addr = p.get("address") or {}
            return addr.get("department") or addr.get("region"), addr.get("locality")
    return None, None


def _fecha(periodo: dict | None, clave: str) -> str | None:
    return (periodo or {}).get(clave)


def aplanar(release: dict) -> dict:
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
    departamento, localidad = _region_comprador(release)
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
        "monto_soles": valor.get("amount_PEN", valor.get("amount")),
        "fecha_publicacion": t.get("datePublished"),
        "consultas_fin": _fecha(t.get("enquiryPeriod"), "endDate"),
        "ofertas_inicio": _fecha(t.get("tenderPeriod"), "startDate"),
        "ofertas_fin": _fecha(t.get("tenderPeriod"), "endDate"),
        # Un proceso puede tener varios ítems; usamos el estado más frecuente.
        "estado": max(set(estados), key=estados.count) if estados else None,
        "n_items": len(items),
        "rubros_cubso": " | ".join(rubros),
        "rubros_unspsc": " | ".join(unspsc),
        "n_postores": t.get("numberOfTenderers"),
        "url_bases": bases,
        "mes": (release.get("dataSegmentation") or {}).get("id"),
    }


def preparar(anio: int, desde: str) -> pd.DataFrame:
    origen = RAW_DIR / f"{anio}.jsonl.gz"
    filas = []
    with gzip.open(origen, "rt", encoding="utf-8") as f:
        for linea in f:
            release = json.loads(linea)
            mes = (release.get("dataSegmentation") or {}).get("id") or ""
            if mes >= desde:
                filas.append(aplanar(release))

    df = pd.DataFrame(filas)
    for col in ["fecha_publicacion", "consultas_fin", "ofertas_inicio", "ofertas_fin"]:
        # Las fechas vienen en hora de Lima (-05:00); las dejamos sin zona horaria.
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_convert("America/Lima").dt.tz_localize(None)
    df["monto_soles"] = pd.to_numeric(df["monto_soles"], errors="coerce")
    df = df.drop_duplicates("ocid").sort_values("fecha_publicacion", ascending=False)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--anio", type=int, default=date.today().year)
    p.add_argument("--desde", default="2026-08", help="mes mínimo AAAA-MM")
    args = p.parse_args()

    df = preparar(args.anio, args.desde)
    df.to_parquet(SALIDA, index=False)
    print(f"{len(df):,} procesos guardados en {SALIDA} ({SALIDA.stat().st_size / 1e6:.1f} MB)")
    print(df["estado"].value_counts().head(8).to_string())
