import pytest
from pyfantastat.team import Team
from pyfantastat.championship import Championship


@pytest.fixture
def four_teams():
    # Points engineered so round outcomes are deterministic:
    # round 0: T0=80, T1=70, T2=75, T3=66 → T0>T1, T2>T3
    # round 1: T0=72, T2=68, T1=76, T3=71 → T0>T2, T1>T3
    # round 2: T0=74, T3=69, T1=73, T2=77 → T0>T3, T2>T1
    points = [[80, 72, 74], [70, 76, 73], [75, 68, 77], [66, 71, 69]]
    teams = []
    for i, pts in enumerate(points):
        t = Team(f"Team{i}", f"User{i}")
        t.add_fanta_pts_scored(pts)
        teams.append(t)
    return teams


@pytest.fixture
def simple_championship(four_teams):
    ch = Championship(
        four_teams,
        card_order=["Punti", "Classifica avulsa", "Differenza reti"],
    )
    calendar = [
        [[0, 1], [2, 3]],
        [[0, 2], [1, 3]],
        [[0, 3], [1, 2]],
    ]
    ch.set_calendar(calendar)
    return ch
