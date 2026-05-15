# Contributing

## Setup

```bash
git clone https://github.com/<your-username>/pyfantastat.git
cd pyfantastat
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

For coverage:

```bash
pytest --cov=pyfantastat --cov-report=term-missing
```

## Code Style

- Follow existing code style (PEP 8, type hints throughout).
- Keep docstrings concise; use the existing format as reference.
- Do not add unnecessary comments — prefer self-documenting names.

## Submitting Changes

1. Fork the repository and create a branch from `main`.
2. Make your changes and ensure all tests pass.
3. Open a pull request with a clear description of what changed and why.

## Domain Notes

pyfantastat is specific to the [Fantacalcio](https://www.fantacalcio.it/) platform. The Excel parsers (`io/loader.py`, `io/formazioni.py`) rely on Italian keywords embedded in the standard Fantacalcio export format — this is intentional, not a localisation bug.
