import pandas as pd

from comparator import estimate_salary


def _wages_pool(n=20, position="ATT", tier=1, base_age=25):
    rows = []
    for i in range(n):
        rows.append({
            "name": f"Player{i}", "club_name": "Club", "league": "Premier League",
            "tier": tier, "position": position, "age": base_age + (i % 5) - 2,
            "value": 10_000_000, "wage": 2_000_000 + i * 100_000,
        })
    return pd.DataFrame(rows)


def test_estimate_scales_with_market_value():
    wages = _wages_pool()
    low_val = estimate_salary("ATT", 25, 1, 10_000_000, wages)
    high_val = estimate_salary("ATT", 25, 1, 20_000_000, wages)
    assert high_val.mid > low_val.mid
    assert high_val.mid == low_val.mid * 2  # ratio-based: escala linealmente con market_value


def test_low_sample_falls_back_to_low_confidence():
    wages = _wages_pool(n=3)
    est = estimate_salary("ATT", 25, 1, 10_000_000, wages)
    assert est.confidence == "Baja"


def test_missing_tier_falls_back_to_nearest_available():
    wages = _wages_pool(tier=1)
    est = estimate_salary("ATT", 25, 4, 1_000_000, wages)
    assert est.tier_used == 1
    assert est.tier_requested == 4
    assert est.confidence != "Alta"


def test_no_comparables_returns_nan_range():
    wages = _wages_pool(position="DEF")
    est = estimate_salary("GK", 25, 1, 1_000_000, wages)
    assert pd.isna(est.mid)
    assert est.n_comparables == 0
