"""Analytics for Formazioni data: roster aggregation, player stats, best lineup.

Typical usage::

    from pyfantastat.io.formazioni import load_formazioni_dir
    from pyfantastat.formazioni import (
        build_team_rosters, player_scoring_stats,
        validate_formazioni, top_formation,
    )

    data = load_formazioni_dir("path/to/formazioni/")
    rosters = build_team_rosters(data)
    result = top_formation(rosters["My Team"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyfantastat.io.models import CalendarData, FormazioniMatchday


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PlayerRecord:
    """Aggregated history for one player across multiple Formazioni matchdays."""

    name: str
    """Player display name (as found in the first file that mentions them)."""

    ruolo: str | None
    """Role code (``"P"``, ``"D"``, ``"C"``, ``"A"``), or ``None`` if unknown."""

    matchdays: dict[int, tuple[float, float]] = field(default_factory=dict)
    """Per-matchday data: giornata (1-based) → ``(voto, fantavoto)``."""


@dataclass
class TeamRoster:
    """Aggregated player data for one fantasy team across all loaded matchdays."""

    team_name: str
    """Fantasy team name (original case from the first file that mentioned it)."""

    players: dict[str, PlayerRecord] = field(default_factory=dict)
    """Mapping of normalised player name → :class:`PlayerRecord`."""


@dataclass
class TopFormationPlayer:
    """One player in the selected best-eleven lineup."""

    name: str
    ruolo: str
    efv: float
    """Expected fantavoto (Bayesian shrinkage-adjusted)."""


@dataclass
class TopFormationResult:
    """Output of :func:`top_formation`."""

    formation: tuple[int, int, int]
    """Selected formation as ``(n_def, n_mid, n_att)``."""

    players: list[TopFormationPlayer]
    """Exactly 11 players, ordered GK → DEF → MID → ATT."""

    total_efv: float
    """Sum of EFV scores for the selected 11."""


@dataclass
class ValidationIssue:
    """Score mismatch between a Formazioni file and the calendar."""

    giornata: int
    team_name: str
    calendar_score: float
    formazioni_score: float

    @property
    def delta(self) -> float:
        return abs(self.formazioni_score - self.calendar_score)


@dataclass
class FormazioniValidation:
    """Result of :func:`validate_formazioni`."""

    ok: bool
    """``True`` when there are no issues, no unmatched teams, and no gaps."""

    issues: list[ValidationIssue] = field(default_factory=list)
    """Score mismatches exceeding *tol*."""

    unmatched_teams: list[tuple[int, str]] = field(default_factory=list)
    """``(giornata, team_name)`` pairs not recognised in the calendar."""

    missing_matchdays: list[int] = field(default_factory=list)
    """Giornate in ``[1, current_matchday]`` that have no Formazioni file."""


# ---------------------------------------------------------------------------
# Roster building
# ---------------------------------------------------------------------------

def build_team_rosters(
    data: dict[int, FormazioniMatchday],
) -> dict[str, TeamRoster]:
    """Aggregate per-matchday Formazioni data into per-team player histories.

    :param data: Mapping returned by
        :func:`~pyfantastat.io.formazioni.load_formazioni_dir` or built manually.
    :returns: Mapping of normalised team name → :class:`TeamRoster`.
    """
    rosters: dict[str, TeamRoster] = {}  # normalised_name → TeamRoster

    for giornata, matchday in sorted(data.items()):
        for fmt_team in matchday.teams:
            norm_team = fmt_team.team_name.strip().lower()
            if norm_team not in rosters:
                rosters[norm_team] = TeamRoster(team_name=fmt_team.team_name)
            roster = rosters[norm_team]

            for player in fmt_team.players:
                norm_player = player.name.strip().lower()
                if norm_player not in roster.players:
                    roster.players[norm_player] = PlayerRecord(
                        name=player.name,
                        ruolo=player.ruolo,
                    )
                record = roster.players[norm_player]
                # Prefer a non-None ruolo if we've seen one
                if record.ruolo is None and player.ruolo is not None:
                    record.ruolo = player.ruolo
                record.matchdays[giornata] = (player.voto, player.fantavoto)

    return rosters


# ---------------------------------------------------------------------------
# Player scoring stats
# ---------------------------------------------------------------------------

def player_scoring_stats(
    record: PlayerRecord,
    n_matchdays: int | None = None,
) -> dict[str, float]:
    """Summary statistics for one player's scoring history.

    Only matchdays where the player actually participated (voto or fantavoto > 0)
    are counted, consistent with how ``team_scoring_stats`` excludes zero rounds.

    :param n_matchdays: If given, only giornate ≤ n_matchdays are considered.
    :returns: ``{"mean_voto", "std_voto", "mean_fantavoto", "std_fantavoto"}``.
    """
    votos: list[float] = []
    fantavotos: list[float] = []

    for giornata, (v, fv) in record.matchdays.items():
        if n_matchdays is not None and giornata > n_matchdays:
            continue
        if v > 0 or fv > 0:
            votos.append(v)
            fantavotos.append(fv)

    def _stats(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return 0.0, 0.0
        a = np.asarray(vals, dtype=float)
        return float(np.mean(a)), float(np.std(a))

    mv, sv = _stats(votos)
    mf, sf = _stats(fantavotos)
    return {
        "mean_voto":       mv,
        "std_voto":        sv,
        "mean_fantavoto":  mf,
        "std_fantavoto":   sf,
    }


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def validate_formazioni(
    data: dict[int, FormazioniMatchday],
    calendar_data: CalendarData,
    tol: float = 0.5,
) -> FormazioniValidation:
    """Cross-check Formazioni team totals against scores stored in the calendar.

    :param data: Loaded Formazioni matchdays.
    :param calendar_data: Parsed calendar (from
        :func:`~pyfantastat.io.load_calendar_xlsx`).
    :param tol: Maximum absolute difference before flagging a mismatch.
    :returns: :class:`FormazioniValidation` describing any discrepancies.
    """
    # Build a normalised lookup for calendar team names
    cal_norm: dict[str, str] = {
        name.strip().lower(): name for name in calendar_data.team_names
    }

    issues: list[ValidationIssue] = []
    unmatched: list[tuple[int, str]] = []

    current = calendar_data.current_matchday or 0

    for giornata, matchday in sorted(data.items()):
        if giornata > current:
            continue  # calendar hasn't recorded this matchday yet — skip
        idx = giornata - 1  # 0-based index into team_points
        for fmt_team in matchday.teams:
            norm = fmt_team.team_name.strip().lower()
            cal_name = cal_norm.get(norm)
            if cal_name is None:
                unmatched.append((giornata, fmt_team.team_name))
                continue
            pts_list = calendar_data.team_points.get(cal_name, [])
            if idx >= len(pts_list):
                continue  # matchday not in calendar range
            cal_score = pts_list[idx]
            if abs(fmt_team.totale - cal_score) > tol:
                issues.append(ValidationIssue(
                    giornata=giornata,
                    team_name=fmt_team.team_name,
                    calendar_score=cal_score,
                    formazioni_score=fmt_team.totale,
                ))

    # Find missing matchdays: giornate in [1, current_matchday] with no file
    missing = [g for g in range(1, current + 1) if g not in data]

    ok = not issues and not unmatched and not missing
    return FormazioniValidation(
        ok=ok,
        issues=issues,
        unmatched_teams=unmatched,
        missing_matchdays=missing,
    )


# ---------------------------------------------------------------------------
# Top formation
# ---------------------------------------------------------------------------

# Valid (n_def, n_mid, n_att) formations — standard Fantacalcio module system
_VALID_FORMATIONS: list[tuple[int, int, int]] = [
    (3, 5, 2),
    (3, 4, 3),
    (4, 5, 1),
    (4, 4, 2),
    (4, 3, 3),
    (5, 3, 2),
    (5, 4, 1),
]

_ROLE_ORDER = ("P", "D", "C", "A")


def _compute_efv(
    record: PlayerRecord,
    role_prior: float,
    shrinkage_k: float,
) -> float:
    """Bayesian shrinkage EFV for one player (port of fantakings k=15 formula)."""
    non_zero = [fv for _, fv in record.matchdays.values() if fv > 0]
    n = len(non_zero)
    sample_mean = float(np.mean(non_zero)) if n > 0 else 0.0
    return (n * sample_mean + shrinkage_k * role_prior) / (n + shrinkage_k)


def top_formation(
    roster: TeamRoster,
    shrinkage_k: float = 15.0,
) -> TopFormationResult:
    """Select the best 11-player lineup from *roster* using EFV scoring.

    Players are scored with Bayesian shrinkage: a player's expected fantavoto
    is pulled toward the role-average prior when they have few appearances.
    The algorithm tests all seven standard Fantacalcio formations and returns
    the one with the highest combined EFV.

    :param roster: :class:`TeamRoster` produced by :func:`build_team_rosters`.
    :param shrinkage_k: Shrinkage constant *k* (default 15, matching fantakings).
    :returns: :class:`TopFormationResult` with the selected 11 and total EFV.
    """
    # Group players by role
    by_role: dict[str, list[PlayerRecord]] = {"P": [], "D": [], "C": [], "A": []}
    for record in roster.players.values():
        role = record.ruolo or "C"  # default unknown to MID
        if role in by_role:
            by_role[role].append(record)

    # Role priors: mean sample-mean over players with ≥3 appearances; fall back to overall
    def _role_prior(role: str) -> float:
        candidates = [
            float(np.mean([fv for _, fv in r.matchdays.values() if fv > 0]))
            for r in by_role[role]
            if sum(1 for _, fv in r.matchdays.values() if fv > 0) >= 3
        ]
        if len(candidates) >= 2:
            return float(np.mean(candidates))
        # Fall back to overall prior across all roles
        all_means = [
            float(np.mean([fv for _, fv in r.matchdays.values() if fv > 0]))
            for records in by_role.values()
            for r in records
            if sum(1 for _, fv in r.matchdays.values() if fv > 0) >= 1
        ]
        return float(np.mean(all_means)) if all_means else 6.0

    priors = {role: _role_prior(role) for role in _ROLE_ORDER}

    # Compute EFV per player — include index as tiebreaker to avoid comparing PlayerRecord
    efv_by_role: dict[str, list[tuple[float, PlayerRecord]]] = {
        role: [
            (efv, rec)
            for efv, _, rec in sorted(
                [(_compute_efv(r, priors[role], shrinkage_k), i, r)
                 for i, r in enumerate(records)],
                reverse=True,
            )
        ]
        for role, records in by_role.items()
    }

    best_result: TopFormationResult | None = None

    for n_def, n_mid, n_att in _VALID_FORMATIONS:
        needed = {"P": 1, "D": n_def, "C": n_mid, "A": n_att}
        # Check enough players per role
        if any(len(efv_by_role[role]) < n for role, n in needed.items()):
            continue

        selected: list[TopFormationPlayer] = []
        total = 0.0
        for role in _ROLE_ORDER:
            n = needed[role]
            for efv, record in efv_by_role[role][:n]:
                selected.append(TopFormationPlayer(
                    name=record.name,
                    ruolo=role,
                    efv=round(efv, 4),
                ))
                total += efv

        if best_result is None or total > best_result.total_efv:
            best_result = TopFormationResult(
                formation=(n_def, n_mid, n_att),
                players=selected,
                total_efv=round(total, 4),
            )

    if best_result is None:
        # Roster too small for any valid formation — return whatever we can
        flat = list(r for records in by_role.values() for r in records)
        all_players = [
            (efv, rec)
            for efv, _, rec in sorted(
                [(_compute_efv(r, priors.get(r.ruolo or "C", 6.0), shrinkage_k), i, r)
                 for i, r in enumerate(flat)],
                reverse=True,
            )
        ][:11]
        selected = [
            TopFormationPlayer(name=r.name, ruolo=r.ruolo or "C", efv=round(e, 4))
            for e, r in all_players
        ]
        total = sum(p.efv for p in selected)
        best_result = TopFormationResult(
            formation=(4, 4, 2),
            players=selected,
            total_efv=round(total, 4),
        )

    return best_result
