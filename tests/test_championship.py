import pytest
import numpy as np
from pyfantastat.team import Team
from pyfantastat.championship import Championship


def test_calendar_initialized_to_none():
    teams = [Team(f"T{i}", f"U{i}") for i in range(4)]
    ch = Championship(teams)
    assert ch.calendar is None


def test_generate_ranking_raises_without_calendar():
    teams = [Team(f"T{i}", f"U{i}") for i in range(4)]
    ch = Championship(teams)
    with pytest.raises(ValueError):
        ch.generate_ranking()


def test_card_order_none_does_not_crash(simple_championship):
    teams = simple_championship.teams
    ch = Championship(teams)
    ch.set_calendar([[[0, 1], [2, 3]], [[0, 2], [1, 3]], [[0, 3], [1, 2]]])
    ch.generate_ranking()
    order, msg = ch.sort_ranking()
    assert len(order) == 4


def test_head_to_head_tiebreaker_uses_correct_indices():
    """Head-to-head must award points to the right teams, not always [0] and [1].

    Fixture (default thresholds: >=66=1G, >=71=2G, >=76=3G):
      round 0 ([0,1],[2,3]): T0(72=2G) vs T1(68=1G) → T0 wins;  T2(68=1G) vs T3(76=3G) → T3 wins
      round 1 ([0,2],[1,3]): T0(76=3G) vs T2(68=1G) → T0 wins;  T1(76=3G) vs T3(68=1G) → T1 wins
      round 2 ([0,3],[1,2]): T0(66=1G) vs T3(66=1G) → Draw;      T1(68=1G) vs T2(76=3G) → T2 wins

    League points: T0=7, T1=3, T2=3, T3=4
    T1 and T2 tied; T2 beat T1 head-to-head → T2 must rank above T1.
    """
    points = [
        [72, 76, 66],
        [68, 76, 68],
        [68, 68, 76],
        [76, 68, 66],
    ]
    teams = []
    for i, pts in enumerate(points):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(pts)
        teams.append(t)

    ch = Championship(
        teams,
        card_order=["Punti", "Classifica avulsa", "Differenza reti"],
    )
    calendar = [
        [[0, 1], [2, 3]],
        [[0, 2], [1, 3]],
        [[0, 3], [1, 2]],
    ]
    ch.set_calendar(calendar)
    ch.generate_ranking()

    assert ch.ranking[0] == 7
    assert ch.ranking[1] == 3
    assert ch.ranking[2] == 3
    assert ch.ranking[3] == 4

    order, _ = ch.sort_ranking()
    ranked_teams = list(order)
    assert ranked_teams.index(2) < ranked_teams.index(1), (
        f"T2 should rank above T1 after head-to-head, got order {ranked_teams}"
    )


def test_generate_ranking_idempotent(simple_championship):
    """Calling generate_ranking() twice must yield identical results."""
    simple_championship.generate_ranking()
    goals_scored_first = [t.goals_scored for t in simple_championship.teams]
    ranking_first = simple_championship.ranking.copy()

    simple_championship.generate_ranking()
    goals_scored_second = [t.goals_scored for t in simple_championship.teams]

    assert list(simple_championship.ranking) == list(ranking_first)
    assert goals_scored_first == goals_scored_second


# ---------------------------------------------------------------------------
# ranking_at_matchday tests
# ---------------------------------------------------------------------------


def test_ranking_at_matchday_zero(simple_championship):
    """Before any match, all teams have 0 points."""
    result = simple_championship.ranking_at_matchday(0)
    assert np.all(result == 0)
    assert result.shape == (4,)


def test_ranking_at_matchday_partial(simple_championship):
    """Points after matchday 1 match a manual re-run up to that point."""
    result = simple_championship.ranking_at_matchday(1)
    # round 0: T0(80) vs T1(70) → T0 wins; T2(75) vs T3(66) → T2 wins
    assert result[0] == 3
    assert result[2] == 3
    assert result[1] == 0
    assert result[3] == 0


def test_ranking_at_matchday_full(simple_championship):
    """At current_matchday, result matches self.ranking after generate_ranking()."""
    simple_championship.set_current_matchday(3)
    simple_championship.generate_ranking()
    expected = simple_championship.ranking.copy()

    result = simple_championship.ranking_at_matchday(3)
    np.testing.assert_array_equal(result, expected)


def test_ranking_at_matchday_does_not_mutate(simple_championship):
    """ranking_at_matchday must not modify self.ranking or team goals."""
    simple_championship.generate_ranking()
    ranking_before = simple_championship.ranking.copy()
    goals_before = [t.goals_scored for t in simple_championship.teams]

    simple_championship.ranking_at_matchday(2)

    np.testing.assert_array_equal(simple_championship.ranking, ranking_before)
    assert [t.goals_scored for t in simple_championship.teams] == goals_before


def test_ranking_at_matchday_sort_flag(simple_championship):
    """sort=True returns (ranking, sorted_indices) with descending order."""
    ranking, sorted_indices = simple_championship.ranking_at_matchday(3, sort=True)
    assert isinstance(ranking, np.ndarray)
    assert isinstance(sorted_indices, np.ndarray)
    # sorted_indices must produce a non-increasing sequence of points
    assert all(
        ranking[sorted_indices[i]] >= ranking[sorted_indices[i + 1]]
        for i in range(len(sorted_indices) - 1)
    )
    # first entry is the team with the most points
    assert ranking[sorted_indices[0]] == ranking.max()


def test_ranking_at_matchday_out_of_range(simple_championship):
    """Negative or too-large matchday raises ValueError."""
    with pytest.raises(ValueError):
        simple_championship.ranking_at_matchday(-1)
    with pytest.raises(ValueError):
        simple_championship.ranking_at_matchday(999)


def test_ranking_at_matchday_no_calendar():
    """Raises ValueError when calendar is not set."""
    teams = [Team(f"T{i}", f"U{i}") for i in range(4)]
    ch = Championship(teams)
    with pytest.raises(ValueError):
        ch.ranking_at_matchday(0)
