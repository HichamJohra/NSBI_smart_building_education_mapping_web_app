"""Plotly figure builders shared by the pages (pure functions: DataFrame in -> go.Figure out)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative

from components.data import ID, columns_for, explode, fmt, get_data, is_numeric, label, value_counts, vocabulary

ACCENT = "#1f4e79"
NA_GREY = "#b0b7c3"
PALETTE = qualitative.Safe + qualitative.Plotly
MIN_PX, MAX_PX = 9, 38
SPREAD_DEG = 0.0025  # offers at the same place are spread around it (~250 m), so each bubble can be hovered
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))
MAX_LISTED = 10  # offers listed in the hover text of a location bubble
GRID: dict = dict(gridcolor="#e5e8ee", zerolinecolor="#c8ccd4")


def empty_figure(message: str, height: int | None = 400) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=15, color="#555"),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_layout(height=height, xaxis_visible=False, yaxis_visible=False,
                      plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
    return fig


def category_colors(col: str) -> dict[str, str]:
    """Stable colour per value of a categorical column (vocabulary order, then the other values found in the
    whole dataset), so a value keeps its colour whatever the filters."""
    values = list(vocabulary(col)["value"])
    c = get_data().courses
    if col in c.columns:
        values += sorted(v for v in explode(c, col).unique() if v not in values)
    colors = {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(values)}
    colors["n/a"] = NA_GREY
    return colors


def _shorten(text, n: int = 80) -> str:
    text = str(text or "")
    return text if len(text) <= n else text[: n - 1] + "…"


def hover_text(df: pd.DataFrame, extra_cols: list[str | None]) -> list[str]:
    """Hover text of each offer: short name, title, the 'hover' columns of the dictionary and extra columns."""
    cols: list[str] = []
    for c in columns_for("hover") + [c for c in extra_cols if c]:
        if c not in cols and c not in ("short_name", "title") and c in df.columns:
            cols.append(c)
    texts = []
    for r in df.to_dict("records"):
        lines = [f"<b>{r['short_name']}</b>"]
        if r.get("title"):
            lines.append(f"<i>{_shorten(r['title'])}</i>")
        lines += [f"{label(c, with_unit=False)}: {fmt(c, r.get(c))}" for c in cols]
        texts.append("<br>".join(lines))
    return texts


def _scaled_sizes(values: pd.Series) -> np.ndarray:
    v = values.astype(float)
    vmin, vmax = np.nanmin(v) if v.notna().any() else np.nan, np.nanmax(v) if v.notna().any() else np.nan
    if not np.isfinite(vmin) or vmax == vmin:
        return np.where(v.notna(), (MIN_PX + MAX_PX) / 2, MIN_PX - 2)
    s = MIN_PX + (MAX_PX - MIN_PX) * (v - vmin) / (vmax - vmin)
    return np.where(v.notna(), s, MIN_PX - 3)


def _spread(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Move points sharing the same position onto a small spiral around it (golden-angle spiral)."""
    lat, lon = lat.astype(float).copy(), lon.astype(float).copy()
    groups: dict[tuple, list[int]] = {}
    for i, key in enumerate(zip(np.round(lat, 4), np.round(lon, 4))):
        groups.setdefault(key, []).append(i)
    for idx in groups.values():
        if len(idx) < 2:
            continue
        lat0 = lat[idx[0]]
        for j, i in enumerate(idx):
            r, a = SPREAD_DEG * math.sqrt(j + 0.5), j * GOLDEN_ANGLE
            lat[i] += r * math.sin(a)
            lon[i] += r * math.cos(a) / max(math.cos(math.radians(lat0)), 0.2)
    return lat, lon


def _auto_view(lat: np.ndarray, lon: np.ndarray) -> tuple[dict, float]:
    center = {"lat": float((lat.min() + lat.max()) / 2), "lon": float((lon.min() + lon.max()) / 2)}
    extent = max(float(lon.max() - lon.min()), float(lat.max() - lat.min()) * 2.2, 0.02)
    zoom = max(1.0, min(12.0, math.log2(360 / extent) - 0.6))
    return center, zoom


def _locations(df: pd.DataFrame, color_col: str | None) -> pd.DataFrame:
    """One row per map position: number of offers, ids, hover text, and the colour value (numeric: mean,
    categorical: most frequent value)."""
    d = df.assign(_lat=df["latitude"].astype(float).round(5), _lon=df["longitude"].astype(float).round(5))
    rows = []
    for (lat, lon), sub in d.groupby(["_lat", "_lon"], sort=False):
        institutions = list(dict.fromkeys(sub["institution"].dropna())) if "institution" in sub else []
        place = ", ".join(str(sub.iloc[0][k]) for k in ("city", "country") if k in sub and pd.notna(sub.iloc[0][k]))
        lines = [f"<b>{'; '.join(institutions) or 'Unknown institution'}</b>", place,
                 f"{len(sub)} offer{'s' if len(sub) != 1 else ''}:"]
        lines += [f"• {_shorten(f'{r.short_name} — {r.title}' if isinstance(r.title, str) else r.short_name, 70)}"
                  for r in sub.head(MAX_LISTED).itertuples()] if "title" in sub else []
        if len(sub) > MAX_LISTED:
            lines.append(f"… and {len(sub) - MAX_LISTED} more")
        color_value = None
        if color_col:
            if is_numeric(color_col):
                color_value = float(sub[color_col].mean()) if sub[color_col].notna().any() else np.nan
                lines.append(f"{label(color_col, with_unit=False)} (mean): {fmt(color_col, color_value)}")
            else:
                vc = sub[color_col].dropna().astype(str).value_counts()
                color_value = vc.index[0] if len(vc) else None
                lines.append(f"{label(color_col, with_unit=False)} (most frequent): {color_value or 'n/a'}")
        rows.append({"latitude": lat, "longitude": lon, "n": len(sub), "ids": "|".join(sub[ID]),
                     "text": "<br>".join(x for x in lines if x), "color": color_value})
    return pd.DataFrame(rows)


def map_figure(df: pd.DataFrame, size_col: str | None, color_col: str | None, basemap: str = "carto-positron",
               colorscale: str = "Viridis", per_location: bool = False, height: int = 620) -> go.Figure:
    """Bubble map of the offers. per_location=True draws one bubble per place (size = number of offers);
    otherwise one bubble per offer, offers at the same place being spread slightly around it.
    customdata holds the course id(s) of each bubble ('id1|id2' for a place)."""
    df = df.dropna(subset=["latitude", "longitude"])
    if df.empty:
        return empty_figure("No offers to show: the dataset is empty or no offer matches the filters."
                            if len(get_data().courses) else "The dataset has no offers yet.", height)
    if per_location:
        loc = _locations(df, color_col)
        lat, lon = loc["latitude"].to_numpy(float), loc["longitude"].to_numpy(float)
        sizes = _scaled_sizes(loc["n"]) if loc["n"].nunique() > 1 else np.full(len(loc), 18.0)
        texts, custom = loc["text"].to_numpy(object), loc["ids"].to_numpy(object)
        colors = loc["color"] if color_col else None
    else:
        lat, lon = _spread(df["latitude"].to_numpy(), df["longitude"].to_numpy())
        sizes = _scaled_sizes(df[size_col]) if size_col else np.full(len(df), 15.0)
        texts = np.array(hover_text(df, [size_col, color_col]), dtype=object)
        custom = df[ID].to_numpy(object)
        colors = df[color_col].reset_index(drop=True) if color_col else None

    fig = go.Figure()

    def add(mask, marker, name, showlegend=True):
        fig.add_trace(go.Scattermap(lat=lat[mask], lon=lon[mask], customdata=custom[mask], hovertext=texts[mask],
                                    hovertemplate="%{hovertext}<extra></extra>", mode="markers",
                                    marker=marker, name=name, showlegend=showlegend))

    if colors is not None and is_numeric(color_col):
        vals = pd.to_numeric(colors, errors="coerce").to_numpy(float)
        has = ~np.isnan(vals)
        if has.any():
            add(has, dict(size=sizes[has], color=vals[has], colorscale=colorscale, opacity=0.85,
                          colorbar=dict(title=dict(text=f"<b>{label(color_col)}</b>", side="right"),
                                        tickfont=dict(weight="bold"), thickness=14)),
                label(color_col, with_unit=False), showlegend=False)
        if (~has).any():
            add(~has, dict(size=sizes[~has], color=NA_GREY, opacity=0.8), "n/a")
    elif colors is not None:
        groups = colors.fillna("n/a").astype(str).to_numpy()
        palette = category_colors(color_col)
        order = [v for v in palette if v in set(groups)] + sorted(set(groups) - set(palette))
        for g in order:
            m = groups == g
            add(m, dict(size=sizes[m], color=palette.get(g, NA_GREY), opacity=0.85), g)
    else:
        add(np.ones(len(lat), bool), dict(size=sizes, color=ACCENT, opacity=0.8),
            "Places" if per_location else "Offers", showlegend=False)
    center, zoom = _auto_view(lat, lon)
    fig.update_layout(
        map=dict(style=basemap, center=center, zoom=zoom),
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title=dict(text=label(color_col, with_unit=False) if color_col else ""),
                    bgcolor="rgba(255,255,255,0.85)", x=0.01, y=0.99, xanchor="left", yanchor="top"),
        uirevision=f"{size_col}-{color_col}-{per_location}",  # keep zoom when only the filters change
    )
    return fig


def count_bars(df: pd.DataFrame, by: str | None, split: str | None = None) -> go.Figure:
    """Horizontal bars: number of offers per value of `by` (multi-valued columns: an offer counts once for each
    of its values), optionally stacked by the values of a single-valued column `split`."""
    if not by:
        return empty_figure("Choose a parameter", 300)
    long = explode(df, by)
    if long.empty:
        return empty_figure("No values for the offers shown", 300)
    order = list(value_counts(df, by).index)
    height = max(280, 30 * len(order) + 110)
    fig = go.Figure()
    if split and split != by:
        groups = df[split].reindex(long.index).fillna("n/a").astype(str)
        table = pd.crosstab(long.to_numpy(), groups.to_numpy())
        palette = category_colors(split)
        cols = [v for v in palette if v in table.columns] + [v for v in table.columns if v not in palette]
        for g in cols:
            vals = table[g].reindex(order).fillna(0)
            fig.add_trace(go.Bar(y=order, x=vals, name=g, orientation="h", marker_color=palette.get(g, NA_GREY),
                                 hovertemplate=f"%{{y}}<br>{g}: %{{x}} offers<extra></extra>"))
        fig.update_layout(barmode="stack", legend=dict(title=dict(text=label(split, with_unit=False)),
                                                       orientation="h", y=-0.12 - 60 / height, x=0))
        height += 60
    else:
        counts = long.value_counts().reindex(order)
        fig.add_trace(go.Bar(y=order, x=counts, orientation="h", marker_color=ACCENT, text=counts,
                             textposition="outside", cliponaxis=False,
                             hovertemplate="%{y}: %{x} offers<extra></extra>"))
    fig.update_layout(height=height, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=10, r=30, t=10, b=40),
                      xaxis=dict(title=dict(text="Number of offers"), **GRID),
                      yaxis=dict(autorange="reversed", automargin=True))
    return fig


def compare_bars(df: pd.DataFrame, col: str | None, height: int = 340) -> go.Figure:
    """One horizontal bar per offer for a numeric parameter ('n/a' when missing)."""
    if df.empty or not col or col not in df.columns:
        return empty_figure("Select offers and a parameter", height)
    vals = df[col].astype(float)
    if vals.isna().all():
        return empty_figure(f"No values of '{label(col, with_unit=False)}' for the selected offers", height)
    names = df["short_name"].astype(str).tolist()
    colors = [NA_GREY if pd.isna(v) else PALETTE[i % len(PALETTE)] for i, v in enumerate(vals)]
    text = [fmt(col, v) for v in vals]
    fig = go.Figure(go.Bar(x=vals.fillna(0), y=names, orientation="h", marker_color=colors, text=text,
                           textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.update_layout(height=max(height, 50 * len(names) + 80), plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=10, r=60, t=10, b=40), xaxis=dict(title=dict(text=label(col)), **GRID),
                      yaxis=dict(autorange="reversed", automargin=True))
    return fig


def points_map(df: pd.DataFrame, height: int | None = 420) -> go.Figure:
    """Map of a few offers, one colour per offer (same order and colours as the compare charts)."""
    d = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if d.empty:
        return empty_figure("No coordinates for the selected offers", height)
    pos = {r[ID]: i for i, r in enumerate(df.to_dict("records"))}
    lat, lon = _spread(d["latitude"].to_numpy(), d["longitude"].to_numpy())
    texts = hover_text(d, [])
    fig = go.Figure()
    for i, r in enumerate(d.to_dict("records")):
        fig.add_trace(go.Scattermap(lat=[lat[i]], lon=[lon[i]], mode="markers", name=str(r["short_name"]),
                                    marker=dict(size=16, color=PALETTE[pos[r[ID]] % len(PALETTE)]),
                                    hovertext=[texts[i]], hovertemplate="%{hovertext}<extra></extra>"))
    center, zoom = _auto_view(lat, lon)
    fig.update_layout(map=dict(style="carto-positron", center=center, zoom=min(zoom, 11)), height=height,
                      margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(bgcolor="rgba(255,255,255,0.85)", x=0.01, y=0.99, xanchor="left", yanchor="top"))
    return fig
