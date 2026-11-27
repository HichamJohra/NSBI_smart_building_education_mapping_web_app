"""Smoke tests of the Dash app: pages, layouts and the main callbacks run on the real dataset."""

from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
import pytest

from components.data import ID, explode, get_data

PAGES = {"/": "Overview", "/compare": "Compare", "/about": "About"}


@pytest.fixture(scope="module")
def ids(dash_app: Any) -> list[str]:
    return list(get_data().courses[ID])


def test_wsgi_entry_point(dash_app: Any) -> None:
    import app

    assert app.server is dash_app.server


def test_all_pages_registered(dash_app: Any) -> None:
    import dash

    registered = {p["path"]: p["name"] for p in dash.page_registry.values()}
    assert registered == PAGES


def test_layouts_build(dash_app: Any, ids: list[str]) -> None:
    from pages import about, compare, home

    assert home.layout() is not None
    assert about.layout() is not None
    assert compare.layout() is not None
    assert compare.layout(course_ids=",".join(ids[:2])) is not None


def test_server_responds(dash_app: Any) -> None:
    client = dash_app.server.test_client()
    for path in PAGES:
        assert client.get(path).status_code == 200
    assert client.get("/_dash-layout").status_code == 200


def test_filter_without_filters_returns_all(ids: list[str]) -> None:
    from pages import home

    selected, text = home._filter([], [], [], [])
    assert selected == ids
    assert text.startswith(f"{len(ids)} of {len(ids)}")


def test_multi_valued_filter(ids: list[str]) -> None:
    from pages import home

    courses = get_data().courses
    topic = explode(courses, "topics").mode()[0]
    selected, _ = home._filter(["topics"], [[topic]], [], [])
    assert selected
    assert all(topic in courses.set_index(ID).loc[i, "topics"] for i in selected)


def test_table_rows_are_json_without_nan(ids: list[str]) -> None:
    from pages import home

    rows = home._table(ids)
    assert len(rows) == len(ids)
    json.dumps(rows, allow_nan=False)  # NaN would break the browser grid


def test_kpis(ids: list[str]) -> None:
    from pages import home

    n, *_ = home._kpis(ids)
    assert n == str(len(ids))


@pytest.mark.parametrize("mode", ["offer", "place"])
def test_map_figure(ids: list[str], mode: str) -> None:
    from pages import home

    fig = home._map(ids, mode, home.MAP_DEFAULTS["size"], home.MAP_DEFAULTS["color"], "carto-positron", "Viridis")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_breakdown_charts(ids: list[str]) -> None:
    from pages import home

    for by, split in home.BREAKDOWN_DEFAULTS:
        assert isinstance(home._breakdown(by, split, ids), go.Figure)


def test_compare_page(ids: list[str]) -> None:
    from pages import compare

    chosen = ids[:3]
    table, _warning = compare._table(chosen, [])
    assert table is not None
    assert compare._matrix(chosen, compare.MATRIX_DEFAULT) is not None
    assert isinstance(compare._bars(chosen, compare.BARS_DEFAULT), go.Figure)
    assert isinstance(compare._map(chosen), go.Figure)


def test_compare_without_selection() -> None:
    from pages import compare

    table, _warning = compare._table([], [])
    assert "No offer selected" in str(table)
