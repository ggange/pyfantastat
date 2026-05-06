"""Statistical utility functions for fantasy football analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyfantastat.team import Team


def mean(values: np.ndarray | list[float]) -> float:
    """Arithmetic mean of *values*."""
    return float(np.mean(values))


def std(values: np.ndarray | list[float]) -> float:
    """Population standard deviation of *values*."""
    return float(np.std(values))


def median(values: np.ndarray | list[float]) -> float:
    """Median of *values*.

    .. note::
        The fantakings backend named this ``centered_average``; here we use
        the standard name for clarity.
    """
    return float(np.median(values))


def pearson_correlation(
    v1: np.ndarray | list[float],
    v2: np.ndarray | list[float],
) -> float:
    """Pearson correlation coefficient between two equal-length sequences.

    :returns: Value in ``[-1, 1]``.  Returns ``0.0`` if either sequence has
        zero variance (e.g. all values identical).
    """
    # np.corrcoef returns a 2×2 matrix; off-diagonal element is the correlation
    arr = np.corrcoef(np.asarray(v1, dtype=float), np.asarray(v2, dtype=float))
    if np.isnan(arr[0, 1]):
        return 0.0
    return float(arr[0, 1])


# ------------------------------------------------------------------
# Domain-aware helpers
# ------------------------------------------------------------------


def team_scoring_stats(team: "Team") -> dict[str, float]:
    """Return summary statistics for a team's fantapoints scored.

    :returns: ``{"mean": ..., "std": ..., "median": ...}``
    """
    pts = np.asarray(team.fanta_pts_scored, dtype=float)
    return {
        "mean": float(np.mean(pts)),
        "std": float(np.std(pts)),
        "median": float(np.median(pts)),
    }


def scoring_correlation(team_a: "Team", team_b: "Team") -> float:
    """Pearson correlation between two teams' weekly fantapoints scored.

    :raises ValueError: If the teams have different numbers of matchdays.
    """
    a = np.asarray(team_a.fanta_pts_scored, dtype=float)
    b = np.asarray(team_b.fanta_pts_scored, dtype=float)
    if len(a) != len(b):
        raise ValueError(
            f"Teams have different matchday counts: {len(a)} vs {len(b)}."
        )
    return pearson_correlation(a, b)
