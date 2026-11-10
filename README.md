# NSBI_smart_building_education_mapping_web_app
Web app to map and explore education programs and courses related to smart building technologies [NSBI project]

Multi-page [Dash](https://dash.plotly.com/) web app to map, filter and compare educational offers (degree
programmes, courses and modules, PhD courses, summer schools, MOOCs, professional trainings) on smart building
technologies, from an embedded Excel dataset. Companion of the
[NSBI Smart Building Mapping](https://github.com/HichamJohra/NSBI_smart_building_mapping_web_app) web app
(same structure and style).

**Live app:** <https://nsbi-smart-building-education-mapping.cloud.run> (Google Cloud Run, redeployed automatically
from the `main` branch; see `docs/deployment.md`).

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python app.py                 # -> http://127.0.0.1:8050
```

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | App entry point, navigation bar, page container, per-tab memory (filters, comparison) |
| `pages/home.py` | Overview: KPIs, add/remove filters, bubble map (per offer or per place), breakdown charts, full table with selection for comparison |
| `pages/compare.py` | Compare 2–6 offers: key facts side by side, content coverage matrix, numeric bars, location map |
| `pages/about.py` | About the app (NSBI context), dataset variables, harmonised vocabulary, caveats, sources, contact |
| `components/data.py` | Excel loading (auto-reload on file change), data-dictionary and vocabulary helpers |
| `components/figures.py` | Plotly figure builders |
| `components/ui.py` | Layout helpers and shared settings |
| `assets/style.css` | Styling (auto-loaded by Dash) |
| `assets/dashAgGridComponentFunctions.js` | Table cell renderer for web links |
| `assets/favicon.ico`, `assets/logos/` | SINTEF browser-tab icon; SINTEF and IBPSA Nordic logos (top right of every page); NSBI logo (About page) |
| `data/smart_building_education_dataset.xlsx` | The dataset |
| `Dockerfile`, `.dockerignore` | Container image for Docker / Google Cloud Run (see `docs/deployment.md`) |
| `docs/` | Documentation: architecture, data model, development, deployment |
| `docs/project_graph_explorer/` | Interactive HTML map of the code + script to regenerate it |

## Documentation

See [docs/README.md](docs/README.md). For an interactive overview of files, imports, function calls and
callback inputs/outputs, open `docs/project_graph_explorer/NSBI_education_project_explorer.html` in a browser.
Regenerate it after code changes:

```bash
.venv\Scripts\python.exe docs/project_graph_explorer/build_project_explorer.py
```

## Dataset

`data/smart_building_education_dataset.xlsx` contains:

- `courses` – one row per offer (identity, location, level and format, access, content, metadata, references)
- `data_dictionary` – label, unit, group, dtype and description of each column. Every column appears in the
  dropdowns that fit its dtype (`numeric`, `categorical`, `multi` = several values separated by `;`);
  `hover` = `Y` shows it in all map pop-ups
- `vocabulary` – harmonised values of the categorical and multi-valued columns (e.g. the 14 smart building topics)
- `sources` – references

To add an offer, add a row to `courses`. To add a parameter, add a column to `courses` and a row to
`data_dictionary`. Refresh the browser: the file is re-read automatically when it changes.

Current content: 10 offers in Denmark (DTU, Aalborg University, University of Southern Denmark), Norway
(SINTEF) and Estonia (TalTech); see
`docs/data_model.md`.
