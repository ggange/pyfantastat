from pyfantastat.team import Team


def test_team_init():
    t = Team("Juventus", "Alice")
    assert t.team_name == "Juventus"
    assert t.user_name == "Alice"
    assert t.fanta_pts_scored == []
    assert t.fanta_pts_against == []
    assert t.goals_scored == 0
    assert t.goals_conceded == 0
    assert t.id is None


def test_add_fanta_pts_scored():
    t = Team("A", "B")
    t.add_fanta_pts_scored([70.0, 80.5, 65.0])
    assert t.fanta_pts_scored == [70.0, 80.5, 65.0]


def test_add_fanta_pts_against():
    t = Team("A", "B")
    t.add_fanta_pts_against([60.0, 75.0])
    assert t.fanta_pts_against == [60.0, 75.0]


def test_add_goals():
    t = Team("A", "B")
    t.add_goals(3, 1)
    assert t.goals_scored == 3
    assert t.goals_conceded == 1
    t.add_goals(1, 2)
    assert t.goals_scored == 4
    assert t.goals_conceded == 3


def test_add_color():
    t = Team("A", "B")
    t.add_color("red")
    assert t.color == "red"


def test_set_id():
    t = Team("A", "B")
    t._set_id(5)
    assert t.id == 5
