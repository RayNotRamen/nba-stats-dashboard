from datetime import date, timedelta
import numpy as np
import pandas as pd
import streamlit as st
from nba_api.stats.endpoints import leaguedashplayerstats

SEASON = "2026-27"

DEFAULT_WEIGHTS = {
    "PTS": 1.0,
    "REB": 1.0,
    "AST": 2.0,
    "STL": 4.0,
    "BLK": 4.0,
    "TOV": -2.0,
    "FGM": 2.0,
    "FGA": -1.0,
    "FG3M": 1.0,
}

@st.cache_data(ttl=3600)
def get_week_stats(per_mode):
    end = date.today()
    start = end - timedelta(days=7)
    return leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed=per_mode,
        date_from_nullable=start.strftime("%m/%d/%Y"),
        date_to_nullable=end.strftime("%m/%d/%Y"),
    ).get_data_frames()[0]

tab_eosa, tab_top10 = st.tabs(["End-of-Season Awards Estimates", "Top 10 Stats"])

# ----- End-of-season awards ------------------------------------------------------  

# -------- MVP CALCULATIONS -------------------------------------------------------
MVP_CANDIDATES = 10
MVP_WEIGHTS = {"PTS_Z": 0.35, "PIE_Z": 0.40, "WINS_Z": 0.25}   
MVP_TEMPERATURE = 1.0
MVP_MIN_MINUTES = 20 # candidates are required at least 20 minutes a game
# MVP_ELIGIBLE_FRACTION = 82-65 
# (add later as the season continues to take out who can't win for missing too many games)

@st.cache_data(ttl=3600)
def get_season_players(measure_type):
    return leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season", 
        per_mode_detailed="PerGame",
        measure_type_detailed_defense=measure_type,
        ).get_data_frames()[0]

def zscore(series):
    return (series - series.mean()) / series.std()

def mvp_estimates(min_games):
    base = get_season_players("Base")
    adv = get_season_players("Advanced")

    # PIE is an nba stat called Player Impact Estimate 
    # that measures a player's overall statistical contribution vs
    # their games that they play, it is the best way to display a players value to a team
    # which is important in considiering an mvp candidate  

    # points and win% are in the Base table, PIE is in the Advanced table
    df = base[["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "PTS", "W_PCT"]].merge(
        adv[["PLAYER_ID", "PIE"]], on="PLAYER_ID"
    )
    # checks minimum games (mvp players are required to play at least 65 games)
    df = df[(df["GP"] >= min_games) &(df["MIN"] >= MVP_MIN_MINUTES)].copy()
    if len(df) < MVP_CANDIDATES:
        return None

    df["PTS_Z"] = zscore(df["PTS"])
    df["PIE_Z"] = zscore(df["PIE"])
    df["WINS_Z"] = zscore(df["W_PCT"])

    # step 1: candidates = best points + PIE combined
    df["CANDIDATE"] = df["PTS_Z"] + df["PIE_Z"]
    top = df.sort_values("CANDIDATE", ascending=False).head(MVP_CANDIDATES).copy()

    # step 2: MVP score, then percentages that add up to 100
    top["SCORE"] = sum(top[col] * w for col, w in MVP_WEIGHTS.items())
    scaled = (top["SCORE"] - top["SCORE"].max()) / MVP_TEMPERATURE
    top["Chance"] = (np.exp(scaled) / np.exp(scaled).sum() * 100).round(1)
    return top.sort_values("Chance", ascending=False)

# --------------- DPOY Calculations --------------------------------------------------------
DPOY_CANDIDATES = 10
DPOY_WEIGHTS = {"BLK_Z": 0.25, "STL_Z": 0.25, "DREB_Z": 0.10, "DEF_Z": 0.35}   
DPOY_TEMPERATURE = 1.0
DPOY_MIN_MINUTES = 20

def dpoy_estimates(min_games):
    base = get_season_players("Base")
    adv = get_season_players("Advanced")

# blocks, steals, rebounds are in Base; defensive rating is in Advanced
    df = base[["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "BLK", "STL", "DREB"]].merge(
        adv[["PLAYER_ID", "DEF_RATING"]], on="PLAYER_ID"
    )
    # filter, so tiny-sample players can't distort the z-scores
    df = df[(df["GP"] >= min_games) & (df["MIN"] >= DPOY_MIN_MINUTES)].copy()
    if len(df) < DPOY_CANDIDATES:
        return None

    df["BLK_Z"] = zscore(df["BLK"])
    df["STL_Z"] = zscore(df["STL"])
    df["DREB_Z"] = zscore(df["DREB"])
    df["DEF_Z"] = -zscore(df["DEF_RATING"])   # a LOWER defensive rating is better

    # score everyone, then take the top 10
    df["SCORE"] = sum(df[col] * w for col, w in DPOY_WEIGHTS.items())
    top = df.sort_values("SCORE", ascending=False).head(DPOY_CANDIDATES).copy()

    # percentages that add up to 100
    scaled = (top["SCORE"] - top["SCORE"].max()) / DPOY_TEMPERATURE
    top["Chance"] = (np.exp(scaled) / np.exp(scaled).sum() * 100).round(1)
    return top

# --------------- ROTY Calculations --------------------------------------------------------
ROY_CANDIDATES = 5
ROY_WEIGHTS = {"PTS_Z": 0.30, "REB_Z": 0.15, "AST_Z": 0.20, "PIE_Z": 0.35}
ROY_TEMPERATURE = 1.0
ROY_MIN_MINUTES = 15

@st.cache_data(ttl=3600)
def get_rookie_players(measure_type, experience=None):
    return leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season", 
        per_mode_detailed="PerGame",
        measure_type_detailed_defense=measure_type,
        player_experience_nullable=experience,
        ).get_data_frames()[0]

def roy_estimates(min_games):
    base = get_rookie_players("Base", "Rookie")
    adv = get_rookie_players("Advanced", "Rookie")

    df = base[["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "PTS", "REB", "AST"]].merge(
        adv[["PLAYER_ID", "PIE"]], on="PLAYER_ID"
    )
    # filter first, so tiny-sample rookies can't distort the z-scores
    df = df[(df["GP"] >= min_games) & (df["MIN"] >= ROY_MIN_MINUTES)].copy()
    if len(df) < ROY_CANDIDATES:
        return None

    df["PTS_Z"] = zscore(df["PTS"])
    df["REB_Z"] = zscore(df["REB"])
    df["AST_Z"] = zscore(df["AST"])
    df["PIE_Z"] = zscore(df["PIE"])

    df["SCORE"] = sum(df[col] * w for col, w in ROY_WEIGHTS.items())
    top = df.sort_values("SCORE", ascending=False).head(ROY_CANDIDATES).copy()

    scaled = (top["SCORE"] - top["SCORE"].max()) / ROY_TEMPERATURE
    top["Chance"] = (np.exp(scaled) / np.exp(scaled).sum() * 100).round(1)
    return top

# ---------- End-of-season awards: display -------------------------------------------------------------------------
with tab_eosa:
    st.header("End-of-Season Awards Estimates")
    tab_mvp, tab_dpoy, tab_roy = st.tabs(["MVP","DPOY", "ROY"])

    # MVP tab
    with tab_mvp:
        st.subheader(f"MVP Estimates (minimum {MVP_MIN_MINUTES} minutes per game)")
        mvp_min_gp = st.slider("Minimum games played", 1, 82, 1, key="mvp_min_gp")

        try:
            mvp = mvp_estimates(mvp_min_gp)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
        else:
            if mvp is None:
                st.info("Not enough eligible players yet. Lower the minimum games.")
            else:
                table = mvp[["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "PTS", "PIE", "W_PCT", "Chance"]].round(3)
                table.columns = ["Player", "Team", "GP", "PTS", "PIE", "Win %", "Chance %"]
                table.index = range(1, len(table) + 1)
                st.dataframe(table)
                st.bar_chart(table, x="Player", y="Chance %", sort="-Chance %")
                st.caption("*THIS IS A STATS-BASED ESTIMATE AND MAY NOT BE ACCURATE TO VOTER DECISION")   

    # DPOY tab
    with tab_dpoy:
        st.subheader(f"DPOY Estimates (minimum {DPOY_MIN_MINUTES} minutes per game)")
        dpoy_min_gp = st.slider("Minimum games played", 1, 82, 1, key="dpoy_min_gp")

        try:
            dpoy = dpoy_estimates(dpoy_min_gp)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
        else:
            if dpoy is None:
                st.info("Not enough eligible players yet. Lower the minimum games.")
            else:
                table = dpoy[["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "BLK", "STL", "DREB", "DEF_RATING", "Chance"]].round(1)
                table.columns = ["Player", "Team", "GP", "BLK", "STL", "DREB", "Def Rating", "Chance %"]
                table.index = range(1, len(table) + 1)
                st.dataframe(table)
                st.bar_chart(table, x="Player", y="Chance %", sort="-Chance %")
                st.caption("*STATS-BASED ESTIMATE. BOX SCORES FAVORS SHOT BLOCKERS AND UNDERVALUES PERIMETER DEFENSE.")

    # ROTY Tab
    with tab_roy:
        st.subheader(f"ROY Estimates (rookies, minimum {ROY_MIN_MINUTES} minutes per game)")
        roy_min_gp = st.slider("Minimum games played", 1, 82, 1, key="roy_min_gp")

        try:
            roy = roy_estimates(roy_min_gp)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
        else:
            if roy is None:
                st.info("Not enough eligible rookies yet. Lower the minimum games.")
            else:
                table = roy[["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "PTS", "REB", "AST", "PIE", "Chance"]]
                table = table.round({"MIN": 1, "PTS": 1, "REB": 1, "AST": 1, "PIE": 3})
                table.columns = ["Player", "Team", "GP", "MIN", "PTS", "REB", "AST", "PIE", "Chance %"]
                table.index = range(1, len(table) + 1)
                st.dataframe(table)
                st.bar_chart(table, x="Player", y="Chance %", sort="-Chance %")
                st.caption("STATS-BASED ESTIMATE, FIRST-YEAR PLAYERS ONLY. VOTERS ALSO WEIGHT ROLE AND NAARRATIVE FOR THIS AWARD.")

# ---------- Top 10 stats section -----------------------------------------------------------------------
with tab_top10:
    st.header("Top 10 Stats for NBA 2026/2027 Season")

# controls
    st.sidebar.header("Fantasy scoring")
    weights = {
        stat: st.sidebar.number_input(f"{stat} weight", value=w, step=0.5)
        for stat, w in DEFAULT_WEIGHTS.items()
    }

    per_mode = st.radio("View", ["Totals", "PerGame"], horizontal=True)
    rank_by = st.selectbox("Rank by", ["FANTASY", "PTS", "AST", "REB", "STL", "BLK","FGM", "FGA", "FG3M"])
    min_gp = st.slider("Minimum games played", 1, 82, 1)

# load data safely
    try:
        week = get_week_stats(per_mode)
    except Exception:
        st.error("Couldn't reach the NBA API. Wait a minute and refresh.")
        st.stop()

    week = week[week["GP"] >= min_gp]

    if week.empty:
        st.info("No players match. Try a lower minimum or check back after more games.")
        st.stop()

    team_select = st.multiselect("Teams", sorted(week["TEAM_ABBREVIATION"].unique()))

    if team_select:
        week =  week[week["TEAM_ABBREVIATION"].isin(team_select)]

    # fantasy score
    week["FANTASY"] = sum(week[col] * w for col, w in weights.items()).round(1)

    # build the table
    top = week.sort_values(rank_by, ascending=False).head(10)
    top = top[["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "FANTASY",
            "PTS", "REB", "AST", "STL", "BLK", "FGM", "FG3M", "FGA"]]
    top.index = range(1, len(top) + 1)
    top.columns = ["Player", "Team", "GP", "MIN", "FP",
                "PTS", "REB", "AST", "STL", "BLK", "FGM", "3PM", "FGA"]
    top = top.round(1)

    st.dataframe(top)
    st.bar_chart(top, x="Player", y="FP", sort="-FP")