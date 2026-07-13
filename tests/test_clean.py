import pandas as pd

from clean import clean_players, clean_wages, _parse_money
from tiers import competition_tier


def test_parse_money():
    assert _parse_money("€440K") == 440_000
    assert _parse_money("€115.5M") == 115_500_000
    assert pd.isna(_parse_money(None))
    assert pd.isna(_parse_money("n/a"))


def test_competition_tier():
    assert competition_tier("Premier League") == 1
    assert competition_tier("LaLiga2") == 2
    assert competition_tier("Serie C - Girone A") == 3
    assert competition_tier("Regionalliga Bayern") == 4
    assert competition_tier("Primavera 1") == 5
    assert competition_tier("Liga Desconocida X") == 3  # fallback conservador
    assert competition_tier(None) == 3


def test_clean_players_drops_missing_and_out_of_range():
    df = pd.DataFrame({
        "player_id": [1, 2, 3, 4, 4],
        "player_name": ["A", "B", "C", "D", "D"],
        "position": ["ATT", "DEF", None, "MID", "MID"],
        "main_position": ["ST", "CB", "CB", "CM", "CM"],
        "birth_date": ["2000-01-01", "1995-05-05", "1990-01-01", "2005-01-01", "2005-01-01"],
        "nationality": ["ES", "ES", "ES", "ES", "ES"],
        "team_id": [1, 1, 1, 1, 1],
        "team_name": ["X", "X", "X", "X", "X"],
        "competition_id": ["ES1", "ES1", "ES1", "ES1", "ES1"],
        "competition_name": ["LaLiga", "LaLiga", "LaLiga", "LaLiga", "LaLiga"],
        "competition_country": ["Spain"] * 5,
        "season": ["2025-2026"] * 5,
        "market_value": [1_000_000, None, 500_000, 400_000_000, 400_000_000],
    })
    out, metrics = clean_players(df, reference_date=pd.Timestamp("2026-01-01"))
    # B: sin market_value. C: sin posicion. fila 4 duplicada. fila con 400M: fuera de rango.
    assert out["player_name"].tolist() == ["A"]
    assert metrics["output_rows"] == 1
    assert metrics["dropped_missing_required_fields"] == 2
    assert metrics["dropped_out_of_range"] == 2
    assert metrics["dropped_duplicate_player_id"] == 0  # ya se filtraron antes por rango


def test_clean_wages_annualizes_and_maps_position():
    df = pd.DataFrame({
        "name": ["P1", "P2"],
        "dob": ["2000-01-01", "1995-01-01"],
        "positions": ["ST,CAM", "GK"],
        "value": ["€10M", "€5M"],
        "wage": ["€10K", "€5K"],
        "club_name": ["ClubA", "ClubB"],
        "club_league_name": ["Premier League", "Bundesliga"],
    })
    out, metrics = clean_wages(df, reference_date=pd.Timestamp("2026-01-01"))
    assert metrics["output_rows"] == 2
    assert out.loc[out["name"] == "P1", "position"].item() == "ATT"
    assert out.loc[out["name"] == "P1", "wage"].item() == 10_000 * 52
    assert out.loc[out["name"] == "P1", "tier"].item() == 1
