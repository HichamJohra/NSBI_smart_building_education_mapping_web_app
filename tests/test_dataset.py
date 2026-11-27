"""Integrity of data/smart_building_education_dataset.xlsx (run after every data change)."""

from __future__ import annotations

import pandas as pd
import pytest

from components.data import DATA_FILE, ID, VOCAB_ALIASES, explode, get_data, split_multi

SHEETS = ["README", "courses", "data_dictionary", "vocabulary", "sources"]
REQUIRED = [
    ID,
    "title",
    "offer_type",
    "institution",
    "city",
    "country",
    "latitude",
    "longitude",
    "location_precision",
    "level",
    "url",
    "topics",
    "main_reference",
]
DTYPES = {"text", "categorical", "multi", "numeric", "url", "date"}
COMPUTED = {"n_topics"}  # added by components.data, not stored in the Excel file


@pytest.fixture(scope="module")
def courses() -> pd.DataFrame:
    return get_data().courses


@pytest.fixture(scope="module")
def raw_dictionary() -> pd.DataFrame:
    d = pd.read_excel(DATA_FILE, sheet_name="data_dictionary")
    return d[d["column"].notna()]


def test_workbook_has_all_sheets() -> None:
    assert set(SHEETS) <= set(pd.ExcelFile(DATA_FILE).sheet_names)


def test_ids_unique_and_present(courses: pd.DataFrame) -> None:
    ids = courses[ID]
    assert ids.notna().all()
    dup = ids[ids.duplicated()].tolist()
    assert not dup, f"duplicate {ID}: {dup}"


def test_required_columns_filled(courses: pd.DataFrame) -> None:
    for col in REQUIRED:
        missing = courses.loc[courses[col].isna(), ID].tolist()
        assert not missing, f"{col} is empty for {missing}"


def test_coordinates_in_range(courses: pd.DataFrame) -> None:
    assert courses["latitude"].between(-90, 90).all()
    assert courses["longitude"].between(-180, 180).all()


def test_dictionary_matches_courses_columns(courses: pd.DataFrame, raw_dictionary: pd.DataFrame) -> None:
    stored = set(pd.read_excel(DATA_FILE, sheet_name="courses").columns)
    described = set(raw_dictionary["column"])
    assert not stored - described, f"columns without a data_dictionary row: {sorted(stored - described)}"
    assert not described - stored - COMPUTED, f"data_dictionary rows without a column: {sorted(described - stored)}"
    dtypes = set(raw_dictionary["dtype"].astype(str).str.strip().str.lower())
    assert dtypes <= DTYPES, f"unknown dtype(s): {sorted(dtypes - DTYPES)}"
    undescribed = raw_dictionary.loc[raw_dictionary["description"].isna(), "column"].tolist()
    assert not undescribed, f"columns without description: {undescribed}"


def test_numeric_values_plausible(courses: pd.DataFrame) -> None:
    ranges = {
        "eqf_level": (1, 8),
        "ects": (0, 360),
        "workload_hours": (0, 10000),
        "duration_weeks": (0, 520),
        "tuition_fee_eur": (0, 100000),
    }
    for col, (lo, hi) in ranges.items():
        values = courses[col].dropna()
        out = courses.loc[values.index[~values.between(lo, hi)], ID].tolist()
        assert not out, f"{col} outside {lo}…{hi} for {out}"


def test_values_in_vocabulary(courses: pd.DataFrame) -> None:
    vocab = get_data().vocabulary
    columns = set(vocab["column"]) | set(VOCAB_ALIASES)
    for col in sorted(columns & set(courses.columns)):
        allowed = set(vocab.loc[vocab["column"] == VOCAB_ALIASES.get(col, col), "value"])
        unknown = set(explode(courses, col)) - allowed
        assert not unknown, f"{col}: values not in the vocabulary sheet: {sorted(unknown)}"


def test_main_topic_is_one_of_the_topics(courses: pd.DataFrame) -> None:
    for _, r in courses.dropna(subset=["main_topic"]).iterrows():
        assert r["main_topic"] in split_multi(r["topics"]), r[ID]


def test_parent_programmes_exist(courses: pd.DataFrame) -> None:
    unknown = set(courses["parent_programme_id"].dropna()) - set(courses[ID])
    assert not unknown, f"unknown parent_programme_id: {sorted(unknown)}"


def test_urls_are_web_links(courses: pd.DataFrame, raw_dictionary: pd.DataFrame) -> None:
    for col in raw_dictionary.loc[raw_dictionary["dtype"].astype(str).str.strip() == "url", "column"]:
        values = courses[col].dropna().astype(str)
        bad = values[~values.str.match(r"https?://")].tolist()
        assert not bad, f"{col}: not a web link {bad}"


def test_dates_parse(courses: pd.DataFrame) -> None:
    values = courses["last_checked"].dropna()
    parsed = pd.to_datetime(values, errors="coerce", format="%Y-%m-%d")
    bad = courses.loc[values.index[parsed.isna()], ID].tolist()
    assert not bad, f"last_checked is not a YYYY-MM-DD date for {bad}"


def test_sources_unique() -> None:
    sources = get_data().sources
    assert sources["source_id"].is_unique
    assert sources["reference"].notna().all()
