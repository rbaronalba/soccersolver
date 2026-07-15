"""UI para el director deportivo: selecciona un jugador y ve el rango de
sueldo esperado segun el mercado, con los comparables usados y la confianza.
Ejecutar con: streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from comparator import estimate_salary

ROOT = Path(__file__).resolve().parent
POSITION_LABELS = {"GK": "Portero", "DEF": "Defensa", "MID": "Centrocampista", "ATT": "Delantero"}


@st.cache_data
def load_data(_players_mtime: float, _wages_mtime: float):
    # Los mtimes forman parte de la clave de cache: si se relanza
    # `pipeline.py` con la app abierta, el cache se invalida solo en vez de
    # servir datos obsoletos hasta reiniciar el proceso.
    players = pd.read_csv(ROOT / "data" / "players_clean.csv")
    wages = pd.read_csv(ROOT / "data" / "wages_clean.csv")
    return players, wages


def fmt_eur(x: float) -> str:
    if pd.isna(x):
        return "sin dato"
    return f"{x:,.0f} €".replace(",", ".")


st.set_page_config(page_title="SoccerSolver · Baremo de sueldos", layout="centered")
st.title("¿Estamos pagando de más o de menos?")
st.caption("Rango de sueldo esperado según el mercado, comparado por posición, edad y nivel de liga.")

try:
    players_path = ROOT / "data" / "players_clean.csv"
    wages_path = ROOT / "data" / "wages_clean.csv"
    players, wages = load_data(players_path.stat().st_mtime, wages_path.stat().st_mtime)
except FileNotFoundError:
    st.error("No se encuentran los datos procesados. Ejecuta primero `python src/pipeline.py`.")
    st.stop()

@st.cache_data
def build_label_map(_players_mtime: float) -> dict:
    return {
        f'{r.player_name} — {r.team_name} ({r.competition_name})': r.player_id
        for r in players.itertuples()
    }


label_map = build_label_map(players_path.stat().st_mtime)
selected_label = st.selectbox(
    "Jugador", sorted(label_map.keys()), index=None, placeholder="Escribe para buscar (ej: Lamine Yamal)"
)
if selected_label is None:
    st.info("Busca y selecciona un jugador para ver su rango de sueldo esperado.")
    st.stop()
player = players[players["player_id"] == label_map[selected_label]].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Posición", POSITION_LABELS.get(player.position, player.position))
col2.metric("Edad", int(player.age))
col3.metric("Valor de mercado", fmt_eur(player.market_value))
st.caption(f"{player.team_name} · {player.competition_name} (tier {int(player.tier)})")

est = estimate_salary(player.position, int(player.age), int(player.tier), player.market_value, wages)

st.subheader("Rango de sueldo anual esperado")
if pd.isna(est.mid):
    st.warning("No hay comparables suficientes para estimar un rango.")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo (p25)", fmt_eur(est.low))
    c2.metric("Esperado (mediana)", fmt_eur(est.mid))
    c3.metric("Máximo (p75)", fmt_eur(est.high))

    confidence_color = {"Alta": "🟢", "Media": "🟡", "Baja": "🔴"}[est.confidence]
    st.write(f"**Confianza: {confidence_color} {est.confidence}** — basado en {est.n_comparables} jugadores "
             f"comparables (±{est.age_window} años de edad).")
    if est.tier_used != est.tier_requested:
        st.info(
            f"La liga de este jugador (tier {est.tier_requested}) no tiene sueldos reales en la fuente; "
            f"se ha usado como referencia el tier {est.tier_used} más cercano. El rango es orientativo."
        )

    st.subheader("Comparables usados")
    comp_df = pd.DataFrame(est.comparables).rename(columns={
        "name": "Jugador", "club_name": "Club", "league": "Liga",
        "age": "Edad", "value": "Valor", "wage": "Sueldo anual (fuente)",
    })
    if not comp_df.empty:
        comp_df["Valor"] = comp_df["Valor"].map(fmt_eur)
        comp_df["Sueldo anual (fuente)"] = comp_df["Sueldo anual (fuente)"].map(fmt_eur)
        st.dataframe(comp_df, hide_index=True, use_container_width=True)
