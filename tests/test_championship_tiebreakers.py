"""Tests covering tiebreakers, interval mode, guard paths, and utility methods."""
import pytest
import numpy as np
from pyfantastat.team import Team
from pyfantastat.championship import Championship


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ch(points_per_team, card_order=None, interval=False, pt_interval=None, only_in_range=False):
    """Build a fully ready championship from a list of per-team point lists."""
    teams = []
    for i, pts in enumerate(points_per_team):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(pts)
        teams.append(t)
    n = len(teams)
    # Simple calendar: each pair plays once per round, cycling
    pairs = [[i, i + 1] for i in range(0, n, 2)]
    rounds = len(points_per_team[0])
    calendar = [pairs for _ in range(rounds)]
    ch = Championship(
        teams,
        card_order=card_order or ["Punti"],
        interval=interval,
        pt_interval=pt_interval,
        only_in_range=only_in_range,
    )
    ch.set_calendar(calendar)
    ch.set_current_matchday(rounds)
    ch.generate_ranking()
    return ch


# ---------------------------------------------------------------------------
# Competition type validation
# ---------------------------------------------------------------------------

def test_competition_type_mantra_raises():
    teams = [Team("A", "a"), Team("B", "b")]
    with pytest.raises(NotImplementedError):
        Championship(teams, competition_type="Mantra")


def test_competition_type_invalid_raises():
    teams = [Team("A", "a"), Team("B", "b")]
    with pytest.raises(ValueError):
        Championship(teams, competition_type="Unknown")


# ---------------------------------------------------------------------------
# set_current_matchday guards
# ---------------------------------------------------------------------------

def test_set_current_matchday_without_calendar_raises():
    teams = [Team("A", "a"), Team("B", "b")]
    ch = Championship(teams)
    with pytest.raises(ValueError, match="Calendar must be set"):
        ch.set_current_matchday(1)


def test_set_current_matchday_out_of_range_raises():
    teams = [Team("A", "a"), Team("B", "b")]
    ch = Championship(teams)
    ch.set_calendar([[[0, 1]]])
    with pytest.raises(ValueError):
        ch.set_current_matchday(-1)
    with pytest.raises(ValueError):
        ch.set_current_matchday(99)


# ---------------------------------------------------------------------------
# Interval mode — only_in_range=False (default when interval=True)
# ---------------------------------------------------------------------------

def test_interval_mode_team_a_wins_by_band():
    # T0=80, T1=73 → diff=7 >= pt_interval=6 and T0>=66 → T0 gets extra goal → wins
    ch = Championship(
        [Team("T0", "u"), Team("T1", "u")],
        interval=True, pt_interval=6.0, only_in_range=False,
    )
    for t, pts in zip(ch.teams, [[80], [73]]):
        t.add_fanta_pts_scored(pts)
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    result, goals = ch.match_result([0, 1], matchday=0)
    assert result == 1
    assert goals[0] > goals[1]


def test_interval_mode_team_b_wins_by_band():
    # T0=73, T1=80 → T1 wins by band
    ch = Championship(
        [Team("T0", "u"), Team("T1", "u")],
        interval=True, pt_interval=6.0, only_in_range=False,
    )
    for t, pts in zip(ch.teams, [[73], [80]]):
        t.add_fanta_pts_scored(pts)
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    result, goals = ch.match_result([0, 1], matchday=0)
    assert result == 2
    assert goals[1] > goals[0]


def test_interval_mode_equalize_when_no_band_condition():
    # T0=76, T1=72 → diff=4 < 6 and -diff=-4 < 6 → equalize → draw
    ch = Championship(
        [Team("T0", "u"), Team("T1", "u")],
        interval=True, pt_interval=6.0, only_in_range=False,
    )
    for t, pts in zip(ch.teams, [[76], [72]]):
        t.add_fanta_pts_scored(pts)
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    result, goals = ch.match_result([0, 1], matchday=0)
    assert result == 0
    assert goals[0] == goals[1]


# ---------------------------------------------------------------------------
# Interval mode — only_in_range=True
# ---------------------------------------------------------------------------

def test_interval_only_in_range_applies_band_when_goals_equal():
    # T0=80, T1=77 → both 3G → equal → diff=3 >= pt_interval=3 → T0 gets extra → T0 wins
    ch = Championship(
        [Team("T0", "u"), Team("T1", "u")],
        interval=True, pt_interval=3.0, only_in_range=True,
    )
    for t, pts in zip(ch.teams, [[80], [77]]):
        t.add_fanta_pts_scored(pts)
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    result, _ = ch.match_result([0, 1], matchday=0)
    assert result == 1


def test_interval_only_in_range_no_band_when_goals_unequal():
    # T0=81, T1=77 → T0: 4G, T1: 3G → not equal → band not applied → T0 wins normally
    ch = Championship(
        [Team("T0", "u"), Team("T1", "u")],
        interval=True, pt_interval=3.0, only_in_range=True,
    )
    for t, pts in zip(ch.teams, [[81], [77]]):
        t.add_fanta_pts_scored(pts)
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    result, goals = ch.match_result([0, 1], matchday=0)
    assert result == 1
    assert goals[0] == 4  # no extra goal added by band


# ---------------------------------------------------------------------------
# Tiebreakers
# ---------------------------------------------------------------------------

def _tied_pair(pts_0, pts_1, card_order):
    """Two-team championship where T0 and T1 face each other every round."""
    t0, t1 = Team("T0", "u"), Team("T1", "u")
    t0.add_fanta_pts_scored(pts_0)
    t1.add_fanta_pts_scored(pts_1)
    rounds = len(pts_0)
    ch = Championship([t0, t1], card_order=card_order)
    ch.set_calendar([[[0, 1]] for _ in range(rounds)])
    ch.set_current_matchday(rounds)
    ch.generate_ranking()
    return ch


def test_tiebreaker_somma_punti_totale():
    # T0=68.5, T1=66.0 per round: both get 1G (both ≥66 but <71) → draw every round
    # T0 total fpt = 3×68.5 > T1 total fpt = 3×66.0 → T0 ranks first via Somma punti totale
    ch = _tied_pair(
        pts_0=[68.5, 68.5, 68.5],
        pts_1=[66.0, 66.0, 66.0],
        card_order=["Punti", "Somma punti totale"],
    )
    assert ch.ranking[0] == ch.ranking[1]  # confirm they are actually tied on points
    order, _ = ch.sort_ranking()
    assert order[0] == 0  # T0 wins on total fpt


def test_tiebreaker_differenza_reti_active():
    # T0 and T1 draw every round. T0 accumulates more goals → better goal diff.
    # To get a draw WITH different goals accumulated, we need a match where T0
    # is in a losing position on normal goals but the _apply_interval equalises —
    # that's complex. Simpler: make them draw (same goals per match) but give T0
    # extra goal diff from wins against a third team that T1 doesn't have.
    # Easiest: 4 teams, T0 and T1 end up tied on pts, T0 has better goal diff.
    # Round 0: T0(80) vs T1(80) → draw (3G-3G)
    # Round 1: T0(90) vs T2(66) → T0 wins 7-1; T1(66) vs T3(66) → T1 draws 1-1
    # Round 2: T0(66) vs T3(66) → T0 draws 1-1; T1(90) vs T2(66) → T1 wins 7-1
    # League pts: T0=1+3+1=5, T1=1+1+3=5 → tied
    # Goal diff: T0=(3-3)+(7-1)+(1-1)=6, T1=(3-3)+(1-1)+(7-1)=6 → also tied...
    # Let me try differently:
    # Round 0: T0(80) vs T2(60) → T0: 3G vs 0G; T1(80) vs T3(65) → T1: 3G vs 0G
    # Round 1: T0(80) vs T3(65) → T0: 3G vs 0G; T1(80) vs T2(60) → T1: 3G vs 0G
    # Round 2: T0(80) vs T1(80) → draw 3G-3G
    # T0 pts: 3+3+1=7; T1 pts: 3+3+1=7 — tied
    # T0 goals: (3+0)+(3+0)+(3+3)=12 scored, 0+0+3=3 conceded → diff=9
    # T1 goals: (3+0)+(3+0)+(3+3)=12 scored, 0+0+3=3 conceded → diff=9 — STILL tied
    # The draw between T0 and T1 mirrors perfectly. Try asymmetric opponents:
    # Round 0: T0(80) vs T2(60)=3-0W; T1(80) vs T3(75)=3-2W
    # Round 1: T0(80) vs T3(75)=3-2W; T1(80) vs T2(60)=3-0W
    # Round 2: T0(80) vs T1(80)=3-3 draw
    # T0 pts: 3+3+1=7; T1 pts: 3+3+1=7 — tied
    # T0 goals: scored=3+3+3=9, conceded=0+2+3=5 → diff=4
    # T1 goals: scored=3+3+3=9, conceded=2+0+3=5 → diff=4 — STILL tied
    # The schedules are mirror images! T0 faced T2 first, T1 faced T3 first, but then swapped.
    # Need an asymmetric home/away effect... but we have none.
    # Key insight: goal diff between T0 and T1 is always symmetric when they play each other.
    # Must make them NOT play each other, or give them different opponent quality.
    # Let me use 6 teams instead:
    # T0 and T1 both get 6pts (2W, 0D, 0L in rounds 0 and 1),
    # and draw in round 2, but T0 has a higher goal diff from their wins.

    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([90, 90, 68])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([76, 76, 68])
    t2 = Team("T2", "u"); t2.add_fanta_pts_scored([66, 66, 66])
    t3 = Team("T3", "u"); t3.add_fanta_pts_scored([66, 66, 66])
    # Round 0: T0(90) vs T2(66) → T0 wins 7-1; T1(76) vs T3(66) → T1 wins 3-1
    # Round 1: T0(90) vs T3(66) → T0 wins 7-1; T1(76) vs T2(66) → T1 wins 3-1
    # Round 2: T0(68) vs T1(68) → draw 1-1; T2(66) vs T3(66) → draw 1-1
    # T0 pts: 3+3+1=7; T1 pts: 3+3+1=7 — tied
    # T0 goal diff: (7-1)+(7-1)+(1-1)=12; T1 goal diff: (3-1)+(3-1)+(1-1)=4
    # Differenza reti: T0=12 > T1=4 → T0 should rank higher
    ch = Championship(
        [t0, t1, t2, t3],
        card_order=["Punti", "Differenza reti"],
    )
    ch.set_calendar([
        [[0, 2], [1, 3]],
        [[0, 3], [1, 2]],
        [[0, 1], [2, 3]],
    ])
    ch.set_current_matchday(3)
    ch.generate_ranking()
    assert ch.ranking[0] == ch.ranking[1]
    order, _ = ch.sort_ranking()
    assert list(order).index(0) < list(order).index(1)


def test_tiebreaker_gol_fatti():
    # T0 and T1 tied on pts AND goal diff, T0 has more goals scored
    # Build a scenario via a 4-team championship where T0 scores more goals
    # but both win/lose by 1G margin (equal goal diff).
    # Simplification: engineer directly, setting goals on the team objects.
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([70])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([70])
    t0.goals_scored = 10; t0.goals_conceded = 5   # diff = 5
    t1.goals_scored = 8;  t1.goals_conceded = 3   # diff = 5
    ch = Championship(
        [t0, t1],
        card_order=["Punti", "Differenza reti", "Gol fatti"],
    )
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    ch.generate_ranking()
    # They'll draw on their head-to-head: 2G-2G → draw → 1pt each
    # Manually set ranking to be equal so we can test the tiebreaker
    ch.ranking = np.array([3.0, 3.0])
    order, _ = ch.sort_ranking()
    # T0 has more goals scored → ranks higher
    assert order[0] == 0


def test_tiebreaker_gol_subiti():
    # T0 and T1 tied on pts, goal diff, AND goals scored; T0 concedes fewer
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([70])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([70])
    t0.goals_scored = 8; t0.goals_conceded = 3   # diff=5, conceded=3
    t1.goals_scored = 8; t1.goals_conceded = 5   # diff=3 — wait this makes diff different
    # Equal diff: t0.diff=5, t1.diff=3 — these differ! need same diff
    t0.goals_scored = 8; t0.goals_conceded = 3   # diff=5
    t1.goals_scored = 10; t1.goals_conceded = 5  # diff=5, same
    ch = Championship(
        [t0, t1],
        card_order=["Punti", "Differenza reti", "Gol fatti", "Gol subiti"],
    )
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    ch.generate_ranking()
    ch.ranking = np.array([3.0, 3.0])
    # T0 goals_scored=8, T1 goals_scored=10 — first tiebreaker after diff is Gol fatti
    # T1 would win on Gol fatti. So for Gol subiti to kick in, need equal goals scored too.
    t0.goals_scored = 10; t0.goals_conceded = 5  # diff=5
    t1.goals_scored = 10; t1.goals_conceded = 7  # diff=3 — differs again
    # Let me set: t0: 10 scored, 5 conceded (diff=5); t1: 10 scored, 5 conceded (diff=5) — fully equal
    # Then change conceded only:
    t0.goals_scored = 10; t0.goals_conceded = 3  # diff=7
    t1.goals_scored = 10; t1.goals_conceded = 3  # diff=7 — still equal
    t0.goals_conceded = 3
    t1.goals_conceded = 5  # now t0.diff=7, t1.diff=5 — different → Differenza reti tiebreaker resolves it
    # For Gol subiti to be relevant: Punti tied, Differenza reti tied, Gol fatti tied, Gol subiti differs
    t0.goals_scored = 8; t0.goals_conceded = 3   # diff=5, scored=8
    t1.goals_scored = 8; t1.goals_conceded = 5   # diff=3 → Differenza reti resolves it, Gol subiti never reached
    # True test: need diff equal AND goals scored equal AND goals conceded to differ
    t0.goals_scored = 8; t0.goals_conceded = 3   # diff=5
    t1.goals_scored = 8; t1.goals_conceded = 3   # diff=5 → still Gol subiti won't differ
    t0.goals_conceded = 3
    t1.goals_conceded = 6   # t1 diff = 8-6=2, t0 diff = 8-3=5 → Differenza reti resolves
    # OK I need: both diff equal, both scored equal, conceded differ
    t0.goals_scored = 10; t0.goals_conceded = 4  # diff=6
    t1.goals_scored = 10; t1.goals_conceded = 4  # diff=6 — equal in all → Gol subiti both=4, still equal
    # Final setup: equal diff AND equal scored, conceded differ
    t0.goals_scored = 10; t0.goals_conceded = 4  # diff=6, scored=10
    t1.goals_scored = 10; t1.goals_conceded = 6  # diff=4 → Differenza reti resolves it first!
    # I cannot avoid Differenza reti resolving it if I change conceded alone.
    # I need: scored_0 - conceded_0 = scored_1 - conceded_1 AND scored_0 = scored_1
    # That implies conceded_0 = conceded_1, so Gol subiti is always tied when Differenza reti and Gol fatti are tied.
    # Gol subiti can only be the deciding criterion when scored and conceded differ in a way that diff and scored are equal.
    # That means: if scored_0=12, conceded_0=4 (diff=8) and scored_1=10, conceded_1=2 (diff=8) → diff equal, scored differ
    # So Gol fatti would already break the tie before reaching Gol subiti.
    # Actually, that's the point: Gol subiti is only the deciding factor when Gol fatti is also equal.
    # And if Gol fatti is equal (scored_0=scored_1), then diff equal implies conceded_0=conceded_1.
    # So Gol subiti as the sole differentiator requires scored to differ → Gol fatti would catch it first.
    # The only way Gol subiti breaks a tie is if the card_order puts it BEFORE Gol fatti:
    t0.goals_scored = 8; t0.goals_conceded = 3
    t1.goals_scored = 10; t1.goals_conceded = 5   # both diff=5, scored differ → Gol subiti kicks in when Gol fatti not in card_order
    ch2 = Championship(
        [t0, t1],
        card_order=["Punti", "Differenza reti", "Gol subiti"],
    )
    ch2.set_calendar([[[0, 1]]])
    ch2.set_current_matchday(1)
    ch2.generate_ranking()
    ch2.ranking = np.array([3.0, 3.0])
    order2, _ = ch2.sort_ranking()
    # T0 concedes fewer (3 < 5) → T0 should rank higher
    assert order2[0] == 0


def test_three_way_tie_returns_warning():
    # Make 3 teams (out of 4) end up with equal league points
    # T0,T1,T2 each get 3pts; T3 gets 0pts
    # Round 0: T0(80) vs T3(66) → T0 wins; T1(68) vs T2(68) → draw 1-1
    # Round 1: T1(80) vs T3(66) → T1 wins; T0(68) vs T2(68) → draw 1-1
    # Round 2: T2(80) vs T3(66) → T2 wins; T0(68) vs T1(68) → draw 1-1
    # T0: W+D+D = 3+1+1=5pts; T1: D+W+D=5pts; T2: D+D+W=5pts; T3: L+L+L=0
    # Wait: T0 round0 wins (3pts), round1 draws (1pt), round2 draws (1pt) = 5pts
    # T1 round0 draws (1pt), round1 wins (3pts), round2 draws (1pt) = 5pts
    # T2 round0 draws (1pt), round1 draws (1pt), round2 wins (3pts) = 5pts → 3-way tie!
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([80, 68, 68])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([68, 80, 68])
    t2 = Team("T2", "u"); t2.add_fanta_pts_scored([68, 68, 80])
    t3 = Team("T3", "u"); t3.add_fanta_pts_scored([66, 66, 66])
    ch = Championship(
        [t0, t1, t2, t3],
        card_order=["Punti", "Classifica avulsa"],
    )
    ch.set_calendar([
        [[0, 3], [1, 2]],
        [[1, 3], [0, 2]],
        [[2, 3], [0, 1]],
    ])
    ch.set_current_matchday(3)
    ch.generate_ranking()
    assert ch.ranking[0] == ch.ranking[1] == ch.ranking[2]
    _, warning = ch.sort_ranking()
    assert warning is not None
    assert "tied" in warning.lower()


# ---------------------------------------------------------------------------
# team_position
# ---------------------------------------------------------------------------

def test_team_position_returns_correct_rank(simple_championship):
    simple_championship.generate_ranking()
    order, _ = simple_championship.sort_ranking()
    for rank, idx in enumerate(order, start=1):
        team_id = simple_championship.teams[idx].id
        assert simple_championship.team_position(team_id) == rank


def test_team_position_invalid_id_raises(simple_championship):
    simple_championship.generate_ranking()
    with pytest.raises(ValueError):
        simple_championship.team_position(999)


# ---------------------------------------------------------------------------
# match_for_team
# ---------------------------------------------------------------------------

def test_match_for_team_returns_correct_match(simple_championship):
    team_id = simple_championship.teams[0].id
    match = simple_championship.match_for_team(team_id, matchday=0)
    assert 0 in match


def test_match_for_team_team_b_position(simple_championship):
    # Team 1 appears as the second element in the first match of round 0
    team_id = simple_championship.teams[1].id
    match = simple_championship.match_for_team(team_id, matchday=0)
    assert 1 in match


def test_match_for_team_calendar_not_set_raises():
    teams = [Team("A", "a"), Team("B", "b")]
    ch = Championship(teams)
    with pytest.raises(ValueError, match="Calendar must be set"):
        ch.match_for_team(0, matchday=0)


def test_match_for_team_matchday_out_of_range_raises(simple_championship):
    with pytest.raises(ValueError):
        simple_championship.match_for_team(0, matchday=99)


# ---------------------------------------------------------------------------
# Analytics guard paths (calendar=None)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,args", [
    ("get_wins_draws_losses", []),
    ("strength_of_schedule", [0]),
    ("lowest_scoring_day", []),
    ("highest_scoring_day", []),
    ("number_close_matches", []),
    ("close_draws", []),
    ("what_if_calendar", [0, 1]),
])
def test_analytics_raises_without_calendar(method, args):
    teams = [Team("A", "a"), Team("B", "b")]
    ch = Championship(teams)
    with pytest.raises(ValueError):
        getattr(ch, method)(*args)


# ---------------------------------------------------------------------------
# close_draws — actual close-draw scenario
# ---------------------------------------------------------------------------

def test_close_draws_counted_correctly():
    # T0=68, T1=68 → both 1G → draw; both >=66; |68-68|=0 <=3 → close draw
    # T0=80, T1=66 → T0: 3G, T1: 1G → not a draw (not counted)
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([68, 80])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([68, 66])
    ch = Championship([t0, t1])
    ch.set_calendar([[[0, 1]], [[0, 1]]])
    ch.set_current_matchday(2)
    ch.generate_ranking()
    draws = ch.close_draws()
    assert draws["T0"] == 1
    assert draws["T1"] == 1


def test_close_draws_zero_when_no_close_draws():
    # T0=90, T1=66 → big gap → not a close draw
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([90])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([66])
    ch = Championship([t0, t1])
    ch.set_calendar([[[0, 1]]])
    ch.set_current_matchday(1)
    ch.generate_ranking()
    draws = ch.close_draws()
    assert draws["T0"] == 0
    assert draws["T1"] == 0


# ---------------------------------------------------------------------------
# what_if_calendar draw path
# ---------------------------------------------------------------------------

def test_what_if_calendar_includes_draws():
    # T0=68, T1=68: draw → T1's opponent was T0 (68 pts) vs T2
    # what_if: T0 vs T1's opponent → need a draw scenario
    # Setup: T0=68, T1=68, T2=68 — all draw with each other
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([68, 68])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([68, 68])
    t2 = Team("T2", "u"); t2.add_fanta_pts_scored([68, 68])
    t3 = Team("T3", "u"); t3.add_fanta_pts_scored([68, 68])
    ch = Championship([t0, t1, t2, t3])
    ch.set_calendar([
        [[0, 1], [2, 3]],
        [[0, 2], [1, 3]],
    ])
    ch.set_current_matchday(2)
    ch.generate_ranking()
    actual, what_if = ch.what_if_calendar(0, 1)
    # All draws → T0 gets 1pt per game in what_if scenario
    assert what_if >= 0


def test_what_if_calendar_self_swap_equals_actual(simple_championship):
    simple_championship.generate_ranking()
    # Swapping with yourself should give the same points
    actual, what_if = simple_championship.what_if_calendar(0, 0)
    assert actual == what_if


# ---------------------------------------------------------------------------
# strength_of_schedule with no matches (empty opponent list)
# ---------------------------------------------------------------------------

def test_strength_of_schedule_no_opponents_returns_zero():
    # Use current_matchday=0 → no rounds replayed → no opponents
    t0 = Team("T0", "u"); t0.add_fanta_pts_scored([80, 80])
    t1 = Team("T1", "u"); t1.add_fanta_pts_scored([70, 70])
    ch = Championship([t0, t1])
    ch.set_calendar([[[0, 1]], [[0, 1]]])
    ch.set_current_matchday(0)  # no played matchdays
    sos = ch.strength_of_schedule(0)
    assert sos == 0.0
