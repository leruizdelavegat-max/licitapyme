"""Descarga los datos abiertos de contrataciones del SEACE (formato OCDS).

Fuente: registro de datos de Open Contracting Partnership, que publica
los datos del OECE (antes OSCE). Se actualiza mensualmente.
https://data.open-contracting.org/es/publication/135

Uso:
    python scripts/descargar_datos.py          # año actual
    python scripts/descargar_datos.py 2025     # otro año
"""

import sys
import urllib.request
from datetime import date
from pathlib import Path

URL = "https://data.open-contracting.org/es/publication/135/download?name={anio}.jsonl.gz"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def descargar(anio: int) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    destino = RAW_DIR / f"{anio}.jsonl.gz"
    print(f"Descargando {anio}.jsonl.gz -> {destino} ...")

    def progreso(bloques, tam_bloque, total):
        if total > 0:
            pct = min(100, bloques * tam_bloque * 100 // total)
            print(f"\r  {pct}%", end="", flush=True)

    urllib.request.urlretrieve(URL.format(anio=anio), destino, progreso)
    print(f"\nListo: {destino.stat().st_size / 1e6:.0f} MB")
    return destino


if __name__ == "__main__":
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    descargar(anio)
