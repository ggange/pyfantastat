# pyfantastat

A Python library for Italian fantasy football (Fantacalcio) league management — parse league calendars, compute standings with full tiebreaker logic, run analytics, and estimate ranking probabilities via Monte Carlo simulation.

## Requirements

- Python 3.10+
- NumPy ≥ 1.24
- openpyxl ≥ 3.1 (for reading `.xlsx` calendars)

## Installation

```bash
pip install pyfantastat
```

Or in editable mode from source:

```bash
git clone <repo-url>
cd pyfantastat
pip install -e ".[dev]"
```

---

## Quick start

```python
from pyfantastat import Championship, load_calendar_xlsx

# Parse a Fantacalcio calendar workbook
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

| Default threshold | Points needed |
|---|---|
| 1 goal | ≥ 66 |
| 2 goals | ≥ 71 |
| 3 goals | ≥ 76 |
| … | … |

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

t = Team(team_name="Juventus FC", user_name="Alice")
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

wdl  = ch.get_wins_draws_losses()        # {"Team0": {"W": 3, "D": 0, "L": 0}, ...}
sos  = ch.strength_of_schedule(0)        # average opponent fantapoints for team 0
fpt  = ch.total_fpt_ranking()            # [("Team0", 226.0), ...] sorted descending
lo   = ch.lowest_scoring_day()           # (matchday_idx, combined_score)
hi   = ch.highest_scoring_day()          # (matchday_idx, combined_score)
close = ch.number_close_matches()        # matches with |pts_diff| ≤ 3 and both ≥ 66
draws = ch.close_draws()                 # subset of above: draws only
act, hyp = ch.what_if_calendar(0, 1)    # actual vs hypothetical pts for team 0 on team 1's schedule
prizes = ch.prizes()                     # {"highest": {...}, "lowest": {...}}
```

---

### `load_calendar_xlsx` / `CalendarData`

```python
from pyfantastat import load_calendar_xlsx, CalendarData

data: CalendarData = load_calendar_xlsx("league.xlsx")

print(data.league_name)         # e.g. "FantaLeague 2024"
print(data.team_names)          # sorted list of team names
print(data.team_points["FC Roma"])  # [78.5, 65.0, 82.0, ...]
print(data.current_matchday)    # most recent completed matchday (1-based)
print(data.calendar)            # nested list[matchday][match][team_idx_a, team_idx_b]
```

The workbook must follow the standard Fantacalcio calendar layout:
- Cell E1: `"Calendario <league_name>"`
- Columns A–F: odd-numbered league matchdays
- Columns G–L: even-numbered league matchdays
- Each match row: `Team1 | Pts1 | Pts2 | Team2`

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

Estimates ranking probabilities by simulating thousands of seasons using pre-computed calendar pools for leagues of 8, 10, or 12 teams (falls back to a minimal round-robin for other sizes).

```python
from pyfantastat import Championship, load_calendar_xlsx
from pyfantastat.monte_carlo import MonteCarloSimulator

data = load_calendar_xlsx("league.xlsx")
ch = Championship.from_calendar_data(data)

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

n = len(ch.teams)
for team_idx in range(n):
    team = ch.teams[team_idx]
    p_first = result.rank_probabilities[team_idx, 0]
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
├── statistics.py        # mean, std, median, pearson_correlation, helpers
├── monte_carlo.py       # MonteCarloSimulator, MonteCarloResult
├── io/
│   ├── __init__.py
│   ├── loader.py        # load_calendar_xlsx
│   └── models.py        # CalendarData dataclass
└── data/
    └── calendars/       # pre-computed .npz calendar pools (n=8, 10, 12)

tests/
├── conftest.py
├── fixtures/
│   └── sample_calendar.xlsx
├── test_team.py
├── test_championship.py
├── test_championship_stats.py
├── test_statistics.py
├── test_monte_carlo.py
├── test_loader.py
└── test_import.py
```

## Running tests

```bash
pytest tests/ -v
```

## Changelog

### 0.2.0
- Restructured package: removed `src/` indirection, added `io/` sub-package
- Renamed all attributes and methods to snake_case
- Fixed non-idempotent `generate_ranking()` (goal counters now reset on each call)
- Added `Championship.from_calendar_data()` factory method
- Added analytics: `get_wins_draws_losses`, `strength_of_schedule`, `total_fpt_ranking`,
  `lowest_scoring_day`, `highest_scoring_day`, `number_close_matches`, `close_draws`,
  `what_if_calendar`, `prizes`
- Added `pyfantastat.statistics` module
- Added `pyfantastat.monte_carlo` module with vectorised batch simulation and convergence stopping
- Expanded test suite to 46 tests across 7 files

### 0.1.0
- Initial release: `Team`, `Championship`, `load_calendar_xlsx`, `CalendarData`
