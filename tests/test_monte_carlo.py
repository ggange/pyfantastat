import numpy as np
import pytest
from pyfantastat.team import Team
from pyfantastat.championship import Championship
from pyfantastat.monte_carlo import MonteCarloSimulator, MonteCarloResult


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
