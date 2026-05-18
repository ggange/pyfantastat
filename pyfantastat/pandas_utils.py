"""Optional pandas conversion helpers for pyfantastat data structures.

Requires pandas (``pip install pyfantastat[pandas]``).  All helpers do a lazy
import so the core library remains usable without pandas installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    from pyfantastat.formazioni import (
        TeamRoster,
        TopFormationResult,
    )
    from pyfantastat.io.models import FormazioniMatchday


def _pd() -> "type[pd]":
    try:
        import pandas
        return pandas
    except ImportError:
        raise ImportError(
            "pandas is required for these helpers: pip install pyfantastat[pandas]"
        )


def roster_to_dataframe(roster: "TeamRoster") -> "pd.DataFrame":
    """Convert a :class:`~pyfantastat.formazioni.TeamRoster` to a DataFrame.

    One row per player. Columns: ``name``, ``ruolo``, ``apps``,
    ``mean_voto``, ``std_voto``, ``mean_fantavoto``, ``std_fantavoto``.
    """
    from pyfantastat.formazioni import player_scoring_stats

    pd = _pd()
    rows = []
    for record in roster.players.values():
        stats = player_scoring_stats(record)
        apps = sum(1 for _, fv in record.matchdays.values() if fv > 0)
        rows.append({
            "name": record.name,
            "ruolo": record.ruolo or "?",
            "apps": apps,
            "mean_voto": round(stats["mean_voto"], 2),
            "std_voto": round(stats["std_voto"], 2),
            "mean_fantavoto": round(stats["mean_fantavoto"], 2),
            "std_fantavoto": round(stats["std_fantavoto"], 2),
        })
    return pd.DataFrame(rows)


def rosters_to_dataframe(rosters: "dict[str, TeamRoster]") -> "pd.DataFrame":
    """Convert all rosters to a single stacked DataFrame.

    Same columns as :func:`roster_to_dataframe` plus a leading ``team`` column.
    """
    pd = _pd()
    frames = []
    for roster in rosters.values():
        df = roster_to_dataframe(roster)
        df.insert(0, "team", roster.team_name)
        frames.append(df)
    if not frames:
        return pd.DataFrame(
            columns=["team", "name", "ruolo", "apps",
                     "mean_voto", "std_voto", "mean_fantavoto", "std_fantavoto"]
        )
    return pd.concat(frames, ignore_index=True)


def top_formation_to_dataframe(result: "TopFormationResult") -> "pd.DataFrame":
    """Convert a :class:`~pyfantastat.formazioni.TopFormationResult` to a DataFrame.

    One row per player (11 rows). Columns: ``name``, ``ruolo``, ``efv``.
    Index is 1-based.
    """
    pd = _pd()
    rows = [{"name": p.name, "ruolo": p.ruolo, "efv": p.efv} for p in result.players]
    df = pd.DataFrame(rows)
    df.index = pd.RangeIndex(1, len(df) + 1)
    return df


def matchday_to_dataframe(matchday: "FormazioniMatchday") -> "pd.DataFrame":
    """Convert a :class:`~pyfantastat.io.models.FormazioniMatchday` to a DataFrame.

    One row per player across all teams in the matchday.
    Columns: ``team``, ``name``, ``ruolo``, ``voto``, ``fantavoto``.
    """
    pd = _pd()
    _COLS = ["team", "name", "ruolo", "voto", "fantavoto"]
    rows = []
    for team in matchday.teams:
        for player in team.players:
            rows.append({
                "team": team.team_name,
                "name": player.name,
                "ruolo": player.ruolo or "?",
                "voto": player.voto,
                "fantavoto": player.fantavoto,
            })
    return pd.DataFrame(rows, columns=_COLS) if rows else pd.DataFrame(columns=_COLS)
