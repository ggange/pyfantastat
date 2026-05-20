# pyfantastat

[![CI](https://github.com/ggange/pyfantastat/actions/workflows/ci.yml/badge.svg)](https://github.com/ggange/pyfantastat/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ggange/pyfantastat/branch/main/graph/badge.svg)](https://codecov.io/gh/ggange/pyfantastat)
[![PyPI](https://img.shields.io/pypi/v/pyfantastat)](https://pypi.org/project/pyfantastat/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Python library for Italian fantasy football (Fantacalcio) league management — parse league calendars and lineup exports, compute standings with full tiebreaker logic, run analytics, and estimate ranking probabilities via Monte Carlo simulation.

> **Disclaimer:** pyfantastat is an independent, community-developed library. It is not affiliated with, sponsored by, or endorsed by [Fantacalcio.it](https://www.fantacalcio.it/). The parsers expect Excel files that can be exported from the Fantacalcio.it platform; all trademarks belong to their respective owners.

> **Disclaimer 2** This library was restructured using Claude based on routines I had coded myself. I am open-sourcing it with the idea that someone might find it useful. Any contribution is welcome!

---

## Requirements

- Python 3.10+
- NumPy ≥ 1.24
- openpyxl ≥ 3.1 (for reading `.xlsx` exports)

## Installation

```bash
pip install pyfantastat                  # core library
pip install "pyfantastat[pandas]"        # + pandas DataFrame helpers
pip install "pyfantastat[notebook]"      # + Jupyter, pandas, matplotlib, seaborn
```

### Contributing / running the demo notebook

Use a virtual environment to keep the install isolated:

```bash
git clone https://github.com/ggange/pyfantastat.git
cd pyfantastat
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,notebook]"
```

To open the demo notebook, register the venv as a Jupyter kernel first:

```bash
python -m ipykernel install --user --name pyfantastat --display-name "pyfantastat"
jupyter notebook examples/pyfantastat_demo.ipynb
```

Select the **pyfantastat** kernel in the notebook UI (Kernel → Change kernel).

---

## Quick start

```python
from pyfantastat import Championship, load_calendar_xlsx

# Parse a Fantacalcio calendar workbook (exported from fantacalcio.it)
data = load_calendar_xlsx("my_league.xlsx")

# Build and rank the championship in one call
ch = Championship.from_calendar_data(
    data,
    card_order=["Punti", "Classifica avulsa", "Differenza reti"],
)
ch.generate_ranking()

sorted_indices, warning = ch.sort_ranking()
for pos, idx in enumerate(sorted_indices, start=1):
    team = ch.teams[idx]
    print(f"{pos}. {team.team_name}  —  {int(ch.ranking[idx])} pts")
```

---

## Core concepts

### Scoring thresholds

Fantapoints are converted to "goals" by counting how many thresholds a team's score crosses:

| Goals | Fantapoints needed |
|---|---|
| 1 | ≥ 66 |
| 2 | ≥ 71 |
| 3 | ≥ 76 |
| … | … (+ 5 per goal) |

The gap between thresholds is 5 by default and can be changed via `goal_threshold`.

### Interval (band) mode

When `interval=True`, an extra goal is awarded to the higher-scoring team if the gap between the two teams' fantapoints exceeds `pt_interval`. With `only_in_range=True`, the rule applies only when the teams are already tied on goals.

### League points

- Win → 3 pts
- Draw → 1 pt
- Loss → 0 pts

### Tiebreaker criteria (`card_order`)

Pass any ordered subset of the following strings:

| Criterion | Description |
|---|---|
| `"Punti"` | League points (always first) |
| `"Somma punti totale"` | Sum of all fantapoints scored |
| `"Classifica avulsa"` | Head-to-head points between tied teams |
| `"Differenza reti"` | Goal difference (scored − conceded) |
| `"Gol fatti"` | Goals scored |
| `"Gol subiti"` | Goals conceded (fewer is better) |

---

## API reference

### `Team`

```python
from pyfantastat import Team

t = Team(team_name="My Team", user_name="Alice")
t.add_fanta_pts_scored([80.5, 72.0, 68.0])   # one value per matchday
t.add_fanta_pts_against([65.0, 74.0, 71.0])
```

| Attribute | Type | Description |
|---|---|---|
| `team_name` | `str` | Display name of the fantasy team |
| `user_name` | `str` | Owner's name |
| `fanta_pts_scored` | `list[float]` | Fantapoints scored per matchday |
| `fanta_pts_against` | `list[float]` | Fantapoints conceded per matchday |
| `goals_scored` | `int` | Cumulative goals scored (set by `generate_ranking`) |
| `goals_conceded` | `int` | Cumulative goals conceded |
| `id` | `int \| None` | Auto-assigned index when added to a `Championship` |

---

### `Championship`

```python
from pyfantastat import Championship, Team

teams = [Team(f"Team{i}", f"User{i}") for i in range(4)]
for i, t in enumerate(teams):
    t.add_fanta_pts_scored([70 + i*2, 75 - i, 68 + i*3])

ch = Championship(
    teams,
    goal_threshold=None,      # 5-point gap (default)
    interval=False,
    only_in_range=False,
    pt_interval=None,
    card_order=["Punti", "Differenza reti"],
)

calendar = [
    [[0, 1], [2, 3]],   # matchday 0: team0 vs team1, team2 vs team3
    [[0, 2], [1, 3]],   # matchday 1
    [[0, 3], [1, 2]],   # matchday 2
]
ch.set_calendar(calendar)
ch.generate_ranking()
sorted_indices, msg = ch.sort_ranking()
```

#### Factory method

```python
ch = Championship.from_calendar_data(data, card_order=["Punti", "Classifica avulsa"])
```

Builds teams from a `CalendarData` object directly, populating `fanta_pts_scored` automatically.

#### Ranking methods

| Method | Returns | Description |
|---|---|---|
| `generate_ranking()` | `None` | Compute league points for all teams. Idempotent. |
| `sort_ranking()` | `(indices, warning)` | Sort teams with configured tiebreakers. |
| `team_position(team_id)` | `int` | 1-based position of a team by its `.id`. |
| `match_for_team(team_id, matchday)` | `list[int]` | Match pair for a team on a given matchday. |

#### Match result methods

| Method | Returns | Description |
|---|---|---|
| `match_result(match, matchday)` | `(result, goals)` | Outcome for a calendar match. |
| `match_result_from_points(pts_a, pts_b)` | `(result, goals)` | Outcome from raw fantapoint values. |

Result codes: `1` = team A wins, `2` = team B wins, `0` = draw.

#### Analytics methods

```python
ch.generate_ranking()   # required before analytics

wdl   = ch.get_wins_draws_losses()        # {"Team0": {"W": 3, "D": 0, "L": 0}, ...}
sos   = ch.strength_of_schedule(0)        # average opponent fantapoints for team 0
fpt   = ch.total_fpt_ranking()            # [("Team0", 226.0), ...] sorted descending
lo    = ch.lowest_scoring_day()           # (matchday_idx, combined_score)
hi    = ch.highest_scoring_day()          # (matchday_idx, combined_score)
close = ch.number_close_matches()         # matches with |pts_diff| ≤ 3 and both ≥ 66
draws = ch.close_draws()                  # subset of above: draws only
act, hyp = ch.what_if_calendar(0, 1)     # actual vs hypothetical pts for team 0 on team 1's schedule
prizes = ch.prizes()                      # {"highest": {...}, "lowest": {...}}
```

---

### `load_calendar_xlsx` / `CalendarData`

```python
from pyfantastat import load_calendar_xlsx, CalendarData

data: CalendarData = load_calendar_xlsx("league.xlsx")

print(data.league_name)                      # e.g. "FantaLeague 2024"
print(data.team_names)                       # sorted list of team names
print(data.team_points["My Team"])           # [78.5, 65.0, 82.0, ...]
print(data.current_matchday)                 # most recent completed matchday (1-based)
print(data.calendar)                         # nested list[matchday][match][team_idx_a, team_idx_b]
```

The workbook must follow the standard Fantacalcio calendar layout as exported from Fantacalcio.it:

- Cell E1: `"Calendario <league_name>"`
- Columns A–F: odd-numbered league matchdays
- Columns G–L: even-numbered league matchdays
- Each match row: `Team1 | Pts1 | Pts2 | Team2`

---

### Formazioni (lineup exports)

pyfantastat can also parse the per-matchday lineup Excel files ("Formazioni") exported from Fantacalcio.it, and expose per-player statistics and best-11 selection.

```python
from pyfantastat import (
    load_formazioni_dir,
    build_team_rosters,
    player_scoring_stats,
    validate_formazioni,
    top_formation,
)

# Load all matchday files from a directory
form_data = load_formazioni_dir("path/to/Formazioni/")

# Aggregate into per-team rosters
rosters = build_team_rosters(form_data)

# Per-player scoring stats (mean/std of voto and fantavoto)
from pyfantastat import player_scoring_stats
for norm_name, record in rosters["my team"].players.items():
    stats = player_scoring_stats(record)
    print(record.name, stats["mean_fantavoto"])

# Cross-validate totals against the calendar
validation = validate_formazioni(form_data, data, tol=0.5)
print("OK" if validation.ok else validation.issues)

# Best 11 selection (Bayesian Expected Fantavoto across all 7 standard formations)
result = top_formation(rosters["my team"])
print(f"Best formation: 1-{result.formation[0]}-{result.formation[1]}-{result.formation[2]}")
print(f"Total EFV: {result.total_efv:.2f}")
```

---

### pandas helpers (optional)

Requires `pip install "pyfantastat[pandas]"`.

```python
from pyfantastat import (
    roster_to_dataframe,
    rosters_to_dataframe,
    top_formation_to_dataframe,
    matchday_to_dataframe,
)

# Single team roster → DataFrame (one row per player)
df = roster_to_dataframe(rosters["my team"])

# All team rosters → DataFrame with an extra "team" column
df = rosters_to_dataframe(rosters)

# TopFormationResult → DataFrame (one row per selected player, ranked)
df = top_formation_to_dataframe(result)

# FormazioniMatchday → DataFrame (one row per player appearance)
df = matchday_to_dataframe(matchday)
```

---

### Statistics module

```python
from pyfantastat import mean, std, median, pearson_correlation
from pyfantastat.statistics import team_scoring_stats, scoring_correlation

values = [70.0, 80.5, 65.0, 88.0]
print(mean(values))    # arithmetic mean
print(std(values))     # population standard deviation
print(median(values))  # median

# Domain helpers
from pyfantastat import Team
t = Team("A", "B")
t.add_fanta_pts_scored(values)
stats = team_scoring_stats(t)   # {"mean": ..., "std": ..., "median": ...}

t2 = Team("C", "D")
t2.add_fanta_pts_scored([68.0, 82.0, 71.0, 90.0])
corr = scoring_correlation(t, t2)   # Pearson correlation in [-1, 1]
```

---

### Monte Carlo simulation

Estimates ranking probabilities by simulating thousands of seasons using pre-computed calendar pools for leagues of 8, 10, or 12 teams.

```python
from pyfantastat import Championship, load_calendar_xlsx
from pyfantastat.monte_carlo import MonteCarloSimulator

data = load_calendar_xlsx("league.xlsx")
ch = Championship.from_calendar_data(data)
ch.generate_ranking()

sim = MonteCarloSimulator(
    ch,
    n_iterations=200_000,   # max seasons to simulate
    batch=50_000,            # seasons per vectorised batch
    patience=3,              # consecutive stable checkpoints to stop early
    tol=0.01,                # convergence tolerance
    seed=42,                 # for reproducibility
)
result = sim.run()

# result.rank_probabilities[i, r] = P(team i finishes rank r), shape (n, n)
# result.expected_points[i]       = mean league points for team i
# result.iterations_run           = actual seasons simulated
# result.converged                = True if stopped early

for i, team in enumerate(ch.teams):
    p_first = result.rank_probabilities[i, 0]
    print(f"{team.team_name}: P(1st) = {p_first:.1%}")
```

The simulation uses vectorised NumPy batch operations and stops early when the rank-probability matrix changes by less than `tol` for `patience` consecutive checkpoints.

---

## Project layout

```
pyfantastat/
├── __init__.py          # public exports
├── team.py              # Team class
├── championship.py      # Championship class (ranking + analytics)
├── formazioni.py        # top_formation, validate_formazioni, build_team_rosters
├── pandas_utils.py      # optional DataFrame helpers (requires pyfantastat[pandas])
├── statistics.py        # mean, std, median, pearson_correlation, helpers
├── monte_carlo.py       # MonteCarloSimulator, MonteCarloResult
├── io/
│   ├── __init__.py
│   ├── loader.py        # load_calendar_xlsx
│   ├── formazioni.py    # load_formazioni_xlsx, load_formazioni_dir
│   └── models.py        # CalendarData, FormazioniMatchday, … dataclasses
└── data/
    └── calendars/       # pre-computed .npz calendar pools (n=8, 10, 12)

tests/
├── conftest.py
├── fixtures/
│   ├── sample_calendar.xlsx
│   └── sample_formazioni.xlsx
├── test_team.py
├── test_championship.py
├── test_championship_stats.py
├── test_championship_tiebreakers.py
├── test_statistics.py
├── test_monte_carlo.py
├── test_loader.py
├── test_formazioni_io.py
├── test_formations.py
├── test_pandas_utils.py
└── test_import.py
```

## Running tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=pyfantastat --cov-report=term-missing
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).
