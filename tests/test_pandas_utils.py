"""Tests for pyfantastat.pandas_utils — all four DataFrame helpers."""
import pytest
import random
from pyfantastat import (
    FormazioniPlayer, FormazioniTeam, FormazioniMatchday,
    build_team_rosters,
    roster_to_dataframe,
    rosters_to_dataframe,
    top_formation_to_dataframe,
    matchday_to_dataframe,
    top_formation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _synthetic_form_data():
    rng = random.Random(42)
    roles = ["P"] + ["D"] * 4 + ["C"] * 4 + ["A"] * 3
    form_data = {}
    for g in range(1, 4):
        teams = []
        for team_name in ["Alpha", "Beta"]:
            players = [
                FormazioniPlayer(
                    name=f"P{i}",
                    ruolo=roles[i],
                    voto=round(rng.uniform(5, 8), 2),
                    fantavoto=round(rng.uniform(4, 10), 2),
                )
                for i in range(11)
            ]
            totale = round(sum(p.fantavoto for p in players), 2)
            teams.append(FormazioniTeam(team_name=team_name, totale=totale, players=players))
        form_data[g] = FormazioniMatchday(giornata=g, teams=teams)
    return form_data


@pytest.fixture
def form_data():
    return _synthetic_form_data()


@pytest.fixture
def rosters(form_data):
    return build_team_rosters(form_data)


@pytest.fixture
def first_roster(rosters):
    return next(iter(rosters.values()))


@pytest.fixture
def top_result(first_roster):
    return top_formation(first_roster)


# ---------------------------------------------------------------------------
# roster_to_dataframe
# ---------------------------------------------------------------------------

def test_roster_to_dataframe_has_expected_columns(first_roster):
    df = roster_to_dataframe(first_roster)
    expected = {"name", "ruolo", "apps", "mean_voto", "std_voto", "mean_fantavoto", "std_fantavoto"}
    assert expected.issubset(set(df.columns))


def test_roster_to_dataframe_row_count(first_roster):
    df = roster_to_dataframe(first_roster)
    assert len(df) == len(first_roster.players)


def test_roster_to_dataframe_apps_are_positive(first_roster):
    df = roster_to_dataframe(first_roster)
    assert (df["apps"] > 0).all()


def test_roster_to_dataframe_mean_fantavoto_in_range(first_roster):
    df = roster_to_dataframe(first_roster)
    assert (df["mean_fantavoto"] >= 0).all()
    assert (df["mean_fantavoto"] <= 15).all()


def test_roster_to_dataframe_ruolo_unknown_fallback():
    # Player with ruolo=None should appear as "?"
    player = FormazioniPlayer(name="X", ruolo=None, voto=6.0, fantavoto=7.0)
    team = FormazioniTeam(team_name="T", totale=7.0, players=[player])
    form = {1: FormazioniMatchday(giornata=1, teams=[team])}
    roster = build_team_rosters(form)["t"]
    df = roster_to_dataframe(roster)
    assert df["ruolo"].iloc[0] == "?"


# ---------------------------------------------------------------------------
# rosters_to_dataframe
# ---------------------------------------------------------------------------

def test_rosters_to_dataframe_has_team_column(rosters):
    df = rosters_to_dataframe(rosters)
    assert "team" in df.columns


def test_rosters_to_dataframe_row_count(rosters):
    df = rosters_to_dataframe(rosters)
    total_players = sum(len(r.players) for r in rosters.values())
    assert len(df) == total_players


def test_rosters_to_dataframe_team_names(rosters):
    df = rosters_to_dataframe(rosters)
    team_names = set(df["team"].unique())
    expected = {r.team_name for r in rosters.values()}
    assert team_names == expected


def test_rosters_to_dataframe_empty_returns_empty_frame():
    df = rosters_to_dataframe({})
    assert len(df) == 0
    assert "team" in df.columns


# ---------------------------------------------------------------------------
# top_formation_to_dataframe
# ---------------------------------------------------------------------------

def test_top_formation_to_dataframe_shape(top_result):
    df = top_formation_to_dataframe(top_result)
    assert df.shape == (11, 3)


def test_top_formation_to_dataframe_columns(top_result):
    df = top_formation_to_dataframe(top_result)
    assert set(df.columns) == {"name", "ruolo", "efv"}


def test_top_formation_to_dataframe_index_one_based(top_result):
    df = top_formation_to_dataframe(top_result)
    assert df.index[0] == 1
    assert df.index[-1] == 11


def test_top_formation_to_dataframe_efv_positive(top_result):
    df = top_formation_to_dataframe(top_result)
    assert (df["efv"] > 0).all()


def test_top_formation_to_dataframe_all_roles_present(top_result):
    df = top_formation_to_dataframe(top_result)
    roles = set(df["ruolo"].unique())
    assert "P" in roles  # always has a goalkeeper


# ---------------------------------------------------------------------------
# matchday_to_dataframe
# ---------------------------------------------------------------------------

def test_matchday_to_dataframe_columns(form_data):
    matchday = next(iter(form_data.values()))
    df = matchday_to_dataframe(matchday)
    assert set(df.columns) == {"team", "name", "ruolo", "voto", "fantavoto"}


def test_matchday_to_dataframe_row_count(form_data):
    matchday = next(iter(form_data.values()))
    df = matchday_to_dataframe(matchday)
    total = sum(len(t.players) for t in matchday.teams)
    assert len(df) == total


def test_matchday_to_dataframe_team_names(form_data):
    matchday = form_data[1]
    df = matchday_to_dataframe(matchday)
    assert set(df["team"].unique()) == {"Alpha", "Beta"}


def test_matchday_to_dataframe_voto_in_range(form_data):
    matchday = next(iter(form_data.values()))
    df = matchday_to_dataframe(matchday)
    assert (df["voto"] >= 0).all()


def test_matchday_to_dataframe_empty_matchday():
    empty = FormazioniMatchday(giornata=1, teams=[])
    df = matchday_to_dataframe(empty)
    assert len(df) == 0
    assert "team" in df.columns
