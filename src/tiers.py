"""Mapeo de competicion -> nivel competitivo (tier).

Solo tenemos sueldos reales (fetch_wages.py) de las 5 grandes ligas top
(Premier League, LaLiga, Serie A, Bundesliga, Ligue 1) = tier 1. Para el
resto de competiciones de data.csv (segundas divisiones, regionales,
filiales, juveniles) no existe sueldo publico real: se les asigna un tier
peor y el comparador escala la referencia de tier 1 con un factor derivado
del propio market_value (ver comparator.py). Es una estimacion, no un dato
observado; se documenta como limitacion en el README.
"""

# Cada set incluye tanto el nombre usado en data.csv (SoccerSolver) como el
# usado por el dataset de sueldos (sofifa/Kaggle), que difieren ligeramente
# ("LaLiga" vs "La Liga", "LaLiga2" vs "La Liga 2"...).
TIER_1 = {"Premier League", "LaLiga", "La Liga", "Serie A", "Bundesliga", "Ligue 1"}
TIER_2 = {"Championship", "LaLiga2", "La Liga 2", "Serie B", "2. Bundesliga", "Ligue 2"}
TIER_3 = {
    "League One", "3. Liga", "Ligue 3",
    "Primera Federación - Grupo I", "Primera Federación - Grupo II",
    "Serie C - Girone A", "Serie C - Girone B", "Serie C - Girone C",
}
TIER_4_PREFIXES = ("Regionalliga", "Serie D", "Segunda Federación")
TIER_4_EXTRA = {"League Two"}
TIER_5_PREFIXES = ("Primavera", "U19", "U18", "U17")


def competition_tier(competition_name: str) -> int:
    """Devuelve el tier (1=maximo nivel .. 5=juvenil) de una competicion.

    Cualquier competicion no reconocida cae en tier 3 (nivel medio) como
    valor por defecto conservador en vez de fallar el pipeline.
    """
    if not isinstance(competition_name, str) or not competition_name.strip():
        return 3
    name = competition_name.strip()
    if name in TIER_1:
        return 1
    if name in TIER_2:
        return 2
    if name in TIER_3:
        return 3
    if name in TIER_4_EXTRA or name.startswith(TIER_4_PREFIXES):
        return 4
    if name.startswith(TIER_5_PREFIXES):
        return 5
    return 3
