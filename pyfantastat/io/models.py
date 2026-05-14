"""Data models for parsed league files."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class FormazioniPlayer:
    """One player entry inside a Formazioni matchday file."""

    name: str
    """Player surname / display name (trailing ``*`` transfer marker stripped)."""

    ruolo: Optional[str]
    """Role code: ``"P"`` (GK), ``"D"`` (DEF), ``"C"`` (MID), ``"A"`` (ATT), or ``None``."""

    voto: float
    """Match grade on the 0-10 scale; ``0.0`` when the player did not participate."""

    fantavoto: float
    """Fantasy points for the matchday; ``0.0`` when the player did not participate."""


@dataclass
class FormazioniTeam:
    """One fantasy team's data as parsed from a Formazioni matchday file."""

    team_name: str
    """Fantasy team name, taken from the white-on-black header cell."""

    totale: float
    """Total fantapoints for the matchday, from the ``TOTALE: XX,XX`` cell."""

    players: list[FormazioniPlayer] = field(default_factory=list)
    """All players listed (starters and bench); bench players have voto/fantavoto == 0."""


@dataclass
class FormazioniMatchday:
    """Parsed content of a single Formazioni Excel file (one league matchday)."""

    giornata: int
    """1-based league matchday number extracted from the file title."""

    teams: list[FormazioniTeam] = field(default_factory=list)
    """All teams present in the file (typically 8 for a complete matchday)."""
