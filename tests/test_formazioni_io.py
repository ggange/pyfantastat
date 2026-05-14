"""Tests for the Formazioni XLSX parser."""

from pathlib import Path
import pytest

from pyfantastat.io.formazioni import load_formazioni_xlsx, load_formazioni_dir
from pyfantastat.io.models import FormazioniMatchday, FormazioniPlayer, FormazioniTeam

FIXTURE = Path(__file__).parent / "fixtures" / "sample_formazioni.xlsx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _team(md: FormazioniMatchday, name: str) -> FormazioniTeam:
    norm = name.strip().lower()
    for t in md.teams:
        if t.team_name.strip().lower() == norm:
            return t
    raise KeyError(f"Team '{name}' not found in matchday")


# ---------------------------------------------------------------------------
# load_formazioni_xlsx
# ---------------------------------------------------------------------------

def test_giornata_extracted():
    md = load_formazioni_xlsx(FIXTURE)
    assert md.giornata == 1


def test_two_teams_found():
    md = load_formazioni_xlsx(FIXTURE)
    assert len(md.teams) == 2


def test_team_names():
    md = load_formazioni_xlsx(FIXTURE)
    names = {t.team_name for t in md.teams}
    assert "ALPHA FC" in names
    assert "BETA SC" in names


def test_totale_alpha():
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    assert alpha.totale == pytest.approx(61.5, abs=0.01)


def test_totale_beta():
    md = load_formazioni_xlsx(FIXTURE)
    beta = _team(md, "BETA SC")
    assert beta.totale == pytest.approx(63.5, abs=0.01)


def test_player_count_includes_bench():
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    # 10 outfield + 1 GK starter + 1 GK bench + 1 DEF bench = 12
    assert len(alpha.players) == 12


def test_player_roles_present():
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    roles = {p.ruolo for p in alpha.players}
    assert roles == {"P", "D", "C", "A"}


def test_bench_player_scores_zero():
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    # Serra and Costa are bench
    bench = [p for p in alpha.players if p.name in ("Serra", "Costa")]
    assert len(bench) == 2
    for p in bench:
        assert p.voto == 0.0
        assert p.fantavoto == 0.0


def test_transfer_marker_stripped():
    """Trailing '*' on player names should be removed."""
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    names = [p.name for p in alpha.players]
    assert "Costa" in names
    assert "Costa*" not in names


def test_starter_scores():
    md = load_formazioni_xlsx(FIXTURE)
    alpha = _team(md, "ALPHA FC")
    rossi = next(p for p in alpha.players if p.name == "Rossi")
    assert rossi.ruolo == "P"
    assert rossi.voto == pytest.approx(6.5)
    assert rossi.fantavoto == pytest.approx(7.5)


def test_invalid_file_raises():
    with pytest.raises(Exception):
        load_formazioni_xlsx(Path(__file__).parent / "fixtures" / "nonexistent.xlsx")


def test_missing_giornata_raises(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.cell(1, 1, "No giornata here")
    p = tmp_path / "bad.xlsx"
    wb.save(p)
    with pytest.raises(ValueError, match="giornata"):
        load_formazioni_xlsx(p)


# ---------------------------------------------------------------------------
# load_formazioni_dir
# ---------------------------------------------------------------------------

def test_load_dir_finds_fixture(tmp_path):
    import shutil
    shutil.copy(FIXTURE, tmp_path / "Formazioni_test_1_giornata.xlsx")
    result = load_formazioni_dir(tmp_path)
    assert 1 in result
    assert result[1].giornata == 1


def test_load_dir_skips_bad_file(tmp_path):
    import shutil
    import warnings
    shutil.copy(FIXTURE, tmp_path / "Formazioni_good.xlsx")
    (tmp_path / "Formazioni_bad.xlsx").write_bytes(b"not an xlsx")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = load_formazioni_dir(tmp_path)
    assert 1 in result
    assert len(w) == 1
    assert "Skipping" in str(w[0].message)


def test_load_dir_deduplicates(tmp_path):
    import shutil
    import warnings
    shutil.copy(FIXTURE, tmp_path / "Formazioni_a.xlsx")
    shutil.copy(FIXTURE, tmp_path / "Formazioni_b.xlsx")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = load_formazioni_dir(tmp_path)
    assert len(result) == 1
    assert any("Duplicate" in str(x.message) for x in w)
