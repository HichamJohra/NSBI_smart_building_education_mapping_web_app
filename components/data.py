"""Data access layer.

Reads data/smart_building_education_dataset.xlsx. The workbook is re-read automatically when the file
changes on disk, so editing the Excel file and refreshing the browser is enough (no restart needed).

The sheet 'data_dictionary' drives the app: label, unit, group, dtype and description of every column.
dtype values:
  numeric      numbers (filters with a range slider, bubble size, bubble colour, compare bars)
  categorical  one value per offer (category filters, bubble colour, breakdown charts)
  multi        several values separated by ';' (category filters "contains any", breakdown charts)
  text / url / date   shown in tables and on the compare page only
The sheet 'vocabulary' lists the harmonised values of categorical and multi-valued columns with a
description; it sets the order of the values in filters and charts and their hover texts.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from dash import html

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "smart_building_education_dataset.xlsx"

ID = "course_id"
MULTI_SEP = ";"
FILTER_DTYPES = ("categorical", "multi")
VOCAB_ALIASES = {"main_topic": "topics"}  # columns that share another column's vocabulary
PROGRAMME_TYPES = {"Degree programme", "Specialisation"}  # offer types counted as programmes in the KPIs
ONLINE_MODES = {"Online", "Hybrid", "Blended"}  # delivery modes that can be followed (partly) online

# Region filled in automatically from the country when the 'region' cell is empty
NORDIC = {"Denmark", "Finland", "Iceland", "Norway", "Sweden", "Faroe Islands", "Greenland", "Åland"}
BALTIC = {"Estonia", "Latvia", "Lithuania"}
EUROPE = {"Albania", "Andorra", "Austria", "Belarus", "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia",
          "Cyprus", "Czech Republic", "Czechia", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
          "Kosovo", "Liechtenstein", "Luxembourg", "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands",
          "North Macedonia", "Poland", "Portugal", "Romania", "San Marino", "Serbia", "Slovakia", "Slovenia",
          "Spain", "Switzerland", "Ukraine", "United Kingdom"}


@dataclass
class Dataset:
    courses: pd.DataFrame
    dictionary: pd.DataFrame
    vocabulary: pd.DataFrame
    sources: pd.DataFrame
    mtime: float


_cache: Dataset | None = None


def _region(country) -> str | None:
    if not isinstance(country, str):
        return None
    if country in NORDIC:
        return "Nordic"
    if country in BALTIC:
        return "Baltic"
    return "Rest of Europe" if country in EUROPE else "Outside Europe"


def _as_text(v):
    """Cell value as clean text (Excel may return numbers or dates for text columns)."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def split_multi(value) -> list[str]:
    """Values of a multi-valued cell ('a; b; c' -> ['a', 'b', 'c'])."""
    if not isinstance(value, str):
        return []
    return [p.strip() for p in value.split(MULTI_SEP) if p.strip()]


def _prepare(c: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Clean the 'courses' sheet: ids as text, numbers as floats, text trimmed, computed columns added."""
    c = c.copy()
    if ID not in c.columns:
        c[ID] = pd.Series(dtype=object)
    c[ID] = c[ID].map(_as_text)
    c = c[c[ID].notna()].copy()
    dtypes = dict(zip(d["column"], d["dtype"].astype(str).str.strip().str.lower()))
    for col in c.columns:
        if dtypes.get(col) == "numeric":
            c[col] = pd.to_numeric(c[col], errors="coerce").astype(float)
        else:
            c[col] = c[col].map(_as_text).astype(object)
    if "short_name" not in c.columns:
        c["short_name"] = None
    c["short_name"] = c["short_name"].fillna(c[ID])
    if "country" in c.columns:
        if "region" not in c.columns:
            c["region"] = None
        c["region"] = c["region"].fillna(c["country"].map(_region))
    if "topics" in c.columns:  # computed: number of topics (empty when no topic is given)
        n = c["topics"].map(lambda v: len(split_multi(v)))
        c["n_topics"] = n.where(n > 0).astype(float)
    return c.reset_index(drop=True)


def get_data() -> Dataset:
    """Return the dataset, reloading it if the Excel file was modified."""
    global _cache
    mtime = DATA_FILE.stat().st_mtime
    if _cache is None or _cache.mtime != mtime:
        sheets = pd.read_excel(DATA_FILE, sheet_name=None)
        d = sheets.get("data_dictionary",
                       pd.DataFrame(columns=["column", "label", "unit", "group", "dtype", "description", "hover"]))
        d = d[d["column"].notna()].fillna("").copy()
        d["dtype"] = d["dtype"].astype(str).str.strip().str.lower()
        courses = _prepare(sheets.get("courses", pd.DataFrame(columns=[ID])), d)
        d = d[d["column"].isin(courses.columns)].reset_index(drop=True)
        v = sheets.get("vocabulary", pd.DataFrame(columns=["column", "value", "description"]))
        v = v[v["column"].notna() & v["value"].notna()].fillna("").copy()
        v["value"] = v["value"].map(_as_text)
        _cache = Dataset(courses=courses, dictionary=d, vocabulary=v.reset_index(drop=True),
                         sources=sheets.get("sources", pd.DataFrame(columns=["source_id", "reference", "url",
                                                                             "used_for"])),
                         mtime=mtime)
    return _cache


# ----------------------------------------------------------------- dictionary helpers
def _meta(col: str) -> dict:
    d = get_data().dictionary
    row = d[d["column"] == col]
    return row.iloc[0].to_dict() if len(row) else {"column": col, "label": col, "unit": "", "group": "", "dtype": ""}


def label(col: str, with_unit: bool = True) -> str:
    m = _meta(col)
    lab = m.get("label") or col
    u = m.get("unit") or ""
    return f"{lab} [{u}]" if with_unit and u and u != "level" else lab


def unit(col: str) -> str:
    return _meta(col).get("unit") or ""


def description(col: str) -> str:
    """Description of a column from the data dictionary ('' if none)."""
    return str(_meta(col).get("description") or "").strip()


def dtype(col: str) -> str:
    """dtype of a column from the data dictionary; guessed from the data for undocumented columns."""
    t = str(_meta(col).get("dtype") or "").strip().lower()
    if t:
        return t
    c = get_data().courses
    return "numeric" if col in c.columns and pd.api.types.is_numeric_dtype(c[col]) else "text"


def is_numeric(col: str) -> bool:
    return dtype(col) == "numeric"


def is_multi(col: str) -> bool:
    return dtype(col) == "multi"


def n_offers() -> int:
    return len(get_data().courses)


def tooltip(col: str) -> str:
    """Hover text for a parameter: label, unit, description and data coverage."""
    lines = [label(col)]
    desc = description(col)
    if desc:
        lines.append(desc)
    c = get_data().courses
    if col in c.columns:
        lines.append(f"Values available for {int(c[col].notna().sum())} of {len(c)} offers.")
    return "\n".join(lines)


def has_data(col: str) -> bool:
    c = get_data().courses
    return col in c.columns and bool(c[col].notna().any())


def all_columns() -> list[str]:
    """All columns: data-dictionary order first, then any undocumented columns."""
    data = get_data()
    cols = [c for c in data.dictionary["column"] if c in data.courses.columns]
    return cols + [c for c in data.courses.columns if c not in cols]


def columns_for(use: str, kind: str | None = None, include_empty: bool = False) -> list[str]:
    """Parameters offered for a given use, according to their dtype.

      kind='numeric'      -> numeric parameters
      kind='categorical'  -> categorical and multi-valued parameters
      kind='single'       -> categorical parameters only (one value per offer, e.g. bubble colour)
      kind=None           -> numeric, categorical and multi-valued parameters
    Text, url and date columns are never offered in dropdowns. use='hover' returns only the columns flagged
    'Y' in the 'hover' column of the data dictionary (shown in all map pop-ups).
    Columns without any value are skipped unless include_empty=True (dropdowns then show them disabled).
    """
    if use == "hover":
        d = get_data().dictionary
        if "hover" not in d.columns:
            return []
        return d.loc[d["hover"].astype(str).str.upper().str.strip() == "Y", "column"].tolist()
    accepted = {"numeric": ("numeric",), "categorical": FILTER_DTYPES, "single": ("categorical",),
                None: ("numeric",) + FILTER_DTYPES}[kind]
    return [c for c in all_columns() if dtype(c) in accepted and (include_empty or has_data(c))]


def hover_label(text: str, title: str) -> html.Span:
    """Option label with a hover description (browser tooltip), for dropdown menus."""
    return html.Span(text, title=title, className="opt-label")


def dropdown_options(cols: list[str]) -> list[Any]:
    """Dropdown options shown as 'Group · Label', with the parameter description on hover.
    Labels are components (for the hover text), so 'search' holds the searchable text."""
    opts = []
    for c in cols:
        grp = _meta(c).get("group") or ""
        text = f"{grp} · {label(c)}" if grp else label(c)
        empty = not has_data(c)
        if empty:
            text += " (no data yet)"
        opts.append({"label": hover_label(text, tooltip(c)), "value": c, "search": f"{text} {c}",
                     "disabled": empty})  # empty parameters are listed but cannot be selected
    return opts


# ----------------------------------------------------------------- vocabulary and values
def vocabulary(col: str) -> pd.DataFrame:
    """Vocabulary rows (value, description) of a column, in the order of the 'vocabulary' sheet."""
    v = get_data().vocabulary
    return v[v["column"] == VOCAB_ALIASES.get(col, col)][["value", "description"]].reset_index(drop=True)


def value_description(col: str, value: str) -> str:
    v = vocabulary(col)
    row = v[v["value"] == value]
    return str(row.iloc[0]["description"]) if len(row) else ""


def explode(df: pd.DataFrame, col: str) -> pd.Series:
    """One entry per (offer, value): multi-valued cells are split; index = row index of df."""
    s = df[col].dropna()
    if is_multi(col):
        s = s.map(split_multi).explode().dropna()
    return s.astype(str)


def value_counts(df: pd.DataFrame, col: str) -> pd.Series:
    """Number of offers per value, ordered by the vocabulary first, then by decreasing count."""
    counts = explode(df, col).value_counts()
    order = [v for v in vocabulary(col)["value"] if v in counts.index]
    rest = [v for v in counts.index if v not in order]
    return counts.reindex(order + rest)


def value_options(col: str | None) -> list[Any]:
    """Options of a category filter: values found in the data (vocabulary order), with the number of offers
    and the vocabulary description on hover."""
    if not col:
        return []
    counts = value_counts(get_data().courses, col)
    opts = []
    for val, n in counts.items():
        desc = value_description(col, val)
        opts.append({"label": hover_label(f"{val} ({n})", f"{val}\n{desc}" if desc else val), "value": val,
                     "search": val})
    return opts


def match_values(df: pd.DataFrame, col: str, values: list[str]) -> pd.Series:
    """Boolean mask: offers whose value is one of `values` (multi-valued: contains any of them)."""
    if is_multi(col):
        wanted = set(values)
        return df[col].map(lambda v: bool(wanted.intersection(split_multi(v))))
    return df[col].astype(str).isin(values) & df[col].notna()


# ----------------------------------------------------------------- formatting
def fmt(col: str, value) -> str:
    """Human-readable value with its unit ('n/a' when missing)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    u = unit(col)
    if isinstance(value, (int, float)):
        if u == "°":
            return f"{value:.5f}°"
        if u == "EUR":
            return f"{value:,.0f} EUR".replace(",", " ")
        num = f"{int(value)}" if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{num} {u}" if u and u != "level" else num
    if is_multi(col):
        return ", ".join(split_multi(value))
    return str(value)


# ----------------------------------------------------------------- offers
def offer_options() -> list[Any]:
    """Options for selecting offers: 'short name — title', with institution, city and type on hover."""
    c = get_data().courses
    opts = []
    for r in c.to_dict("records"):
        text = f"{r['short_name']} — {r.get('title') or ''}".rstrip(" —")
        details = " · ".join(str(r[k]) for k in ("offer_type", "institution", "city", "level")
                             if isinstance(r.get(k), str) and r.get(k))
        opts.append({"label": hover_label(text, details or text), "value": r[ID],
                     "search": f"{text} {r.get('institution') or ''} {r.get('city') or ''}"})
    return opts


def get_offers(ids: list[str]) -> pd.DataFrame:
    """Rows of the given offers, in the order of `ids` (unknown ids are skipped)."""
    c = get_data().courses
    known = [i for i in ids if i in set(c[ID])]
    return c.set_index(ID).loc[known].reset_index()
