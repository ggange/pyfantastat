"""Tests for Formazioni analytics: validation, rosters, player stats, top formation."""

from pathlib import Path

import pytest

from pyfantastat.io.formazioni import load_formazioni_xlsx
from pyfantastat.io.models import CalendarData, FormazioniMatchday, FormazioniPlayer, FormazioniTeam
from pyfantastat.formazioni import (
    PlayerRecord,
    TeamRoster,
    build_team_rosters,
    player_scoring_stats,
    top_formation,
    validate_formazioni,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_formazioni.xlsx"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_calendar(team_points: dict[str, list[float]], current: int = 1) -> CalendarData:
    names = list(team_points)
    return CalendarData(
        league_name=None,
        team_names=names,
        user_names=names,
        team_points=team_points,
        match_count=current,
        calendar=[],
        current_matchday=current,
        first_matchday_serie_a=None,
        last_matchday_serie_a=None,
    )


def _single_giornata_data() -> dict[int, FormazioniMatchday]:
    return {1: load_formazioni_xlsx(FIXTURE)}


def _make_roster(players_by_matchday: dict[str, dict[int, tuple[float, float]]]) -> TeamRoster:
    """Build a TeamRoster directly from a dict of player-name → {giornata: (v, fv)}."""
    roster = TeamRoster(team_name="TEST")
    for name, mds in players_by_matchday.items():
        role = "C"
        record = PlayerRecord(name=name, ruolo=role, matchdays=dict(mds))
        roster.players[name.lower()] = record
    return roster


# ---------------------------------------------------------------------------
# validate_formazioni
# ---------------------------------------------------------------------------


def test_validate_clean():
    data = _single_giornata_data()
    cal = _make_calendar({
        "ALPHA FC": [61.5],
        "BETA SC":  [63.5],
    })
    val = validate_formazioni(data, cal)
    assert val.ok
    assert val.issues == []
    assert val.unmatched_teams == []
    assert val.missing_matchdays == []


def test_validate_score_mismatch():
    data = _single_giornata_data()
    cal = _make_calendar({
        "ALPHA FC": [99.0],   # deliberately wrong
        "BETA SC":  [63.5],
    })
    val = validate_formazioni(data, cal)
    assert not val.ok
    assert len(val.issues) == 1
    assert val.issues[0].team_name == "ALPHA FC"
    assert val.issues[0].calendar_score == pytest.approx(99.0)
    assert val.issues[0].formazioni_score == pytest.approx(61.5)


def test_validate_unmatched_team():
    data = _single_giornata_data()
    cal = _make_calendar({
        "ALPHA FC": [61.5],
        # BETA SC intentionally absent
    })
    val = validate_formazioni(data, cal)
    assert not val.ok
    assert any(t[1] == "BETA SC" for t in val.unmatched_teams)


def test_validate_missing_matchdays():
    data = _single_giornata_data()  # only giornata 1
    cal = _make_calendar(
        {"ALPHA FC": [61.5, 0.0, 0.0], "BETA SC": [63.5, 0.0, 0.0]},
        current=3,
    )
    val = validate_formazioni(data, cal)
    assert not val.ok
    assert 2 in val.missing_matchdays
    assert 3 in val.missing_matchdays


def test_validate_skips_future_giornate():
    """Formazioni files beyond current_matchday should not trigger issues."""
    future_team = FormazioniTeam(team_name="ALPHA FC", totale=99.0)
    future_md = FormazioniMatchday(giornata=5, teams=[future_team])
    data = {1: load_formazioni_xlsx(FIXTURE), 5: future_md}
    cal = _make_calendar({"ALPHA FC": [61.5], "BETA SC": [63.5]})
    val = validate_formazioni(data, cal)
    # Only giornata 1 is checked; giornata 5 is ignored
    assert val.ok


def test_validate_tolerance():
    data = _single_giornata_data()
    # 0.3 pt difference — within default tol=0.5
    cal = _make_calendar({"ALPHA FC": [61.8], "BETA SC": [63.5]})
    val = validate_formazioni(data, cal, tol=0.5)
    assert val.ok


# ---------------------------------------------------------------------------
# build_team_rosters
# ---------------------------------------------------------------------------


def test_build_rosters_team_count():
    data = _single_giornata_data()
    rosters = build_team_rosters(data)
    assert len(rosters) == 2


def test_build_rosters_team_names():
    data = _single_giornata_data()
    rosters = build_team_rosters(data)
    assert "alpha fc" in rosters
    assert "beta fc" not in rosters


def test_build_rosters_player_recorded():
    data = _single_giornata_data()
    rosters = build_team_rosters(data)
    alpha = rosters["alpha fc"]
    assert "rossi" in alpha.players
    record = alpha.players["rossi"]
    assert 1 in record.matchdays
    voto, fv = record.matchdays[1]
    assert voto == pytest.approx(6.5)
    assert fv == pytest.approx(7.5)


def test_build_rosters_multiple_matchdays():
    # Two files for the same team
    md1 = FormazioniMatchday(giornata=1, teams=[
        FormazioniTeam("TEAM A", 60.0, [FormazioniPlayer("Rossi", "P", 6.5, 7.5)]),
    ])
    md2 = FormazioniMatchday(giornata=2, teams=[
        FormazioniTeam("TEAM A", 65.0, [FormazioniPlayer("Rossi", "P", 7.0, 8.0)]),
    ])
    rosters = build_team_rosters({1: md1, 2: md2})
    record = rosters["team a"].players["rossi"]
    assert record.matchdays[1] == (6.5, 7.5)
    assert record.matchdays[2] == (7.0, 8.0)


def test_build_rosters_preserves_original_case():
    data = _single_giornata_data()
    rosters = build_team_rosters(data)
    # Key is normalised; original case is in team_name attribute
    alpha = rosters["alpha fc"]
    assert alpha.team_name == "ALPHA FC"


# ---------------------------------------------------------------------------
# player_scoring_stats
# ---------------------------------------------------------------------------


def test_player_stats_basic():
    record = PlayerRecord("Rossi", "P", matchdays={1: (6.5, 7.5), 2: (7.0, 8.0)})
    s = player_scoring_stats(record)
    assert s["mean_voto"] == pytest.approx(6.75)
    assert s["mean_fantavoto"] == pytest.approx(7.75)


def test_player_stats_excludes_absent():
    """Matchdays where voto=0 and fv=0 (bench/absent) must not count."""
    record = PlayerRecord("Rossi", "P", matchdays={
        1: (6.5, 7.5),
        2: (0.0, 0.0),   # bench
        3: (7.0, 8.0),
    })
    s = player_scoring_stats(record)
    assert s["mean_voto"] == pytest.approx(6.75)  # only md 1 and 3


def test_player_stats_n_matchdays_cutoff():
    record = PlayerRecord("Rossi", "P", matchdays={1: (6.5, 7.5), 5: (9.0, 10.0)})
    s = player_scoring_stats(record, n_matchdays=2)
    assert s["mean_voto"] == pytest.approx(6.5)   # only giornata 1


def test_player_stats_all_absent():
    record = PlayerRecord("Rossi", "P", matchdays={1: (0.0, 0.0), 2: (0.0, 0.0)})
    s = player_scoring_stats(record)
    assert s["mean_voto"] == 0.0
    assert s["mean_fantavoto"] == 0.0


# ---------------------------------------------------------------------------
# top_formation
# ---------------------------------------------------------------------------


def _build_big_roster() -> TeamRoster:
    """Roster with enough players per role for all valid formations."""
    players = {
        "gk1":  {"ruolo": "P", "mds": {1: (6.5, 7.5), 2: (6.0, 7.0)}},
        "gk2":  {"ruolo": "P", "mds": {1: (5.5, 6.0)}},
        "def1": {"ruolo": "D", "mds": {1: (6.5, 7.0), 2: (6.0, 6.5)}},
        "def2": {"ruolo": "D", "mds": {1: (6.0, 6.0), 2: (6.5, 7.0)}},
        "def3": {"ruolo": "D", "mds": {1: (5.5, 5.5), 2: (5.5, 5.0)}},
        "def4": {"ruolo": "D", "mds": {1: (6.0, 6.5)}},
        "def5": {"ruolo": "D", "mds": {1: (6.0, 6.0)}},
        "mid1": {"ruolo": "C", "mds": {1: (7.0, 9.0), 2: (7.0, 9.0)}},
        "mid2": {"ruolo": "C", "mds": {1: (6.5, 7.5), 2: (6.5, 7.5)}},
        "mid3": {"ruolo": "C", "mds": {1: (6.0, 6.5), 2: (6.0, 6.5)}},
        "mid4": {"ruolo": "C", "mds": {1: (6.0, 6.0)}},
        "mid5": {"ruolo": "C", "mds": {1: (6.0, 6.0)}},
        "att1": {"ruolo": "A", "mds": {1: (8.0, 12.0), 2: (8.0, 12.0)}},
        "att2": {"ruolo": "A", "mds": {1: (7.0, 9.0), 2: (7.0, 9.0)}},
        "att3": {"ruolo": "A", "mds": {1: (6.5, 7.5)}},
    }
    roster = TeamRoster(team_name="BIG TEAM")
    for key, data in players.items():
        roster.players[key] = PlayerRecord(
            name=key,
            ruolo=data["ruolo"],
            matchdays=data["mds"],
        )
    return roster


def test_top_formation_returns_11_players():
    roster = _build_big_roster()
    result = top_formation(roster)
    assert len(result.players) == 11


def test_top_formation_valid_formation():
    valid = {(3, 5, 2), (3, 4, 3), (4, 5, 1), (4, 4, 2), (4, 3, 3), (5, 3, 2), (5, 4, 1)}
    roster = _build_big_roster()
    result = top_formation(roster)
    assert result.formation in valid


def test_top_formation_one_gk():
    roster = _build_big_roster()
    result = top_formation(roster)
    gks = [p for p in result.players if p.ruolo == "P"]
    assert len(gks) == 1


def test_top_formation_role_counts_match_formation():
    roster = _build_big_roster()
    result = top_formation(roster)
    n_def, n_mid, n_att = result.formation
    assert sum(1 for p in result.players if p.ruolo == "D") == n_def
    assert sum(1 for p in result.players if p.ruolo == "C") == n_mid
    assert sum(1 for p in result.players if p.ruolo == "A") == n_att


def test_top_formation_picks_highest_efv():
    """The top attacker by EFV should always be att1 (highest fantavoto)."""
    roster = _build_big_roster()
    result = top_formation(roster)
    att_players = [p for p in result.players if p.ruolo == "A"]
    att_names = {p.name for p in att_players}
    assert "att1" in att_names


def test_top_formation_total_efv_positive():
    roster = _build_big_roster()
    result = top_formation(roster)
    assert result.total_efv > 0


def test_top_formation_from_real_fixture():
    data = _single_giornata_data()
    rosters = build_team_rosters(data)
    # With only 1 matchday, both teams should still produce a result
    for roster in rosters.values():
        result = top_formation(roster)
        assert len(result.players) == 11
        assert result.total_efv > 0
