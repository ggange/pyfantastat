import numpy as np
import pytest
from pyfantastat.team import Team
from pyfantastat.championship import Championship
from pyfantastat.monte_carlo import MonteCarloSimulator, MonteCarloResult, _load_pool


def _make_ch(n=8):
    """Build a championship with n teams and n-1 rounds of random points."""
    rng = np.random.default_rng(0)
    teams = []
    for i in range(n):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(rng.uniform(60, 100, size=n - 1).tolist())
        teams.append(t)
    ch = Championship(teams)
    return ch


def test_run_returns_monte_carlo_result():
    ch = _make_ch(8)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=42)
    result = sim.run()
    assert isinstance(result, MonteCarloResult)


def test_rank_probabilities_shape():
    n = 8
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=42)
    result = sim.run()
    assert result.rank_probabilities.shape == (n, n)


def test_rank_probabilities_rows_sum_to_one():
    n = 8
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=2000, batch=500, seed=42)
    result = sim.run()
    row_sums = result.rank_probabilities.sum(axis=1)
    np.testing.assert_allclose(row_sums, 1.0, atol=1e-9)


def test_expected_points_shape():
    n = 8
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=42)
    result = sim.run()
    assert result.expected_points.shape == (n,)
    assert (result.expected_points >= 0).all()


def test_deterministic_with_same_seed():
    ch1 = _make_ch(8)
    ch2 = _make_ch(8)
    r1 = MonteCarloSimulator(ch1, n_iterations=1000, batch=500, seed=7).run()
    r2 = MonteCarloSimulator(ch2, n_iterations=1000, batch=500, seed=7).run()
    np.testing.assert_array_equal(r1.rank_probabilities, r2.rank_probabilities)


def test_different_seeds_give_different_results():
    ch1 = _make_ch(8)
    ch2 = _make_ch(8)
    r1 = MonteCarloSimulator(ch1, n_iterations=500, batch=250, seed=1).run()
    r2 = MonteCarloSimulator(ch2, n_iterations=500, batch=250, seed=2).run()
    assert not np.array_equal(r1.rank_probabilities, r2.rank_probabilities)


def test_iterations_run_capped_by_n_iterations():
    n = 8
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=300, batch=100, patience=100, seed=42)
    result = sim.run()
    assert result.iterations_run <= 300


def test_converged_flag_type():
    ch = _make_ch(8)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=42)
    result = sim.run()
    assert isinstance(result.converged, bool)


# ---------------------------------------------------------------------------
# Pool loading — 10 and 12 teams
# ---------------------------------------------------------------------------

def test_run_with_10_teams():
    n = 10
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=0)
    result = sim.run()
    assert result.rank_probabilities.shape == (n, n)
    np.testing.assert_allclose(result.rank_probabilities.sum(axis=1), 1.0, atol=1e-9)


def test_run_with_12_teams():
    n = 12
    ch = _make_ch(n)
    sim = MonteCarloSimulator(ch, n_iterations=500, batch=250, seed=0)
    result = sim.run()
    assert result.rank_probabilities.shape == (n, n)
    np.testing.assert_allclose(result.rank_probabilities.sum(axis=1), 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# Pool loading — unsupported / odd team count fallback
# ---------------------------------------------------------------------------

def test_load_pool_unsupported_even_size_returns_minimal_pool():
    pool = _load_pool(6)  # no pool file for 6 teams → minimal fallback
    assert pool.ndim == 4
    assert pool.shape[-1] == 2  # each entry is [team_a, team_b]


def test_load_pool_odd_size_raises():
    with pytest.raises(ValueError, match="must be even"):
        _load_pool(5)


# ---------------------------------------------------------------------------
# Pool tiling when n_matchdays exceeds R_pool
# ---------------------------------------------------------------------------

def test_pool_tiling_more_matchdays_than_pool_rounds():
    # Build a championship with more played matchdays than the pool has rounds.
    # Pool for 8 teams has 7 rounds. Give teams 14 rounds of data.
    rng = np.random.default_rng(99)
    teams = []
    for i in range(8):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(rng.uniform(60, 100, size=14).tolist())
        teams.append(t)
    ch = Championship(teams)
    # Set current_matchday directly to bypass the calendar requirement for this
    # internal-state test (we're testing the pool-tiling path in MonteCarloSimulator).
    ch.current_matchday = 14
    sim = MonteCarloSimulator(ch, n_iterations=200, batch=100, seed=1)
    result = sim.run()
    assert result.rank_probabilities.shape == (8, 8)


# ---------------------------------------------------------------------------
# Early convergence
# ---------------------------------------------------------------------------

def test_early_convergence_triggers():
    # Very loose tolerance → converges after the first checkpoint
    ch = _make_ch(8)
    sim = MonteCarloSimulator(
        ch,
        n_iterations=100_000,
        batch=500,
        patience=1,
        tol=1.0,  # any change < 100% is "stable" — converges immediately
        seed=42,
    )
    result = sim.run()
    assert result.converged is True
    assert result.iterations_run < 100_000


# ---------------------------------------------------------------------------
# Interval mode in vectorized simulation
# ---------------------------------------------------------------------------

def test_run_with_interval_mode():
    rng = np.random.default_rng(5)
    teams = []
    for i in range(8):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(rng.uniform(60, 100, size=7).tolist())
        teams.append(t)
    ch = Championship(teams, interval=True, pt_interval=6.0, only_in_range=False)
    sim = MonteCarloSimulator(ch, n_iterations=400, batch=200, seed=7)
    result = sim.run()
    assert result.rank_probabilities.shape == (8, 8)
    np.testing.assert_allclose(result.rank_probabilities.sum(axis=1), 1.0, atol=1e-9)


def test_run_with_interval_only_in_range():
    rng = np.random.default_rng(5)
    teams = []
    for i in range(8):
        t = Team(f"T{i}", f"U{i}")
        t.add_fanta_pts_scored(rng.uniform(60, 100, size=7).tolist())
        teams.append(t)
    ch = Championship(teams, interval=True, pt_interval=3.0, only_in_range=True)
    sim = MonteCarloSimulator(ch, n_iterations=400, batch=200, seed=7)
    result = sim.run()
    np.testing.assert_allclose(result.rank_probabilities.sum(axis=1), 1.0, atol=1e-9)
