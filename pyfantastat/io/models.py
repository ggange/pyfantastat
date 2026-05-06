"""Data models for parsed league files."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CalendarData:
    """Parsed representation of a fantasy football league calendar.

    Typically produced by :func:`pyfantastat.io.load_calendar_xlsx`.
    """

    league_name: Optional[str]
    """Human-readable league name extracted from the workbook, or ``None``."""

    team_names: list[str]
    """Sorted list of all team names found in the calendar."""

    user_names: list[str]
    """List of team-owner names, parallel to :attr:`team_names`."""

    team_points: dict[str, list[float]]
    """Mapping of team name → list of fantapoints per matchday (calendar order)."""

    match_count: int
    """Total number of matchdays in the calendar."""

    calendar: list[list[list[int]]]
    """Nested structure: ``calendar[matchday][match] = [team_idx_a, team_idx_b]``."""

    current_matchday: Optional[int]
    """The most recent completed matchday number (1-based league day), or ``None``."""

    first_matchday_serie_a: Optional[int]
    """Lowest Serie A matchday number referenced in the calendar, or ``None``."""

    last_matchday_serie_a: Optional[int]
    """Highest Serie A matchday number referenced in the calendar, or ``None``."""
