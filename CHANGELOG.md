# Changelog

All notable changes to this project will be documented in this file.

## [0.3.2] - 2026-05-20

- Added author metadata to `pyproject.toml`
- Added `CHANGELOG.md`
- CI now uploads coverage report to Codecov (Python 3.12 run)
- Added Codecov badge to README

## [0.3.1]

- Added `pyfantastat.pandas_utils` module with four DataFrame conversion helpers:
  `roster_to_dataframe`, `rosters_to_dataframe`, `top_formation_to_dataframe`, `matchday_to_dataframe`
- Added `pyfantastat[pandas]` optional-dependency extra
- CI now installs the `pandas` extra so pandas tests run on every push

## [0.3.0]

- Open-source cleanup: replaced personal league filename in demo notebook with a generic placeholder
- Added MIT `LICENSE` file
- Added GitHub Actions CI workflow (Python 3.10, 3.11, 3.12)
- Added `CONTRIBUTING.md`
- Translated remaining Italian warning message in `championship.py` to English
- Added `[project.urls]` and `license` field to `pyproject.toml`
- Updated `.gitignore` to exclude personal Fantacalcio data files

## [0.2.0]

- Restructured package: removed `src/` indirection, added `io/` sub-package
- Renamed all attributes and methods to snake_case
- Fixed non-idempotent `generate_ranking()` (goal counters now reset on each call)
- Added `Championship.from_calendar_data()` factory method
- Added analytics: `get_wins_draws_losses`, `strength_of_schedule`, `total_fpt_ranking`,
  `lowest_scoring_day`, `highest_scoring_day`, `number_close_matches`, `close_draws`,
  `what_if_calendar`, `prizes`
- Added `pyfantastat.statistics` module
- Added `pyfantastat.monte_carlo` module with vectorised batch simulation and convergence stopping
- Added `pyfantastat.formazioni` module: lineup parsing, roster aggregation, player stats, best-11 selection
- Expanded test suite to 83 tests across 9 files

## [0.1.0]

- Initial release: `Team`, `Championship`, `load_calendar_xlsx`, `CalendarData`
