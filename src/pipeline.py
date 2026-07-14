"""Orquesta el pipeline completo: descarga sueldos, limpia ambos datasets y
escribe los CSV procesados en data/. Se puede re-ejecutar cuantas veces se
quiera: cada corrida sobreescribe los ficheros de salida de forma
deterministica (no hay append), asi que no se duplican datos.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean import clean_players, clean_wages
from fetch_wages import fetch as fetch_wages

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data_raw"
DATA_OUT = ROOT / "data"


def _write_clean_csv(clean_df: pd.DataFrame, metrics: dict, out_path: Path, label: str) -> None:
    if metrics["output_rows"] == 0:
        raise RuntimeError(
            f"La limpieza de {label} no dejo ninguna fila valida ({metrics}). "
            "Se aborta el pipeline en vez de sobreescribir la salida anterior con un CSV vacio."
        )
    clean_df.to_csv(out_path, index=False)
    print(f"{label}: {metrics}")


def run(refresh_wages: bool = False) -> None:
    DATA_OUT.mkdir(exist_ok=True)

    wages_raw_path = fetch_wages(refresh=refresh_wages)
    wages_raw = pd.read_csv(wages_raw_path)
    wages_clean, wages_metrics = clean_wages(wages_raw)
    _write_clean_csv(wages_clean, wages_metrics, DATA_OUT / "wages_clean.csv", "wages")

    players_path = DATA_RAW / "data.csv"
    if not players_path.exists():
        raise FileNotFoundError(
            f"No se encuentra {players_path}. Coloca el fichero de SoccerSolver ahi antes de ejecutar el pipeline."
        )
    players_raw = pd.read_csv(players_path)
    players_clean, players_metrics = clean_players(players_raw)
    _write_clean_csv(players_clean, players_metrics, DATA_OUT / "players_clean.csv", "players")


if __name__ == "__main__":
    try:
        run(refresh_wages="--refresh" in sys.argv)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"[pipeline] fallo: {exc}", file=sys.stderr)
        sys.exit(1)
