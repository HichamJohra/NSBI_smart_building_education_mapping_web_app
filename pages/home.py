"""Overview: KPIs, filters, map of the offers, breakdown charts and full table (with selection for comparison)."""
from typing import Any

import dash
import dash_ag_grid as dag
import numpy as np
import pandas as pd
from dash import ALL, MATCH, Input, Output, Patch, State, callback, ctx, dcc, html, no_update

from components.data import (ID, ONLINE_MODES, PROGRAMME_TYPES, all_columns, columns_for, dropdown_options, dtype,
                             get_data, get_offers, has_data, is_multi, label, match_values, tooltip, value_options)
from components.figures import count_bars, map_figure
from components.ui import APP_SHORT, MAX_COMPARE, PERSIST, card, control, ext_link, graph, kpi

dash.register_page(__name__, path="/", name="Overview", order=0, title=f"Overview · {APP_SHORT}")

BASEMAPS = [
    {"label": "Light (Carto Positron)", "value": "carto-positron"},
    {"label": "OpenStreetMap", "value": "open-street-map"},
    {"label": "Carto Voyager", "value": "carto-voyager"},
    {"label": "Dark", "value": "carto-darkmatter"},
]
COLORSCALES = ["Viridis", "RdYlGn", "Plasma", "Blues", "Turbo"]
DEFAULT_CAT_FILTER = "topics"                      # parameter pre-selected in the first category filter
MAP_DEFAULTS = {"size": "ects", "color": "level"}  # pre-selected bubble size and colour
BREAKDOWN_DEFAULTS = [("topics", "level"), ("country", "delivery_mode")]  # (count by, split by) of the two charts
HIDDEN: Any = {"display": "none"}

# Component settings as module constants. Typed as Any because Dash 3+ / dash-ag-grid declare these props as
# TypedDicts, which makes IDEs flag plain dict literals (the values themselves are standard options).
SLIDER_TOOLTIP: Any = {"placement": "bottom", "always_visible": True}
MAP_MODES: Any = [{"label": " Per offer", "value": "offer"}, {"label": " Per place", "value": "place"}]
GRID_DEFAULT_COLDEF: Any = {"sortable": True, "filter": True, "floatingFilter": True, "resizable": True}
GRID_OPTIONS: Any = {
    "pagination": True, "paginationPageSize": 20, "enableCellTextSelection": True, "tooltipShowDelay": 300,
    # tick boxes to select offers for the comparison (clicking a row does not select it, so text can be copied)
    "rowSelection": {"mode": "multiRow", "checkboxes": True, "headerCheckbox": True, "enableClickSelection": False,
                     "selectAll": "filtered"},
    "selectionColumnDef": {"pinned": "left", "width": 50},
}
GRID_ROW_ID = f"params.data.{ID}"  # keeps ticked rows when the filters change the table content
GRID_CSV_EXPORT: Any = {"fileName": "nsbi_smart_building_education.csv"}
GRID_STYLE: Any = {"height": "560px", "width": "100%"}

# Hover descriptions of the KPI cards (all KPIs are computed on the offers matching the filters)
KPI_HELP = {
    "n": "Offers shown\nNumber of educational offers (programmes, courses, PhD courses, summer schools, MOOCs, "
         "trainings…) that match all active filters. The map, charts and table show these offers only. "
         "Programmes = degree programmes and specialisations.",
    "inst": "Institutions\nNumber of different institutions offering the offers shown, and the number of cities "
            "where they are taught.",
    "countries": "Countries\nNumber of different countries among the offers shown, and their regions.",
    "online": "Online access\nShare of the offers shown that can be followed online: delivery mode Online, Hybrid "
              "(each participant chooses on site or online) or Blended (mix of on-site and online parts). "
              "Computed over the offers whose delivery mode is known.",
}


def _pick(preferred: str | None, options: list[str], fallback_index: int = 0) -> str | None:
    """Default dropdown value: the preferred parameter, else a fallback that has data."""
    options = [o for o in options if has_data(o)]
    if preferred in options:
        return preferred
    return options[fallback_index] if len(options) > fallback_index else (options[0] if options else None)


def _color_columns() -> list[str]:
    """Bubble colour: numeric and single-valued categorical parameters (one colour per offer)."""
    return [c for c in columns_for("map_color", include_empty=True) if not is_multi(c)]


def _column_defs() -> list[dict]:
    defs = []
    for c in all_columns():
        d: dict = {"field": c, "headerName": label(c), "headerTooltip": tooltip(c), "minWidth": 120}
        t = dtype(c)
        d["filter"] = "agNumberColumnFilter" if t == "numeric" else "agTextColumnFilter"
        if t == "url":
            # renderer defined in assets/dashAgGridComponentFunctions.js
            d.update(cellRenderer="ExternalLink", minWidth=100, filter=False)
        if c == "short_name":
            d.update(pinned="left", minWidth=160)
        if c in ("title", "description", "learning_outcomes"):
            d.update(minWidth=280, tooltipField=c)
        defs.append(d)
    return defs


def _placeholder(col: str | None) -> str:
    return "Contains any of… (all values)" if col and is_multi(col) else "All values"


# ----------------------------------------------------------------- dynamic filter rows
def _cat_row(index: int, param: str | None = None, values: list | None = None) -> html.Div:
    """One category filter: parameter dropdown + values dropdown + remove button (values: restored selection)."""
    cols = columns_for("filter", "categorical", include_empty=True)
    param = param if param in cols else None
    opts = value_options(param)
    allowed = {o["value"] for o in opts}
    values = [v for v in (values or []) if v in allowed]
    return html.Div(id={"type": "catf-row", "index": index}, className="filter-row", children=[
        dcc.Dropdown(id={"type": "catf-param", "index": index}, options=dropdown_options(cols), value=param,
                     placeholder="Choose a category parameter…"),
        dcc.Dropdown(id={"type": "catf-vals", "index": index}, options=opts, value=values, multi=True,
                     placeholder=_placeholder(param)),
        html.Button("✕", id={"type": "catf-del", "index": index}, className="btn-icon", title="Remove this filter"),
    ])


def _num_row(index: int, param: str | None = None, rng: list | None = None) -> html.Div:
    """One numeric filter: parameter dropdown + range slider + remove button (rng: restored range)."""
    cols = columns_for("filter", "numeric", include_empty=True)
    param = param if param in cols else None
    lo, hi, val, marks, step, disabled = _range_config(param)
    if param and rng and len(rng) == 2:
        val = [max(lo, min(hi, float(rng[0]))), max(lo, min(hi, float(rng[1])))]
    return html.Div(id={"type": "numf-row", "index": index}, className="filter-row", children=[
        dcc.Dropdown(id={"type": "numf-param", "index": index}, options=dropdown_options(cols), value=param,
                     placeholder="Choose a numeric parameter…"),
        html.Div(className="range-block", children=dcc.RangeSlider(
            id={"type": "numf-range", "index": index}, min=lo, max=hi, value=val, marks=marks, step=step,
            disabled=disabled, tooltip=SLIDER_TOOLTIP)),
        html.Button("✕", id={"type": "numf-del", "index": index}, className="btn-icon", title="Remove this filter"),
    ])


def _breakdown_block(index: int, by: str, split: str) -> html.Div:
    by_cols = columns_for("breakdown", "categorical", include_empty=True)
    split_cols = columns_for("breakdown_split", "single", include_empty=True)
    return html.Div([
        html.Div(className="grid-2", children=[
            control("Count offers by", dcc.Dropdown(id={"type": "brk-by", "index": index},
                                                    options=dropdown_options(by_cols), value=_pick(by, by_cols, index),
                                                    clearable=False, **PERSIST)),
            control("Split by", dcc.Dropdown(id={"type": "brk-split", "index": index},
                                             options=dropdown_options(split_cols),
                                             value=split if has_data(split) else None, clearable=True,
                                             placeholder="No split", **PERSIST)),
        ]),
        graph({"type": "brk-fig", "index": index}),
    ])


def layout(**_):
    size_cols = columns_for("map_size", "numeric", include_empty=True)
    color_cols = _color_columns()
    n_total = len(get_data().courses)

    filters = card(
        [
            html.Div(className="grid-2 filters-grid", children=[
                html.Div([
                    html.Label("Category filters", className="control-label"),
                    html.Div(id="db-catf-list", children=[_cat_row(0, DEFAULT_CAT_FILTER)]),
                    html.Button("+ Add category filter", id="db-catf-add", className="btn-light"),
                ]),
                html.Div([
                    html.Label("Numeric filters", className="control-label"),
                    html.Div(id="db-numf-list", children=[_num_row(0)]),
                    html.Button("+ Add numeric filter", id="db-numf-add", className="btn-light"),
                ]),
            ]),
            html.Div(className="filter-footer", children=[
                html.Span(id="db-filter-count", className="muted"),
                html.Button("Reset filters", id="db-reset", className="btn"),
            ]),
        ],
        title="Filters",
        subtitle="Filters apply to the map, the charts and the table, and are combined (AND). For parameters with "
                 "several values per offer (e.g. topics, languages), an offer matches when it has any of the "
                 "selected values. Offers without a value for a numeric filter parameter are excluded while that "
                 "filter is active.",
    )

    map_card = card(
        [
            html.Div(className="grid-5", children=[
                control("Bubbles", dcc.RadioItems(id="db-map-mode", options=MAP_MODES, value="offer", inline=True,
                                                  className="radio", **PERSIST),
                        "Per offer: one bubble per offer; offers taught at the same place are spread slightly "
                        "around it.\nPer place: one bubble per campus or venue; its size is the number of offers "
                        "and its colour the mean (numeric) or most frequent value (category)."),
                control("Bubble size", dcc.Dropdown(id="db-size", options=dropdown_options(size_cols),
                                                    value=_pick(MAP_DEFAULTS["size"], size_cols), clearable=True,
                                                    placeholder="Same size", **PERSIST)),
                control("Bubble colour", dcc.Dropdown(id="db-color", options=dropdown_options(color_cols),
                                                      value=_pick(MAP_DEFAULTS["color"], color_cols), clearable=True,
                                                      placeholder="Single colour", **PERSIST)),
                control("Colour scale (numeric)", dcc.Dropdown(id="db-cscale", options=COLORSCALES, value="Viridis",
                                                               clearable=False, **PERSIST)),
                control("Map background", dcc.Dropdown(id="db-basemap", options=BASEMAPS, value="carto-positron",
                                                       clearable=False, **PERSIST)),
            ]),
            graph("db-map"),
            html.Div(id="db-selected", className="selected-panel",
                     children="Click a bubble to see the offer(s), open their web page or add them to the comparison."),
            html.Div(id="db-cmp-status-map", className="cmp-status"),
        ],
        title="Map of education offers",
        subtitle="Offers are placed at the campus or venue where they are taught (online-only offers at the "
                 "providing department). Hover for details; scroll to zoom.",
    )

    breakdown_card = card(
        html.Div(className="grid-2", children=[_breakdown_block(i, by, split)
                                                for i, (by, split) in enumerate(BREAKDOWN_DEFAULTS)]),
        title="What is offered",
        subtitle="Number of offers per value of a parameter, optionally split by a second one. For parameters with "
                 "several values per offer (e.g. topics), an offer is counted once for each of its values.",
    )

    table_card = card(
        [
            html.Div(className="table-toolbar", children=[
                dcc.Input(id="db-search", type="search", placeholder="Search all columns…", debounce=False,
                          className="search", **PERSIST),
                html.Button("Add ticked offers to comparison", id="db-addsel", className="btn"),
                html.Button("Export CSV", id="db-export", className="btn"),
                html.Span(id="db-cmp-status-table", className="cmp-status"),
            ]),
            dag.AgGrid(
                id="db-grid",
                rowData=[],
                columnDefs=_column_defs(),
                defaultColDef=GRID_DEFAULT_COLDEF,
                dashGridOptions=GRID_OPTIONS,
                getRowId=GRID_ROW_ID,
                csvExportParams=GRID_CSV_EXPORT,
                style=GRID_STYLE,
            ),
        ],
        title="All offers",
        subtitle="Sort and filter each column from its header, or search across all columns. Scroll sideways for all "
                 "parameters. Tick offers (up to 6) and add them to the comparison. The table shows the filtered "
                 "offers only.",
    )

    head_note = (f"Courses and programmes on smart building technologies: where they are taught, what they cover "
                 f"and how to take them. {n_total} offers in the dataset." if n_total else
                 "Courses and programmes on smart building technologies. The dataset has no offers yet.")
    return html.Div([
        html.Div(className="page-head", children=[html.H1("Smart building education"), html.P(head_note)]),
        html.Div(className="kpi-row", children=[
            kpi("Offers shown", "db-kpi-n", "db-kpi-n-sub", description=KPI_HELP["n"]),
            kpi("Institutions", "db-kpi-inst", "db-kpi-inst-sub", description=KPI_HELP["inst"]),
            kpi("Countries", "db-kpi-countries", "db-kpi-countries-sub", description=KPI_HELP["countries"]),
            kpi("Online access", "db-kpi-online", "db-kpi-online-sub", description=KPI_HELP["online"]),
        ]),
        filters,
        map_card,
        breakdown_card,
        table_card,
        dcc.Store(id="db-ids"),
        dcc.Store(id="db-init", data=True),  # fires once when the page is opened -> restores the filter rows
    ])


# ----------------------------------------------------------------- callbacks: filter rows
def _range_config(col: str | None) -> tuple[Any, ...]:
    if not col:
        return 0, 1, [0, 1], None, None, True
    s = get_data().courses[col].dropna().astype(float)
    if s.empty:
        return 0, 1, [0, 1], None, None, True
    lo, hi = float(np.floor(s.min() * 100) / 100), float(np.ceil(s.max() * 100) / 100)
    if lo == hi:
        hi = lo + 1
    step = 1 if (s % 1 == 0).all() and (hi - lo) >= 5 else float(10 ** np.floor(np.log10((hi - lo) / 100)))
    marks = {lo: f"{lo:g}", hi: f"{hi:g}"}
    return lo, hi, [lo, hi], marks, step, False


def _edit_rows(row_ids, make_row):
    """Shared add/remove logic for the two filter lists (keeps at least one row)."""
    trig = ctx.triggered_id
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return no_update  # a new remove button appeared (n_clicks None), not a click
    indices = [r["index"] for r in row_ids]
    p = Patch()
    if isinstance(trig, str):  # "+ Add" button
        p.append(make_row(max(indices, default=-1) + 1))
        return p
    if len(indices) <= 1 or trig["index"] not in indices:
        return no_update
    del p[indices.index(trig["index"])]
    return p


@callback(
    Output("db-catf-list", "children"),
    Input("db-catf-add", "n_clicks"), Input({"type": "catf-del", "index": ALL}, "n_clicks"),
    State({"type": "catf-row", "index": ALL}, "id"), prevent_initial_call=True,
)
def _edit_cat_filters(_add, _dels, row_ids):
    return _edit_rows(row_ids, _cat_row)


@callback(
    Output("db-numf-list", "children"),
    Input("db-numf-add", "n_clicks"), Input({"type": "numf-del", "index": ALL}, "n_clicks"),
    State({"type": "numf-row", "index": ALL}, "id"), prevent_initial_call=True,
)
def _edit_num_filters(_add, _dels, row_ids):
    return _edit_rows(row_ids, _num_row)


@callback(Output({"type": "catf-del", "index": ALL}, "style"), Input({"type": "catf-row", "index": ALL}, "id"))
def _cat_del_visibility(row_ids):
    return [HIDDEN if len(row_ids) <= 1 else {} for _ in row_ids]


@callback(Output({"type": "numf-del", "index": ALL}, "style"), Input({"type": "numf-row", "index": ALL}, "id"))
def _num_del_visibility(row_ids):
    return [HIDDEN if len(row_ids) <= 1 else {} for _ in row_ids]


@callback(
    Output({"type": "catf-vals", "index": MATCH}, "options"), Output({"type": "catf-vals", "index": MATCH}, "value"),
    Output({"type": "catf-vals", "index": MATCH}, "placeholder"),
    Input({"type": "catf-param", "index": MATCH}, "value"), prevent_initial_call=True,
)
def _cat_options(col):
    return value_options(col), [], _placeholder(col)


@callback(
    Output({"type": "numf-range", "index": MATCH}, "min"), Output({"type": "numf-range", "index": MATCH}, "max"),
    Output({"type": "numf-range", "index": MATCH}, "value"), Output({"type": "numf-range", "index": MATCH}, "marks"),
    Output({"type": "numf-range", "index": MATCH}, "step"), Output({"type": "numf-range", "index": MATCH}, "disabled"),
    Input({"type": "numf-param", "index": MATCH}, "value"), prevent_initial_call=True,
)
def _cfg_range(col):
    return _range_config(col)


@callback(
    Output("db-catf-list", "children", allow_duplicate=True),
    Output("db-numf-list", "children", allow_duplicate=True),
    Output("db-search", "value"),
    Input("db-reset", "n_clicks"), prevent_initial_call=True,
)
def _reset(n):
    base = (n or 0) * 1000  # fresh ids so no stale component state is reused
    return [_cat_row(base, DEFAULT_CAT_FILTER)], [_num_row(base)], ""


# ----------------------------------------------------------------- callbacks: filter memory (per browser tab)
RESTORED_BASE = 100  # index base of restored filter rows


@callback(
    Output("db-catf-list", "children", allow_duplicate=True),
    Output("db-numf-list", "children", allow_duplicate=True),
    Input("db-init", "data"), State("mem-db-filters", "data"),
    prevent_initial_call="initial_duplicate",
)
def _restore_filters(_, memory):
    """When the Overview opens, rebuild the filter rows saved in this tab's session memory."""
    if not memory:
        return no_update, no_update
    cats = memory.get("cat") or []
    nums = memory.get("num") or []
    cat_rows = [_cat_row(RESTORED_BASE + i, p, v) for i, (p, v) in enumerate(cats)]
    num_rows = [_num_row(RESTORED_BASE + i, p, r) for i, (p, r) in enumerate(nums)]
    return (cat_rows or [_cat_row(RESTORED_BASE, DEFAULT_CAT_FILTER)]), (num_rows or [_num_row(RESTORED_BASE)])


@callback(
    Output("mem-db-filters", "data"),
    Input({"type": "catf-param", "index": ALL}, "value"), Input({"type": "catf-vals", "index": ALL}, "value"),
    Input({"type": "numf-param", "index": ALL}, "value"), Input({"type": "numf-range", "index": ALL}, "value"),
    Input("db-catf-list", "children"), Input("db-numf-list", "children"),
    prevent_initial_call=True,  # never overwrite the memory with the defaults of a freshly opened page
)
def _save_filters(cat_params, cat_vals, num_params, num_ranges, _cat_children, _num_children):
    """Save the current filter rows (parameter + selection) in this tab's session memory."""
    return {
        "cat": [[p, v or []] for p, v in zip(cat_params, cat_vals)],
        "num": [[p, r if p else None] for p, r in zip(num_params, num_ranges)],
    }


@callback(
    Output("db-ids", "data"), Output("db-filter-count", "children"),
    Input({"type": "catf-param", "index": ALL}, "value"), Input({"type": "catf-vals", "index": ALL}, "value"),
    Input({"type": "numf-param", "index": ALL}, "value"), Input({"type": "numf-range", "index": ALL}, "value"),
)
def _filter(cat_params, cat_vals, num_params, num_ranges):
    c = get_data().courses
    m = pd.Series(True, index=c.index)
    n_active = 0
    for col, vals in zip(cat_params, cat_vals):
        if col and vals and col in c.columns:
            m &= match_values(c, col, vals)
            n_active += 1
    for col, rng in zip(num_params, num_ranges):
        if col and rng and col in c.columns:
            m &= c[col].astype(float).between(rng[0] - 1e-9, rng[1] + 1e-9)
            n_active += 1
    ids = c.loc[m, ID].tolist()
    return ids, f"{len(ids)} of {len(c)} offers match · {n_active} active filter(s)"


# ----------------------------------------------------------------- callbacks: views
def _subset(ids) -> pd.DataFrame:
    c = get_data().courses
    return c if ids is None else c[c[ID].isin(ids)]


def _nunique(d: pd.DataFrame, col: str) -> int:
    return int(d[col].nunique()) if col in d.columns else 0


@callback(
    Output("db-kpi-n", "children"), Output("db-kpi-n-sub", "children"),
    Output("db-kpi-inst", "children"), Output("db-kpi-inst-sub", "children"),
    Output("db-kpi-countries", "children"), Output("db-kpi-countries-sub", "children"),
    Output("db-kpi-online", "children"), Output("db-kpi-online-sub", "children"),
    Input("db-ids", "data"),
)
def _kpis(ids):
    d = _subset(ids)
    n = len(d)
    prog = int(d["offer_type"].isin(PROGRAMME_TYPES).sum()) if "offer_type" in d.columns else 0
    n_sub = f"{prog} programme{'s' if prog != 1 else ''} · {n - prog} other offer{'s' if n - prog != 1 else ''}"
    cities = _nunique(d, "city")
    regions = ", ".join(sorted(d["region"].dropna().unique())) if "region" in d.columns else ""
    if "delivery_mode" in d.columns and d["delivery_mode"].notna().any():
        known = int(d["delivery_mode"].notna().sum())
        online = int(d["delivery_mode"].isin(ONLINE_MODES).sum())
        online_val, online_sub = f"{100 * online / known:.0f} %", f"{online} of {known} offers (known delivery mode)"
    else:
        online_val, online_sub = "–", "no delivery mode data for these offers"
    return (f"{n}", n_sub, f"{_nunique(d, 'institution')}", f"in {cities} cit{'y' if cities == 1 else 'ies'}",
            f"{_nunique(d, 'country')}", regions or "–", online_val, online_sub)


@callback(Output("db-size", "disabled"), Input("db-map-mode", "value"))
def _size_disabled(mode):
    return mode == "place"  # per place, the bubble size is the number of offers


@callback(
    Output("db-map", "figure"),
    Input("db-ids", "data"), Input("db-map-mode", "value"), Input("db-size", "value"), Input("db-color", "value"),
    Input("db-basemap", "value"), Input("db-cscale", "value"),
)
def _map(ids, mode, size_col, color_col, basemap, cscale):
    return map_figure(_subset(ids), size_col, color_col, basemap=basemap, colorscale=cscale,
                      per_location=mode == "place")


@callback(
    Output({"type": "brk-fig", "index": MATCH}, "figure"),
    Input({"type": "brk-by", "index": MATCH}, "value"), Input({"type": "brk-split", "index": MATCH}, "value"),
    Input("db-ids", "data"),
)
def _breakdown(by, split, ids):
    return count_bars(_subset(ids), by, split)


@callback(Output("db-grid", "rowData"), Input("db-ids", "data"))
def _table(ids):
    d = _subset(ids)
    return d.astype(object).where(d.notna(), None).to_dict("records")


@callback(Output("db-grid", "dashGridOptions"), Input("db-search", "value"))
def _search(text):
    p = Patch()
    p["quickFilterText"] = text or ""
    return p


@callback(Output("db-grid", "exportDataAsCsv"), Input("db-export", "n_clicks"), prevent_initial_call=True)
def _export(_):
    return True


# ----------------------------------------------------------------- callbacks: selection and comparison
@callback(Output("db-selected", "children"), Input("db-map", "clickData"), prevent_initial_call=True)
def _select(click):
    """List the offer(s) of the clicked bubble, with their web page and an 'Add to comparison' button."""
    try:
        custom = click["points"][0]["customdata"]
    except (TypeError, KeyError, IndexError):
        return no_update
    if isinstance(custom, list):
        custom = custom[0]
    d = get_offers(str(custom).split("|"))
    if d.empty:
        return no_update
    items = []
    for r in d.to_dict("records"):
        where = ", ".join(str(r[k]) for k in ("institution", "city") if isinstance(r.get(k), str))
        items.append(html.Li([
            html.B(r["short_name"]), f" — {r.get('title') or ''}", html.Span(f" ({where})" if where else "",
                                                                             className="muted"),
            " ", ext_link("Web page ↗", r.get("url"), "link-strong"),
            html.Button("Add to comparison", id={"type": "db-addone", "index": r[ID]}, className="btn btn-small"),
        ]))
    head = f"{len(d)} offers at this place:" if len(d) > 1 else "Selected offer:"
    return html.Div([html.Span(head), html.Ul(items)])


@callback(
    Output("mem-cmp-ids", "data", allow_duplicate=True),
    Input("db-addsel", "n_clicks"), Input({"type": "db-addone", "index": ALL}, "n_clicks"),
    State("db-grid", "selectedRows"), State("mem-cmp-ids", "data"),
    prevent_initial_call=True,
)
def _add_to_comparison(_add_selected, _add_one, selected_rows, memory):
    """Add the ticked table rows, or the offer of the clicked button, to the comparison (at most MAX_COMPARE)."""
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return no_update  # a new 'Add' button appeared (n_clicks None), not a click
    trig = ctx.triggered_id
    if trig == "db-addsel":
        new = [r[ID] for r in (selected_rows or []) if isinstance(r, dict) and r.get(ID)]
    else:
        new = [trig["index"]]
    current = list(memory or [])
    for i in new:
        if i not in current and len(current) < MAX_COMPARE:
            current.append(i)
    return current


@callback(
    Output("db-cmp-status-map", "children"), Output("db-cmp-status-table", "children"),
    Input("mem-cmp-ids", "data"),
)
def _comparison_status(memory):
    """Number of offers selected for comparison (shown below the map and above the table)."""
    n = len(memory or [])
    if not n:
        text = f"Comparison: no offer selected yet (up to {MAX_COMPARE})."
        return text, text
    full = " (maximum reached)" if n >= MAX_COMPARE else ""
    return tuple(html.Span([f"Comparison: {n} of {MAX_COMPARE} offers{full}.",
                            dcc.Link("Open the comparison →", href="/compare", className="link-strong")])
                 for _ in range(2))
