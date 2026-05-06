from pathlib import Path
import pytest
from pyfantastat.io import load_calendar_xlsx, CalendarData

FIXTURE = Path(__file__).parent / "fixtures" / "sample_calendar.xlsx"


def test_returns_calendar_data():
    data = load_calendar_xlsx(FIXTURE)
    assert isinstance(data, CalendarData)


def test_league_name():
    data = load_calendar_xlsx(FIXTURE)
    assert data.league_name == "TestLeague"


def test_team_names_sorted():
    data = load_calendar_xlsx(FIXTURE)
    assert data.team_names == sorted(data.team_names)
    assert set(data.team_names) == {"Alpha", "Beta", "Gamma", "Delta"}


def test_team_points_populated():
    data = load_calendar_xlsx(FIXTURE)
    for name, pts in data.team_points.items():
        assert len(pts) > 0, f"{name} has no points"


def test_alpha_points_correct():
    data = load_calendar_xlsx(FIXTURE)
    # round 1: Alpha scored 80; round 2: Alpha scored 72
    assert data.team_points["Alpha"] == [80.0, 72.0]


def test_calendar_structure():
    data = load_calendar_xlsx(FIXTURE)
    # 2 matchdays, each with 2 matches of 2 team indices
    assert len(data.calendar) == 2
    for day in data.calendar:
        for match in day:
            assert len(match) == 2
            assert all(isinstance(idx, int) for idx in match)


def test_match_count():
    data = load_calendar_xlsx(FIXTURE)
    assert data.match_count == 2


def test_current_matchday_detected():
    data = load_calendar_xlsx(FIXTURE)
    # Both matchdays have non-zero scores → current = last
    assert data.current_matchday == 2
