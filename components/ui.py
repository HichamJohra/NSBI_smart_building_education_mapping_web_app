"""Small reusable layout blocks and shared component settings."""
from typing import Any

from dash import dcc, html

APP_NAME = "NSBI Smart Building Education Mapping"
APP_SHORT = "NSBI Smart Building Education"  # used in browser-tab titles
MAX_COMPARE = 6  # maximum number of offers on the Compare page

# Plotly options shared by all graphs (hide the Plotly logo in the mode bar). Typed as Any because dcc.Graph's
# `config` prop is a TypedDict in Dash 3+, which makes IDEs flag a plain dict literal.
# noinspection SpellCheckingInspection
GRAPH_CONFIG: Any = {"displaylogo": False}  # 'displaylogo' is Plotly's option name
GRAPH_CONFIG_RESPONSIVE: Any = {**GRAPH_CONFIG, "responsive": True}  # graph resizes with its container

# Remember a control's value in the browser tab (sessionStorage): kept when moving between pages or reloading,
# private to this tab and this user, cleared when the tab is closed. Use as dcc.Dropdown(..., **PERSIST).
PERSIST: Any = {"persistence": True, "persistence_type": "session"}


def card(children, title: str | None = None, subtitle: str | None = None, className: str = "") -> html.Div:
    head = []
    if title:
        head.append(html.H3(title, className="card-title"))
    if subtitle:
        head.append(html.P(subtitle, className="card-subtitle"))
    return html.Div(head + (children if isinstance(children, list) else [children]), className=f"card {className}")


def control(label: str, component, description: str = "") -> html.Div:
    """Labelled control; `description` is shown when hovering the label."""
    return html.Div([html.Label(label, className="control-label", title=description or None), component],
                    className="control")


def kpi(label: str, value_id: str, sub_id: str | None = None, description: str = "") -> html.Div:
    """KPI card whose value is filled by a callback; `description` is shown on hover."""
    children = [html.Div(label, className="kpi-label"), html.Div("–", id=value_id, className="kpi-value")]
    if sub_id:
        children.append(html.Div("", id=sub_id, className="kpi-sub"))
    return html.Div(children, className="kpi", title=description or None)


def graph(gid: str | dict, height: int | None = None, **kwargs) -> dcc.Loading:
    style = {"height": f"{height}px"} if height else {}
    return dcc.Loading(dcc.Graph(id=gid, config=GRAPH_CONFIG, style=style, **kwargs), type="default")


def ext_link(text, url: str | None, className: str = "") -> html.A | str:
    """Link opening in a new tab (plain text when there is no URL)."""
    if not isinstance(url, str) or not url.strip():
        return text
    return html.A(text, href=url.strip(), target="_blank", rel="noopener noreferrer", className=className or None)
