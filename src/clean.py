"""Limpieza y validacion de los dos datasets de entrada.

Todas las funciones son puras (DataFrame -> DataFrame) para poder testearlas
sin tocar disco. Cada una devuelve tambien un dict de metricas de limpieza
(filas de entrada, descartadas por motivo, filas de salida) para dejar
trazabilidad de que se tiro y por que.
"""
from datetime import datetime

import numpy as np
import pandas as pd

from config import MAX_AGE, MAX_MARKET_VALUE, MAX_WAGE, MIN_AGE, MIN_MARKET_VALUE, MIN_WAGE
from tiers import competition_tier

POSITION_CODE_MAP = {
    "GK": "GK",
    "CB": "DEF", "RB": "DEF", "LB": "DEF", "RWB": "DEF", "LWB": "DEF", "SW": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "RM": "MID", "LM": "MID",
    "ST": "ATT", "CF": "ATT", "RW": "ATT", "LW": "ATT", "SS": "ATT",
}

REQUIRED_PLAYER_COLUMNS = {
    "player_id", "player_name", "position", "main_position", "birth_date",
    "team_name", "competition_name", "market_value",
}
REQUIRED_WAGE_COLUMNS = {"name", "dob", "positions", "value", "wage", "club_name", "club_league_name"}


def _validate_schema(df: pd.DataFrame, required: set, source_name: str) -> None:
    """Falla rapido y con un mensaje claro si la fuente cambio de formato,
    en vez de dejar que pandas lance un KeyError críptico mas adelante."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Formato inesperado en {source_name}: faltan columnas {sorted(missing)}")


def _parse_money(value: str) -> float:
    """Convierte '€440K' / '€115.5M' en euros (float). NaN si no parseable."""
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    text = "".join(ch for ch in text if ch.isdigit() or ch in ".KMkm")
    if not text:
        return np.nan
    multiplier = 1.0
    if text[-1] in "Kk":
        multiplier, text = 1_000.0, text[:-1]
    elif text[-1] in "Mm":
        multiplier, text = 1_000_000.0, text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return np.nan


def clean_players(df: pd.DataFrame, reference_date: datetime | None = None) -> tuple[pd.DataFrame, dict]:
    _validate_schema(df, REQUIRED_PLAYER_COLUMNS, "data.csv")
    reference_date = reference_date or datetime.utcnow()
    metrics = {"input_rows": len(df)}
    out = df.copy()

    out["market_value"] = pd.to_numeric(out["market_value"], errors="coerce")
    out["birth_date"] = pd.to_datetime(out["birth_date"], errors="coerce", utc=True)

    missing_required = out["market_value"].isna() | out["birth_date"].isna() | out["position"].isna()
    metrics["dropped_missing_required_fields"] = int(missing_required.sum())
    out = out[~missing_required].copy()

    out["age"] = ((reference_date - out["birth_date"].dt.tz_localize(None)).dt.days / 365.25).astype(int)

    out_of_range = (
        (out["age"] < MIN_AGE) | (out["age"] > MAX_AGE)
        | (out["market_value"] < MIN_MARKET_VALUE) | (out["market_value"] > MAX_MARKET_VALUE)
    )
    metrics["dropped_out_of_range"] = int(out_of_range.sum())
    out = out[~out_of_range].copy()

    dupes = out.duplicated(subset=["player_id"])
    metrics["dropped_duplicate_player_id"] = int(dupes.sum())
    out = out[~dupes].copy()

    out["tier"] = out["competition_name"].apply(competition_tier)

    keep_cols = [
        "player_id", "player_name", "position", "main_position", "age",
        "team_name", "competition_name", "tier", "market_value",
    ]
    out = out[keep_cols].reset_index(drop=True)
    metrics["output_rows"] = len(out)
    return out, metrics


def clean_wages(df: pd.DataFrame, reference_date: datetime | None = None) -> tuple[pd.DataFrame, dict]:
    """Limpia el dataset de sueldos (sofifa/Kaggle, snapshot 2025-06).

    El sueldo de la fuente es semanal (convencion sofifa/EA FC); se anualiza
    (x52) para poder compararlo con el market_value anual-equivalente.
    """
    _validate_schema(df, REQUIRED_WAGE_COLUMNS, "wages_raw.csv")
    reference_date = reference_date or datetime.utcnow()
    metrics = {"input_rows": len(df)}
    out = df.copy()

    out["value"] = out["value"].apply(_parse_money)
    out["wage"] = out["wage"].apply(_parse_money) * 52
    out["birth_date"] = pd.to_datetime(out["dob"], errors="coerce", utc=True)
    first_position = out["positions"].astype(str).str.split(",").str[0].str.strip()
    out["position"] = first_position.map(POSITION_CODE_MAP)

    missing_required = (
        out["wage"].isna() | out["value"].isna() | out["birth_date"].isna()
        | out["position"].isna() | out["club_league_name"].isna()
    )
    metrics["dropped_missing_required_fields"] = int(missing_required.sum())
    out = out[~missing_required].copy()

    out["age"] = ((reference_date - out["birth_date"].dt.tz_localize(None)).dt.days / 365.25).astype(int)

    out_of_range = (
        (out["age"] < MIN_AGE) | (out["age"] > MAX_AGE)
        | (out["wage"] < MIN_WAGE) | (out["wage"] > MAX_WAGE)
        | (out["value"] < MIN_MARKET_VALUE) | (out["value"] > MAX_MARKET_VALUE)
    )
    metrics["dropped_out_of_range"] = int(out_of_range.sum())
    out = out[~out_of_range].copy()

    out["tier"] = out["club_league_name"].apply(competition_tier)

    dupes = out.duplicated(subset=["name", "club_name", "age", "wage", "value"])
    metrics["dropped_duplicate_rows"] = int(dupes.sum())
    out = out[~dupes].copy()

    out = out.rename(columns={"club_league_name": "league"})
    keep_cols = ["name", "club_name", "league", "tier", "position", "age", "value", "wage"]
    out = out[keep_cols].reset_index(drop=True)
    metrics["output_rows"] = len(out)
    return out, metrics
