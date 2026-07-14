"""Descarga y cachea el dataset de sueldos (Kaggle, sofifa/EA FC 25, snapshot
2025-06-03): https://www.kaggle.com/datasets/aniss7/fifa-player-data-from-sofifa-2025-06-03

Trae valor de mercado Y sueldo semanal reales para ~18k jugadores de las
principales ligas europeas (hasta 3a/4a division en varios paises), lo que
permite calibrar directamente la relacion sueldo/valor sin depender de
datasets cruzados.

Idempotencia: si ya existe una copia en cache (data_raw/wages_raw.csv) y no
se pide --refresh, no se vuelve a golpear la red/API. Si Kaggle no responde,
las credenciales no estan configuradas o el paquete no esta instalado, se
usa la cache existente con un aviso; si no hay cache ni acceso, se aborta
con un error explicito en vez de generar un pipeline a medias.
"""
import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

DATASET_REF = "aniss7/fifa-player-data-from-sofifa-2025-06-03"
DATASET_FILE = "player-data-full-2025-june.csv"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data_raw" / "wages_raw.csv"
NEEDED_COLUMNS = ["name", "dob", "positions", "value", "wage", "club_name", "club_league_name"]


def _download_from_kaggle(dest_dir: Path) -> pd.DataFrame:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET_REF, path=str(dest_dir), unzip=True)
    raw = pd.read_csv(dest_dir / DATASET_FILE, low_memory=False)
    missing = set(NEEDED_COLUMNS) - set(raw.columns)
    if missing:
        raise RuntimeError(f"La fuente cambio de formato: faltan columnas {missing}")
    return raw[NEEDED_COLUMNS]


def fetch(refresh: bool = False, cache_path: Path = CACHE_PATH) -> Path:
    if cache_path.exists() and not refresh:
        return cache_path

    try:
        with tempfile.TemporaryDirectory() as tmp:
            slim = _download_from_kaggle(Path(tmp))
    except Exception as exc:  # credenciales, paquete no instalado, red, formato...
        if cache_path.exists():
            print(f"[fetch_wages] fuente Kaggle no disponible ({exc}), uso cache existente", file=sys.stderr)
            return cache_path
        raise RuntimeError(
            "No se pudo descargar el dataset de sueldos de Kaggle y no hay cache local. "
            "Configura las credenciales de Kaggle (~/.kaggle/kaggle.json o KAGGLE_API_TOKEN) "
            f"o coloca manualmente un CSV en {cache_path}. Detalle: {exc}"
        ) from exc

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    slim.to_csv(cache_path, index=False)
    return cache_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="fuerza re-descarga ignorando cache")
    args = parser.parse_args()
    path = fetch(refresh=args.refresh)
    print(f"wages_raw listo en {path}")
