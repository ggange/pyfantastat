def test_public_api_imports():
    from pyfantastat import (
        Team,
        Championship,
        load_calendar_xlsx,
        CalendarData,
        mean,
        std,
        median,
        pearson_correlation,
    )
    from pyfantastat.monte_carlo import MonteCarloSimulator, MonteCarloResult
