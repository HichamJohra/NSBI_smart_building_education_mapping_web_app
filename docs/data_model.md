# Data model

All data is in `data/smart_building_education_dataset.xlsx`. The app reads it with
`components/data.py::get_data()`.

## Sheets

| Sheet | One row per | Purpose |
|---|---|---|
| `README` | – | Short instructions inside the workbook |
| `courses` | educational offer | Programme, course or module, PhD course, summer school, MOOC, training… |
| `data_dictionary` | column of `courses` | Label, unit, group, type (dtype), description and hover flag |
| `vocabulary` | value | Harmonised values of categorical and multi-valued columns (`column, value, description`) |
| `sources` | reference | Bibliographic sources (`source_id, reference, url, used_for`) |

## Column groups in `courses`

| Group | Columns |
|---|---|
| Identity | `course_id` (unique key), `short_name`, `title`, `course_code`, `offer_type`, `parent_programme_id`, `institution`, `provider_type`, `department`, `url`, `joint_offer`, `partner_institutions`*, `network`* |
| Location | `campus_address`, `city`, `country`, `region`, `latitude`, `longitude`, `location_precision` |
| Level and format | `level`, `eqf_level`, `ects`, `workload_hours`, `duration_weeks`, `pace`, `delivery_mode`, `language`*, `teaching_period`*, `frequency` |
| Access | `fee_category`, `tuition_fee_eur`, `open_to_external`, `target_audience`*, `prerequisites`, `credential` |
| Content | `topics`*, `main_topic`, `n_topics` (computed), `smart_building_relevance`, `disciplines`*, `standards_and_frameworks`*, `software_tools`*, `teaching_methods`*, `hands_on`, `industry_involvement`, `learning_outcomes`, `description` |
| Metadata | `status`, `last_checked`, `data_source_type`, `notes` |
| References | `main_reference`, `main_reference_url`, `syllabus_url` |

\* multi-valued (dtype `multi`): several values separated by semicolons, e.g. `English; Norwegian`.

Units: ECTS credits, hours, weeks, EUR, degrees (coordinates). An empty cell means *not known*; a free offer has
`tuition_fee_eur` = 0.

Computed by the app (not in the Excel sheet): `n_topics` (number of topics); `region` is filled from `country`
when empty (Nordic, Baltic, Rest of Europe, Outside Europe).

## `data_dictionary`

Columns: `column, label, unit, group, dtype, description, hover`.

| dtype | Meaning | Where it appears |
|---|---|---|
| `numeric` | number | Numeric filters, bubble size and colour, compare bars |
| `categorical` | one value per offer | Category filters, bubble colour, breakdown charts, coverage matrix |
| `multi` | several values separated by `;` | Category filters ("contains any"), breakdown charts, coverage matrix |
| `text`, `url`, `date` | free text, link, date (YYYY-MM-DD) | Tables and compare page only |

Parameters without any value yet are listed with "(no data yet)" and cannot be selected. `hover` = `Y` marks the
parameters always shown in the map pop-ups. `group` orders the variables (About page, compare table).
The `description` is shown as hover text everywhere: write it so that a user unfamiliar with the field understands
what the parameter means.

## `vocabulary`

Harmonised values of categorical and multi-valued columns, with a description. The app uses the sheet order for
filters, charts and colours, shows the descriptions on hover and lists the vocabulary on the About page.
`main_topic` uses the `topics` vocabulary. In Excel, the single-valued categorical columns of `courses` have a
drop-down list from this sheet (a warning is shown for other values). Lists that are open by nature (language,
network, partner institutions, standards and frameworks, software and tools) accept new values; keep the spelling
consistent.

The 14 topics: building automation and control (BACS/BMS); HVAC control and optimisation; IoT, sensors and networks;
data analytics and AI for buildings; digital twins and BIM; building energy modelling and simulation; energy
flexibility and grid interaction; renewables, storage and e-mobility; fault detection, commissioning and
monitoring; indoor environment and occupants; Smart Readiness Indicator, policy and regulation; interoperability,
semantics and cybersecurity; smart districts and energy communities; operation, facility management and business
models.

## Adding data

- **New offer:** add a row to `courses` with a unique `course_id` (country code + number, e.g. `NO-001`) and
  `latitude`/`longitude`. Modules of a programme in the dataset get the programme's id in `parent_programme_id`.
- **New parameter:** add a column to `courses` and a row to `data_dictionary`; for a categorical or multi-valued
  parameter, add its values to `vocabulary`.
- Write descriptions in your own words; no personal data (no names or e-mails of teachers).
- Save, close Excel (the `~$` lock file is git-ignored), refresh the browser.

## Current content

10 offers in Denmark, Norway and Estonia (checked 2026-11-09/10, from official web pages and course catalogues;
DK-004 was removed and its ID is not reused):

| ID | Offer | Institution |
|---|---|---|
| DK-001 | Energy management with embedded systems (46035), bachelor course | DTU, Lyngby |
| DK-002 | MSc Sustainable Energy Systems – specialisation Energy-efficient Building Systems | DTU, Lyngby |
| DK-003 | High performance buildings (41463), master course (part of DK-002) | DTU, Lyngby |
| DK-005 | Control and Analysis of Building Energy Systems (B-BED-K3-14), MSc Building Energy Design course | AAU, Aalborg |
| DK-006 | Advanced Control for Building Applications (B-EVU-ACB-26), continuing education | AAU, Copenhagen |
| DK-007 | IoT and Cloud based energy solutions (T610032101), status unknown (last description 2022) | SDU, Odense |
| NO-001 | Systematic fault detection and optimisation of ventilation systems, half-day course (last held September 2025) | SINTEF Community, Oslo |
| EE-001 | Building automation and HVAC (Hooneautomaatika ja tehnosüsteemid), 18 ECTS micro-credential, in Estonian | TalTech, Tallinn |
| EE-002 | Buildings' electricity and automation technology (Hoonete elektri- ja automaatikatehnika), 24 ECTS micro-credential, in Estonian | TalTech, Tallinn |
| EE-003 | MSc Hardware Development and Programming (IACM23), with a building automation study path, in Estonian | TalTech, Tallinn |
