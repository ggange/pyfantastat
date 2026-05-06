import pytest
from pyfantastat.team import Team
from pyfantastat.championship import Championship


def _make_championship():
    # 4 teams, 3 rounds, fully deterministic results
    # round 0: T0(80) vs T1(70) → T0 wins; T2(75) vs T3(66) → T2 wins
    # round 1: T0(72) vs T2(68) → T0 wins; T1(76) vs T3(71) → T1 wins
    # round 2: T0(74) vs T3(69) → T0 wins; T1(73) vs T2(77) → T2 wins
    points = [[80, 72, 74], [70, 76, 73], [75, 68, 77], [66, 71, 69]]
    teams = []
    for i, pts in enumerate(points):
        t = Team(f"Team{i}", f"User{i}")
        t.add_fanta_pts_scored(pts)
        teams.append(t)
    ch = Championship(teams, card_order=["Punti", "Differenza reti"])
    ch.set_calendar([
        [[0, 1], [2, 3]],
        [[0, 2], [1, 3]],
        [[0, 3], [1, 2]],
    ])
    ch.generate_ranking()
    return ch


def test_get_wins_draws_losses_counts():
    ch = _make_championship()
    wdl = ch.get_wins_draws_losses()
    # T0 wins all 3
    assert wdl["Team0"]["W"] == 3
    assert wdl["Team0"]["D"] == 0
    assert wdl["Team0"]["L"] == 0
    # T2 wins 2 (round0, round2), loses 1 (round1)
    assert wdl["Team2"]["W"] == 2
    assert wdl["Team2"]["L"] == 1


def test_get_wins_draws_losses_all_teams_present():
    ch = _make_championship()
    wdl = ch.get_wins_draws_losses()
    assert len(wdl) == 4
    for name, counts in wdl.items():
        assert counts["W"] + counts["D"] + counts["L"] == 3


def test_total_fpt_ranking_ordered():
    ch = _make_championship()
    ranking = ch.total_fpt_ranking()
    totals = [total for _, total in ranking]
    assert totals == sorted(totals, reverse=True)
    assert len(ranking) == 4


def test_strength_of_schedule_returns_float():
    ch = _make_championship()
    sos = ch.strength_of_schedule(0)
    assert isinstance(sos, float)
    assert sos > 0


def test_highest_lowest_scoring_day():
    ch = _make_championship()
    lo_day, lo_score = ch.lowest_scoring_day()
    hi_day, hi_score = ch.highest_scoring_day()
    assert lo_score <= hi_score
    assert 0 <= lo_day < 3
    assert 0 <= hi_day < 3


def test_number_close_matches_subset_of_total():
    ch = _make_championship()
    close = ch.number_close_matches()
    draws = ch.close_draws()
    for name in close:
        assert draws.get(name, 0) <= close[name]


def test_what_if_calendar_returns_ints():
    ch = _make_championship()
    actual, what_if = ch.what_if_calendar(0, 1)
    assert isinstance(actual, (int, float))
    assert isinstance(what_if, (int, float))


def test_prizes_has_expected_keys():
    ch = _make_championship()
    p = ch.prizes()
    assert "highest" in p
    assert "lowest" in p


def test_from_calendar_data_factory():
    from pyfantastat.io.models import CalendarData
    from pyfantastat.championship import Championship

    data = CalendarData(
        league_name="Test League",
        team_names=["A", "B", "C", "D"],
        user_names=["u1", "u2", "u3", "u4"],
        team_points={
            "A": [80.0, 72.0, 74.0],
            "B": [70.0, 76.0, 73.0],
            "C": [75.0, 68.0, 77.0],
            "D": [66.0, 71.0, 69.0],
        },
        match_count=3,
        calendar=[
            [[0, 1], [2, 3]],
            [[0, 2], [1, 3]],
            [[0, 3], [1, 2]],
        ],
        current_matchday=3,
        first_matchday_serie_a=1,
        last_matchday_serie_a=3,
    )
    ch = Championship.from_calendar_data(data)
    assert len(ch.teams) == 4
    assert ch.teams[0].team_name == "A"
    assert ch.teams[0].fanta_pts_scored == [80.0, 72.0, 74.0]
    ch.generate_ranking()
    order, _ = ch.sort_ranking()
    assert len(order) == 4
