import numpy as np
import pytest
from pyfantastat import mean, std, median, pearson_correlation
from pyfantastat.statistics import team_scoring_stats, scoring_correlation
from pyfantastat.team import Team


VALUES = [70.0, 80.0, 60.0, 90.0, 75.0]


def test_mean():
    assert mean(VALUES) == pytest.approx(np.mean(VALUES))


def test_std():
    assert std(VALUES) == pytest.approx(np.std(VALUES))


def test_median():
    assert median(VALUES) == pytest.approx(np.median(VALUES))


def test_pearson_correlation_perfect():
    v = [1.0, 2.0, 3.0, 4.0]
    assert pearson_correlation(v, v) == pytest.approx(1.0)


def test_pearson_correlation_anti():
    v = [1.0, 2.0, 3.0, 4.0]
    w = [4.0, 3.0, 2.0, 1.0]
    assert pearson_correlation(v, w) == pytest.approx(-1.0)


def test_pearson_correlation_zero_variance():
    v = [5.0, 5.0, 5.0]
    w = [1.0, 2.0, 3.0]
    assert pearson_correlation(v, w) == 0.0


def test_team_scoring_stats():
    t = Team("A", "B")
    t.add_fanta_pts_scored(VALUES)
    stats = team_scoring_stats(t)
    assert set(stats.keys()) == {"mean", "std", "median"}
    assert stats["mean"] == pytest.approx(np.mean(VALUES))
    assert stats["std"] == pytest.approx(np.std(VALUES))
    assert stats["median"] == pytest.approx(np.median(VALUES))


def test_scoring_correlation():
    t1 = Team("A", "B")
    t2 = Team("C", "D")
    t1.add_fanta_pts_scored([70.0, 80.0, 75.0])
    t2.add_fanta_pts_scored([65.0, 85.0, 70.0])
    corr = scoring_correlation(t1, t2)
    expected = float(np.corrcoef([70.0, 80.0, 75.0], [65.0, 85.0, 70.0])[0, 1])
    assert corr == pytest.approx(expected)


def test_scoring_correlation_length_mismatch():
    t1 = Team("A", "B")
    t2 = Team("C", "D")
    t1.add_fanta_pts_scored([70.0, 80.0])
    t2.add_fanta_pts_scored([65.0, 85.0, 70.0])
    with pytest.raises(ValueError):
        scoring_correlation(t1, t2)
