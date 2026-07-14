"""Baremo: rango de sueldo esperado para un jugador por comparacion de mercado.

El dataset de sueldos (sofifa/Kaggle) trae valor Y sueldo real del mismo
jugador, asi que se puede calibrar directamente la relacion sueldo/valor:

1. Se construye un "peer group" de jugadores del dataset de sueldos con la
   misma posicion y tier de liga, y edad similar (ventana que se ensancha
   si hay pocos comparables).
2. Se calcula la distribucion de su ratio sueldo_anual / valor_mercado.
3. El sueldo esperado del jugador objetivo = su market_value (SoccerSolver)
   x esa distribucion de ratios -> percentiles 25/50/75 dan el rango y la
   mediana; el ratio, no el sueldo absoluto, es lo que se transporta entre
   datasets porque son poblaciones de jugadores distintas.

Si el tier del jugador no tiene comparables directos en la fuente (hoy,
tipicamente tiers 4-5: Regionalliga, Serie D, Segunda Federacion, Primavera),
se usa el ratio del tier real mas cercano como aproximacion. La confianza
nunca llega a "Alta" en ese caso, y baja a "Baja" si el salto de tier es
grande o hay pocos comparables (ver estimate_salary).
"""
from dataclasses import dataclass, field

import pandas as pd

from config import MAX_AGE_WINDOW, MIN_COMPARABLES


def _widen_until_enough(df: pd.DataFrame, age: int, min_n: int = MIN_COMPARABLES):
    for window in (4, 6, 8, 10, MAX_AGE_WINDOW):
        subset = df[(df["age"] >= age - window) & (df["age"] <= age + window)]
        if len(subset) >= min_n or window == MAX_AGE_WINDOW:
            return subset, window
    return df, MAX_AGE_WINDOW  


def _nearest_tier_with_data(wages_clean: pd.DataFrame, position: str, tier: int) -> int:
    available = sorted(wages_clean.loc[wages_clean["position"] == position, "tier"].unique())
    if not available:
        return tier
    higher_or_equal = [t for t in available if t <= tier]
    return max(higher_or_equal) if higher_or_equal else min(available)


@dataclass
class SalaryEstimate:
    low: float
    mid: float
    high: float
    confidence: str
    confidence_score: float
    n_comparables: int
    age_window: int
    tier_used: int
    tier_requested: int
    comparables: list = field(default_factory=list)


def estimate_salary(
    position: str,
    age: int,
    tier: int,
    market_value: float,
    wages_clean: pd.DataFrame,
    n_comparables_shown: int = 8,
) -> SalaryEstimate:
    tier_used = _nearest_tier_with_data(wages_clean, position, tier)
    pool = wages_clean[(wages_clean["position"] == position) & (wages_clean["tier"] == tier_used)]
    pool, age_window = _widen_until_enough(pool, age)

    if len(pool):
        ratio = pool["wage"] / pool["value"]
        low = float(market_value * ratio.quantile(0.25))
        mid = float(market_value * ratio.quantile(0.50))
        high = float(market_value * ratio.quantile(0.75))
    else:
        low = mid = high = float("nan")

    # Los tiers 3+ solo tienen dato real de sueldo para alguna liga concreta
    # (p.ej. League Two ingles) que se aplica como aproximacion a las demas
    # ligas del mismo tier en otros paises: nunca se marca como "Alta" aunque
    # la muestra sea grande, porque la aproximacion cross-pais es una fuente
    # de incertidumbre que el tamaño de muestra no refleja.
    n = len(pool)
    if tier_used == tier and tier <= 2 and n >= 15 and age_window <= 6:
        confidence, score = "Alta", 0.9
    elif n >= MIN_COMPARABLES and tier_used - tier <= 1:
        confidence, score = "Media", 0.6
    else:
        confidence, score = "Baja", 0.3

    pool_sorted = pool.assign(dist=(pool["age"] - age).abs()).sort_values("dist")
    comparables = pool_sorted.head(n_comparables_shown)[
        ["name", "club_name", "league", "age", "value", "wage"]
    ].to_dict("records")

    return SalaryEstimate(
        low=low, mid=mid, high=high,
        confidence=confidence, confidence_score=score,
        n_comparables=n, age_window=age_window,
        tier_used=tier_used, tier_requested=tier,
        comparables=comparables,
    )
