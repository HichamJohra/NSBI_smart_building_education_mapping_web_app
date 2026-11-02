"""About page: the web app and its NSBI context, dataset variables, vocabulary, caveats, sources and contact."""
import dash
import pandas as pd
from dash import dcc, html
from dash.development.base_component import Component

from components.data import explode, get_data, label, unit, vocabulary
from components.ui import APP_NAME, APP_SHORT, card, ext_link

dash.register_page(__name__, path="/about", name="About", order=99, title=f"About · {APP_SHORT}")

REPOSITORY_URL = "https://github.com/HichamJohra/NSBI_smart_building_education_mapping_web_app"
NSBI_URL = "https://www.ibpsa-nordic.org/nordic-smart-building-initiative/"
IBPSA_NORDIC_URL = "https://www.ibpsa-nordic.org/"
SINTEF_COMMUNITY_URL = "https://www.sintef.no/en/community/"
MAPPING_APP_URL = "https://github.com/HichamJohra/NSBI_smart_building_mapping_web_app"
CONTACT_NAME, CONTACT_EMAIL = "Hicham Johra", "hicham.johra@sintef.no"
CONTACT_URL = "https://www.sintef.no/en/all-employees/employee/hicham.johra/"

# Columns whose vocabulary is shown on this page (in this order); other vocabularies are listed after them
VOCAB_FIRST = ["topics", "offer_type", "level", "delivery_mode", "smart_building_relevance", "target_audience"]

WHAT_IS_SHOWN = """
The app lists **educational offers related to smart building technologies**: building automation and control,
sensors and IoT, data analytics and AI, digital twins, energy flexibility, the Smart Readiness Indicator, and
related topics (see the topic vocabulary below). An offer can be:

* a **degree programme** or a **specialisation** within a programme,
* a **course or module** of a programme (with its own credits), a **PhD course**,
* a **summer or winter school**, a **MOOC**, a **professional training** or a **micro-credential**.

Each offer is one row of the dataset. Modules of a programme that is also in the dataset are linked to it
(*Parent programme*), so they can be counted with or without the programme.

* **Overview** – key figures, filters, a map of where the offers are taught, charts of what is offered (by topic,
  level, country…) and the full table, which can be searched and exported as CSV.
* **Compare** – up to six offers side by side: all their characteristics, the topics (or other values) they cover,
  their size, duration and cost, and their location.
"""

# Short explanation of each variable group (keys = 'group' column of the data_dictionary sheet)
GROUP_INTROS = {
    "Identity": "What the offer is and who provides it: identifiers, title, type of offer, institution, links and "
                "joint offers.",
    "Location": "Where the offer is taught. Coordinates place it on the map; check the location precision before "
                "reading positions as exact addresses. Online-only offers are placed at the providing department.",
    "Level and format": "Study level, size (ECTS credits or workload), duration, pace, delivery mode, language and "
                        "when the offer runs.",
    "Access": "Who can take the offer and on which terms: fee, openness to external participants, target audience, "
              "prerequisites and the credential obtained.",
    "Content": "What is taught and how: smart building topics (harmonised vocabulary), relevance for smart "
               "buildings, disciplines, standards and frameworks, software, teaching methods, hands-on work and "
               "industry involvement.",
    "Metadata": "Status of the offer and how and when the entry was checked.",
    "References": "Where the information comes from.",
}

CAVEATS = """
* The dataset is **not exhaustive**: it lists the offers documented so far, starting with the Nordic and Baltic
  countries. A missing offer does not mean that nothing exists.
* Offers change from year to year (content, fees, language, status). Each entry has a *Last checked* date;
  always confirm the details on the provider's web page before applying.
* *Topics* and *Smart building relevance* are assessed from the public course descriptions with the harmonised
  vocabulary: a topic is listed when it is a learning objective or a dedicated part of the teaching.
* Fees are given in euros for EU/EEA participants unless the notes say otherwise; converted amounts are indicative.
* Map positions are the campus or venue; online-only offers are placed at the providing department.
  Positions marked *City centre* are approximate.
* Empty cells mean *not known*, not *none* (a free offer has a tuition fee of 0).
"""


def _table(header, rows, className: str = "info-table") -> html.Table:
    return html.Table([html.Tr([html.Th(h) for h in header])] + [html.Tr([html.Td(c) for c in r]) for r in rows],
                      className=className)


def _variables_section() -> html.Div:
    """All dataset variables, grouped as in the data dictionary, with unit, description and coverage."""
    data = get_data()
    c, d = data.courses, data.dictionary
    n = len(c)
    groups = list(dict.fromkeys(g for g in d["group"] if g))
    blocks: list[Component] = [html.P(
        f"The dataset currently contains {n} offer{'s' if n != 1 else ''} described by {len(d)} variables, "
        f"organised in {len(groups)} groups. Hover a variable in any dropdown or table header of the app to see the "
        "same description. The column name is the name used in the Excel file. Variables marked 'several values' "
        "can hold more than one value per offer, separated by semicolons.")]
    for g in groups:
        rows = d[d["group"] == g]
        table = html.Table(
            [html.Tr([html.Th("Variable"), html.Th("Unit"), html.Th("Description"), html.Th("Available"),
                      html.Th("Column name")])]
            + [html.Tr([
                html.Td(label(col, with_unit=False) + (" (several values)" if t == "multi" else "")),
                html.Td(unit(col) or "–"),
                html.Td(desc),
                html.Td(f"{int(c[col].notna().sum())} / {n}" if col in c.columns else "–"),
                html.Td(html.Code(col)),
            ]) for col, desc, t in zip(rows["column"], rows["description"], rows["dtype"])],
            className="info-table vars-table")
        children: list[Component] = [html.Summary(f"{g} ({len(rows)} variable{'s' if len(rows) != 1 else ''})")]
        if GROUP_INTROS.get(g):
            children.append(html.P(GROUP_INTROS[g], className="muted"))
        children.append(table)
        blocks.append(html.Details(open=False, className="var-group", children=children))
    return html.Div(blocks)


def _vocabulary_section() -> html.Div:
    """Harmonised values of the categorical and multi-valued variables, with description and number of offers."""
    data = get_data()
    v, c = data.vocabulary, data.courses
    cols = [x for x in VOCAB_FIRST if x in set(v["column"])]
    cols += [x for x in dict.fromkeys(v["column"]) if x not in cols]
    blocks: list[Component] = [html.P(
        "Categorical variables use harmonised values so that offers from different countries can be filtered and "
        "compared. The number of offers using each value is given in the last column.")]
    for col in cols:
        voc = vocabulary(col)
        counts = explode(c, col).value_counts() if col in c.columns else pd.Series(dtype=int)
        rows = [[val, desc or "–", f"{int(counts.get(val, 0))}"] for val, desc in zip(voc["value"], voc["description"])]
        title = label(col, with_unit=False)
        blocks.append(html.Details(open=col == "topics", className="var-group", children=[
            html.Summary(f"{title} ({len(rows)} values)"),
            _table(["Value", "Description", "Offers"], rows, "info-table vars-table"),
        ]))
    return html.Div(blocks)


def _ext_img(path: str, name: str, url: str) -> html.A:
    return html.A(html.Img(src=dash.get_asset_url(path), alt=name), href=url, target="_blank",
                  rel="noopener noreferrer", title=f"{name} – {url}")


def _about_app_section() -> list[Component]:
    """First About card: what the app is, its goal, and the NSBI / IBPSA Nordic / SINTEF context."""
    c = get_data().courses
    n = len(c)
    n_countries = c["country"].nunique() if "country" in c.columns else 0
    n_inst = c["institution"].nunique() if "institution" in c.columns else 0
    content = (f"The dataset currently contains {n} offer{'s' if n != 1 else ''} from {n_inst} "
               f"institution{'s' if n_inst != 1 else ''} in {n_countries} countr{'y' if n_countries == 1 else 'ies'} "
               "and is meant to grow as new offers are documented." if n else
               "The dataset is being compiled: offers will be added as they are documented.")
    return [
        html.P([
            html.B(APP_NAME), " is an open, interactive map and database of educational programmes and courses "
            "related to smart building technologies. For each documented offer – from a full master programme to a "
            "single module or a short PhD course – it records where and how it is taught, for whom, and which smart "
            "building topics it covers. Users can locate the offers on a map, filter them, see what is offered by "
            "topic, level or country, and compare offers side by side.",
        ]),
        html.P([
            html.B("Goal: "), "to give students, PhD candidates, professionals, teachers and education planners a "
            "shared overview of where smart building competences can be acquired, starting with the Nordic and "
            "Baltic countries. The app helps learners find relevant offers, helps institutions find partners and "
            "identify gaps in the offer, and supports the discussion on the skills needed for smart buildings. "
            + content,
        ]),
        html.P([
            "The web app is developed within the ", ext_link("Nordic Smart Building Initiative (NSBI)", NSBI_URL),
            ", under the umbrella of ", ext_link("IBPSA Nordic", IBPSA_NORDIC_URL),
            " (the International Building Performance Simulation Association in the Nordic countries), and is "
            "supported by ", ext_link("SINTEF Community", SINTEF_COMMUNITY_URL), " (Norway). NSBI is a collaborative "
            "forum gathering researchers, academics, engineers, consultants and other stakeholders of the smart "
            "building industry in the Nordic and Baltic countries. It is the companion of the ",
            ext_link("NSBI Smart Building Mapping", MAPPING_APP_URL), " web app, which maps real smart buildings.",
        ]),
        html.Div(_ext_img("logos/nsbi_logo.png", "Nordic Smart Building Initiative (NSBI)", NSBI_URL),
                 className="about-logo"),
    ]


def layout(**_):
    src = get_data().sources
    src_rows = []
    for _, r in src.iterrows():
        src_rows.append([r.get("source_id", ""), ext_link(r.get("reference", ""), r.get("url")), r.get("used_for", "")])
    sources = (_table(["ID", "Reference", "Used for"], src_rows) if src_rows
               else html.P("No sources registered yet.", className="muted"))
    return html.Div([
        html.Div(className="page-head", children=[
            html.H1("About"), html.P("The web app, the dataset, the vocabulary, data sources and caveats.")]),
        card(_about_app_section(), title="About this web app"),
        card(dcc.Markdown(WHAT_IS_SHOWN), title="What is shown"),
        card(_variables_section(), title="Dataset variables"),
        card(_vocabulary_section(), title="Harmonised vocabulary"),
        card(dcc.Markdown(CAVEATS), title="Data notes and caveats"),
        card(sources, title="Sources"),
        card(dcc.Markdown(
            "The dataset is the Excel file `data/smart_building_education_dataset.xlsx`. Add offers as new rows in the "
            "`courses` sheet (one row per offer, unique `course_id`) and new parameters as new columns, registered in "
            "the `data_dictionary` sheet (label, unit, group, type and description). Harmonised values are listed in "
            "the `vocabulary` sheet. Every parameter then appears automatically in the dropdowns that fit its type. "
            "Refresh the browser to see the changes."),
            title="Updating the data"),
        card([
            html.P(["To suggest an offer or a correction, contact ", ext_link(CONTACT_NAME, CONTACT_URL), " (",
                    html.A(CONTACT_EMAIL, href=f"mailto:{CONTACT_EMAIL}"), ")."]),
            html.P(["The data and the code of this web app can be found on GitHub: ",
                    ext_link(REPOSITORY_URL, REPOSITORY_URL), "."]),
        ], title="Data, code and contact"),
    ])
