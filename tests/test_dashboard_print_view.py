"""Contracts for the printable dashboard period report."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import zrzavy_energy_monitor as application

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "app.css"
SCRIPT_FILE = PROJECT_ROOT / "app" / "static" / "dashboard.js"


def _css_block(css: str, opening: str) -> str:
    """Return the body of the first CSS block that starts with opening."""

    start = css.index("{", css.index(opening)) + 1
    depth = 1
    index = start
    while depth:
        character = css[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        index += 1
    return css[start : index - 1]


def _dashboard_html() -> str:
    """Render the dashboard page through the application test client."""

    response = application.app.test_client().get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_dashboard_offers_a_print_button() -> None:
    """The dashboard exposes one button for the current period."""

    html = _dashboard_html()
    assert 'id="print-dashboard"' in html
    assert "Drucken" in html


def test_dashboard_marks_exactly_three_report_sections() -> None:
    """Only the chart, the value table and the KPI row belong to the report."""

    html = _dashboard_html()
    sections = re.findall(r'<section class="([^"]*\bprint-report\b[^"]*)"', html)
    assert len(sections) == 3
    for expected in ("chart-panel", "values-panel", "kpi-grid"):
        assert any(expected in classes.split() for classes in sections)


def test_dashboard_provides_a_print_chart_image() -> None:
    """The chart is printed from a prepared image instead of the live canvas."""

    html = _dashboard_html()
    assert 'id="print-energy-chart"' in html
    assert 'class="print-chart"' in html
    assert 'id="print-stamp"' in html


def test_print_rules_keep_the_complete_value_table() -> None:
    """The screen clipping and the sticky header must not survive printing."""

    css = STYLE_FILE.read_text(encoding="utf-8")
    print_block = _css_block(css, "@media print")
    assert "max-height: none" in print_block
    assert "overflow: visible" in print_block
    assert "display: table-header-group" in print_block
    assert "display: table-row-group" in print_block
    assert "position: static" in print_block
    assert "break-inside: avoid" in print_block
    assert "body.is-loading .values-panel" in print_block
    assert "table-layout: fixed" in print_block
    assert "display: table-header-group" in print_block


def test_print_page_is_a4_and_hides_non_report_sections() -> None:
    """The report is A4 and is built only from the opt-in sections."""

    css = STYLE_FILE.read_text(encoding="utf-8")
    assert "size: A4" in _css_block(css, "@page")
    print_block = _css_block(css, "@media print")
    assert "main > section:not(.print-report)" in print_block
    assert "print-color-adjust: exact" in print_block
    assert "repeat(3, minmax(0, 1fr))" in print_block
    assert "body:not(.has-print-chart)" in print_block


def test_dashboard_script_prepares_the_print_report() -> None:
    """The script renders the print image and stamps the print time."""

    script = SCRIPT_FILE.read_text(encoding="utf-8")
    assert 'addEventListener("beforeprint"' in script
    assert 'addEventListener("afterprint"' in script
    assert 'toDataURL("image/png")' in script
    assert "PRINT_CHART_PIXEL_RATIO" in script
    assert "toLocaleDateString" in script
    assert "refreshPrintChart()" in script
    assert "has-print-chart" in script


def test_value_table_offers_the_quota_columns() -> None:
    """The value table has eight columns including both quota columns."""

    html = _dashboard_html()
    assert html.count('<th scope="col">') == 8
    assert "Eigenverbrauchsquote" in html
    assert "Autarkiegrad" in html
    assert 'colspan="8"' in html
    assert 'colspan="6"' not in html


def test_print_rules_define_widths_for_all_eight_columns() -> None:
    """The fixed print layout must cover every column and stay at 100 %."""

    css = STYLE_FILE.read_text(encoding="utf-8")
    print_block = _css_block(css, "@media print")
    widths = {
        int(match.group(1)): float(match.group(2))
        for match in re.finditer(
            r"\.values-table th:nth-child\((\d+)\) \{\s*width: ([\d.]+)%;",
            print_block,
        )
    }

    assert sorted(widths) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert sum(widths.values()) == pytest.approx(100.0)


def test_dashboard_script_renders_the_quotas_from_the_series() -> None:
    """The table reads both quotas from the payload and formats them as percent."""

    script = SCRIPT_FILE.read_text(encoding="utf-8")
    assert 'series: "self_consumption_pct"' in script
    assert 'series: "autarky_pct"' in script
    assert 'format: "pct"' in script
    assert "sample_count" in script
    assert "formatCell(data.kpi[column.kpi]" in script
