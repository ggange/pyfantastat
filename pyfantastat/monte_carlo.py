"""Monte Carlo simulation for ranking probability estimation."""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyfantastat.championship import Championship


def _vectorized_match_result(
    fa: np.ndarray,
    fb: np.ndarray,
    goal_threshold: int | None,
    interval: bool,
    only_in_range: bool,
    pt_interval: float | None,
) -> np.ndarray:
    """Vectorized match result: 1=team_a wins, 2=team_b wins, 0=draw."""
    if goal_threshold is not None:
        limits = np.arange(66, 66 + goal_threshold * 8, goal_threshold, dtype=np.float64)
    else:
        limits = np.arange(66, 101, 5, dtype=np.float64)

    goals_a = (fa[..., None] >= limits).sum(axis=-1)
    goals_b = (fb[..., None] >= limits).sum(axis=-1)

    if interval and pt_interval is not None:
        cond1 = (fa - fb >= pt_interval) & (fa >= 66)
        cond2 = (fb - fa >= pt_interval) & (fb >= 66)
        if not only_in_range:
            g_min = np.minimum(goals_a, goals_b)
            goals_a = np.where(cond1, goals_a + 1, np.where(cond2, goals_a, g_min))
            goals_b = np.where(cond2, goals_b + 1, np.where(cond1, goals_b, g_min))
        else:
            tie = goals_a == goals_b
            goals_a = np.where(tie & cond1, goals_a + 1, goals_a)
            goals_b = np.where(tie & cond2, goals_b + 1, goals_b)

    return np.where(goals_a > goals_b, 1, np.where(goals_b > goals_a, 2, 0))


def _load_pool(n: int) -> np.ndarray:
    """Load a pre-computed calendar pool for *n* teams from package data.

    Falls back to a trivial single-round-robin for unsupported sizes.
    """
    pool_files = {
        8: "pool_n8_K20000.npz",
        10: "pool_n10_K45000.npz",
        12: "pool_n12_K65000.npz",
    }
    filename = pool_files.get(n)
    if filename is not None:
        pkg = importlib.resources.files("pyfantastat").joinpath("data/calendars")
        path = pkg.joinpath(filename)
        try:
            with importlib.resources.as_file(path) as p:
                npz = np.load(p)
            key = "calendars" if "calendars" in npz else npz.files[0]
            return npz[key]
        except (FileNotFoundError, KeyError):
            pass

    # Fallback: minimal pool with a single pairing calendar
    if n % 2 != 0:
        raise ValueError(f"Unsupported team count for Monte Carlo: {n} (must be even).")
    pairs = [[i, i + 1] for i in range(0, n, 2)]
    return np.array([[pairs]], dtype=np.intp)  # shape (1, 1, M, 2)


@dataclass
class MonteCarloResult:
    """Output of a Monte Carlo ranking simulation.

    Attributes:
        rank_probabilities: Array of shape ``(n_teams, n_teams)`` where
            ``rank_probabilities[i, r]`` is the probability that team *i*
            finishes in rank *r* (0 = first place).
        expected_points: Mean league points per team across all simulated
            seasons, shape ``(n_teams,)``.
        iterations_run: Number of seasons actually simulated (may be less
            than *n_iterations* when convergence is reached early).
        converged: ``True`` if the simulation stopped early due to
            convergence rather than exhausting *n_iterations*.
    """

    rank_probabilities: np.ndarray
    expected_points: np.ndarray
    iterations_run: int
    converged: bool


class MonteCarloSimulator:
    """Estimate ranking probabilities via vectorized Monte Carlo simulation.

    Each iteration samples a random calendar from a pre-computed pool and
    replays the season using each team's historical fantapoints. The
    simulation stops early when the rank-probability matrix stabilises.

    :param championship: A configured :class:`~pyfantastat.championship.Championship`
        whose teams already have ``fanta_pts_scored`` populated.
    :param n_iterations: Maximum number of seasons to simulate.
    :param batch: Number of seasons per vectorised batch.
    :param patience: Number of consecutive stable checkpoints required to
        declare convergence.
    :param tol: Maximum element-wise change in rank-probability matrix
        between checkpoints to be considered stable.
    :param seed: Random seed for reproducibility.  ``None`` → non-deterministic.
    """

    def __init__(
        self,
        championship: "Championship",
        n_iterations: int = 200_000,
        batch: int = 50_000,
        patience: int = 3,
        tol: float = 0.01,
        seed: int | None = None,
    ) -> None:
        self.championship = championship
        self.n_iterations = n_iterations
        self.batch = batch
        self.patience = patience
        self.tol = tol
        self.seed = seed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fantapoints_matrix(self) -> np.ndarray:
        """Return array of shape ``(n_teams, n_rounds)`` from team histories."""
        rows = [
            np.asarray(t.fanta_pts_scored, dtype=np.float64)
            for t in self.championship.teams
        ]
        if not rows:
            raise ValueError("No teams in championship.")
        max_len = max(len(r) for r in rows)
        matrix = np.zeros((len(rows), max_len), dtype=np.float64)
        for i, row in enumerate(rows):
            matrix[i, : len(row)] = row
        return matrix

    def _run_batch(
        self,
        k_indices: np.ndarray,
        pool: np.ndarray,
        fantapoints: np.ndarray,
        day_samples: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Simulate *B* seasons in one vectorised pass.

        :param day_samples: Shape ``(B, R_pool)`` — matchday indices sampled
            from ``[0, n_matchdays)`` for each simulated season.  Allows
            re-using all historical matchdays even when the pool has fewer
            rounds than matchdays played.
        :returns: ``(league_pts, ranks)`` each of shape ``(B, n_teams)``.
        """
        B = k_indices.size
        n = fantapoints.shape[0]
        cal_batch = pool[k_indices]  # (B, R, M, 2)
        R = cal_batch.shape[1]
        M = cal_batch.shape[2]

        team_a = cal_batch[:, :, :, 0]  # (B, R, M)
        team_b = cal_batch[:, :, :, 1]
        # day_samples: (B, R) → broadcast to (B, R, 1) for indexing (B, R, M)
        day_idx = day_samples[:, :, None]  # (B, R, 1)

        fa = fantapoints[team_a, day_idx]  # (B, R, M)
        fb = fantapoints[team_b, day_idx]

        result = _vectorized_match_result(
            fa,
            fb,
            self.championship.goal_threshold,
            self.championship.interval,
            self.championship.only_in_range,
            self.championship.pt_interval,
        )

        pa = np.where(result == 1, 3, np.where(result == 2, 0, 1)).astype(np.float64)
        pb = np.where(result == 2, 3, np.where(result == 1, 0, 1)).astype(np.float64)

        league_pts = np.zeros((B, n), dtype=np.float64)
        b_idx = np.arange(B)
        for r in range(R):
            for m in range(M):
                np.add.at(league_pts, (b_idx, team_a[:, r, m]), pa[:, r, m])
                np.add.at(league_pts, (b_idx, team_b[:, r, m]), pb[:, r, m])

        # Tie-break key: use total fantapoints across the sampled matchdays
        sampled_fpt = fantapoints[:, day_samples.T]  # (n, R, B) — per-team sampled totals
        fantapoints_total = sampled_fpt.sum(axis=1).T  # (B, n)
        key = league_pts * (fantapoints_total.max() + 1.0) + fantapoints_total
        order = np.argsort(-key, kind="stable", axis=1)
        ranks = np.empty((B, n), dtype=np.int32)
        ranks[np.arange(B)[:, None], order] = np.arange(n, dtype=np.int32)

        return league_pts, ranks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> MonteCarloResult:
        """Run the simulation and return a :class:`MonteCarloResult`.

        :raises ValueError: If teams have no fantapoints recorded.
        """
        fantapoints = self._fantapoints_matrix()
        n, n_matchdays = fantapoints.shape
        pool = _load_pool(n)
        K = pool.shape[0]
        R_pool = pool.shape[1]  # rounds per simulated season

        rng = np.random.default_rng(self.seed)
        rank_counts = np.zeros((n, n), dtype=np.int64)
        sum_pts = np.zeros(n, dtype=np.float64)

        last_prob: np.ndarray | None = None
        stable = 0
        done = 0
        converged = False

        while done < self.n_iterations:
            step = min(self.batch, self.n_iterations - done)
            k_indices = rng.integers(0, K, size=step, dtype=np.intp)
            # Sample R_pool matchday indices per simulated season from historical data
            day_samples = rng.integers(0, n_matchdays, size=(step, R_pool), dtype=np.intp)

            pts_batch, ranks_batch = self._run_batch(k_indices, pool, fantapoints, day_samples)

            sum_pts += pts_batch.sum(axis=0)
            np.add.at(
                rank_counts,
                (np.tile(np.arange(n, dtype=np.intp), step), ranks_batch.ravel()),
                1,
            )
            done += step

            if done >= self.batch:
                prob = rank_counts / float(done)
                if last_prob is not None:
                    delta = float(np.max(np.abs(prob - last_prob)))
                    if delta < self.tol:
                        stable += 1
                    else:
                        stable = 0
                last_prob = prob.copy()
                if stable >= self.patience:
                    converged = True
                    break

        rank_prob = rank_counts / float(done)
        avg_pts = sum_pts / float(done)

        return MonteCarloResult(
            rank_probabilities=rank_prob,
            expected_points=avg_pts,
            iterations_run=done,
            converged=converged,
        )
