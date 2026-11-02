"""Compare offers: key facts side by side, content coverage matrix, numeric bars and location map.

The selection is kept in the per-tab memory 'mem-cmp-ids' (app.py), which the Overview fills ('Add to
comparison'). A link /compare?course_ids=NO-001,SE-004 opens the page with these offers.
"""
from typing import Any

import dash
import pandas as pd
from dash import Input, Output, State, callback, dcc, html

from components.data import (ID, all_columns, columns_for, dropdown_options, dtype, explode, fmt, get_data,
                             get_offers, has_data, label, offer_options, tooltip, value_description, vocabulary)
from components.figures import PALETTE, compare_bars, points_map
from components.ui import APP_SHORT, GRAPH_CONFIG, MAX_COMPARE, PERSIST, card, control, ext_link

dash.register_page(__name__, path="/compare", name="Compare", order=1, title=f"Compare · {APP_SHORT}")

MATRIX_DEFAULT = "topics"  # parameter pre-selected in the content coverage matrix
BARS_DEFAULT = "ects"      # parameter pre-selected in the numeric bar chart
NOT_IN_TABLE = {"short_name"}  # shown as the column headers
TABLE_OPTIONS: Any = [{"label": " Hide empty rows", "value": "hide_empty"},
                      {"label": " Only rows that differ", "value": "diff"}]


def _default(preferred: str, cols: list[str]) -> str | None:
    with_data = [c for c in cols if has_data(c)]
    return preferred if preferred in with_data else (with_data[0] if with_data else None)


def layout(course_ids: str | None = None, **_):
    query = [i.strip() for i in (course_ids or "").split(",") if i.strip()]
    matrix_cols = columns_for("matrix", "categorical", include_empty=True)
    num_cols = columns_for("bars", "numeric", include_empty=True)
    return html.Div([
        html.Div(className="page-head", children=[
            html.H1("Compare offers"),
            html.P(f"Select 2 to {MAX_COMPARE} offers to compare them side by side, here or by ticking them in the "
                   "table of the Overview page."),
        ]),
        card(control("Offers", dcc.Dropdown(id="cmp-select", options=offer_options(), value=[], multi=True,
                                            placeholder="Choose offers to compare…"))),
        html.Div(id="cmp-warning", className="muted"),
        card([
            dcc.Checklist(id="cmp-table-opts", options=TABLE_OPTIONS, value=["hide_empty"], inline=True,
                          className="checklist", **PERSIST),
            html.Div(id="cmp-table", className="table-scroll"),
        ], title="Key facts",
            subtitle="All parameters of the dataset, grouped as on the About page. Hover a parameter name for its "
                     "definition; a blue bar marks the rows where the offers differ."),
        html.Div(className="grid-2", children=[
            card([
                control("Parameter", dcc.Dropdown(id="cmp-matrix-param", options=dropdown_options(matrix_cols),
                                                  value=_default(MATRIX_DEFAULT, matrix_cols), clearable=False,
                                                  **PERSIST)),
                html.Div(id="cmp-matrix", className="table-scroll"),
            ], title="Content coverage",
                subtitle="Which values each offer has, e.g. the topics it covers. All values of the harmonised "
                         "vocabulary are listed, also those no selected offer covers."),
            card([
                control("Parameter", dcc.Dropdown(id="cmp-bars-param", options=dropdown_options(num_cols),
                                                  value=_default(BARS_DEFAULT, num_cols), clearable=False,
                                                  **PERSIST)),
                dcc.Graph(id="cmp-bars", config=GRAPH_CONFIG),
            ], title="Size, duration and cost", subtitle="Compare a numeric parameter (grey: not available)."),
        ]),
        card(dcc.Graph(id="cmp-map", config=GRAPH_CONFIG), title="Location"),
        dcc.Store(id="cmp-init", data={"query": query}),  # fires once when the page opens -> restores the selection
    ])


# ----------------------------------------------------------------- callbacks: selection memory
@callback(Output("cmp-select", "value"), Input("cmp-init", "data"), State("mem-cmp-ids", "data"))
def _restore(init, memory):
    """Selection when the page opens: offers given in the link (?course_ids=…), else the tab's memory."""
    known = set(get_data().courses[ID])
    ids = (init or {}).get("query") or memory or []
    return [i for i in ids if i in known][:MAX_COMPARE]


@callback(Output("mem-cmp-ids", "data", allow_duplicate=True), Input("cmp-select", "value"),
          prevent_initial_call=True)
def _save(ids):
    return list(ids or [])[:MAX_COMPARE]


# ----------------------------------------------------------------- callbacks: views
def _selected(ids) -> pd.DataFrame:
    return get_offers(list(ids or [])[:MAX_COMPARE])


def _swatch(i: int) -> html.Span:
    return html.Span(className="swatch", style={"background": PALETTE[i % len(PALETTE)]})


def _header(d: pd.DataFrame) -> html.Thead:
    """Table header: one column per offer (colour swatch as in the charts + short name, title on hover)."""
    cells = [html.Th([_swatch(i), str(r["short_name"])], title=str(r.get("title") or ""))
             for i, r in enumerate(d.to_dict("records"))]
    return html.Thead(html.Tr([html.Th("")] + cells))


def _cell(col: str, value) -> html.Td:
    if dtype(col) == "url":
        return html.Td(ext_link("Open ↗", value) if isinstance(value, str) and value else "–")
    text = fmt(col, value)
    return html.Td("–" if text == "n/a" else text, className="muted" if text == "n/a" else None)


@callback(
    Output("cmp-table", "children"), Output("cmp-warning", "children"),
    Input("cmp-select", "value"), Input("cmp-table-opts", "value"),
)
def _table(ids, opts):
    opts = opts or []
    d = _selected(ids)
    warn = ""
    if len(ids or []) > MAX_COMPARE:
        warn = f"Only the first {MAX_COMPARE} offers are compared."
    elif len(d) < 2:
        warn = "Select at least two offers."
    if d.empty:
        return html.P("No offer selected.", className="muted"), warn
    dictionary = get_data().dictionary
    groups = dict(zip(dictionary["column"], dictionary["group"]))
    body: list = []
    current_group = None
    for c in all_columns():
        if c in NOT_IN_TABLE:
            continue
        values = [r.get(c) for r in d.to_dict("records")]
        shown = [fmt(c, v) for v in values]
        empty = all(s == "n/a" for s in shown)
        differs = len(set(shown)) > 1
        if ("hide_empty" in opts and empty) or ("diff" in opts and not differs):
            continue
        g = groups.get(c) or "Other"
        if g != current_group:
            body.append(html.Tr(html.Th(g, colSpan=len(d) + 1), className="group-row"))
            current_group = g
        body.append(html.Tr([html.Th(label(c), title=tooltip(c))] + [_cell(c, v) for v in values],
                            className="diff" if differs and len(d) > 1 else None))
    if not body:
        body = [html.Tr(html.Td("No rows to show with the current options.", colSpan=len(d) + 1))]
    return html.Table([_header(d), html.Tbody(body)], className="info-table compare-table"), warn


@callback(Output("cmp-matrix", "children"), Input("cmp-select", "value"), Input("cmp-matrix-param", "value"))
def _matrix(ids, col):
    d = _selected(ids)
    if d.empty or not col:
        return html.P("Select offers and a parameter.", className="muted")
    long = explode(d, col)
    has = {(idx, v) for idx, v in long.items()}
    values = list(vocabulary(col)["value"])
    values += sorted(v for v in long.unique() if v not in values)
    if not values:
        return html.P("No values for the selected offers.", className="muted")
    rows = []
    for v in values:
        marks = [(idx, v) in has for idx in d.index]
        desc = value_description(col, v)
        rows.append(html.Tr([html.Th(v, title=desc or None)]
                            + [html.Td("●" if m else "", className="yes" if m else None) for m in marks]
                            + [html.Td(f"{sum(marks)}/{len(d)}", className="count")]))
    head = html.Thead(html.Tr([html.Th(label(col, with_unit=False))]
                              + [html.Th([_swatch(i), str(r["short_name"])])
                                 for i, r in enumerate(d.to_dict("records"))] + [html.Th("Offers")]))
    return html.Table([head, html.Tbody(rows)], className="info-table matrix-table")


@callback(Output("cmp-bars", "figure"), Input("cmp-select", "value"), Input("cmp-bars-param", "value"))
def _bars(ids, col):
    return compare_bars(_selected(ids), col)


@callback(Output("cmp-map", "figure"), Input("cmp-select", "value"))
def _map(ids):
    return points_map(_selected(ids))
