"""Streamlit dashboard for wind turbine data served by the REST API."""

import json
import os
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Turbine Monitor",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #172b4d;
        --muted: #64748b;
        --accent: #2563eb;
        --line: #e5eaf2;
        --surface: #ffffff;
    }
    .stApp {
        background:
            radial-gradient(ellipse at 92% 0%, rgba(37, 99, 235, .07), transparent 34rem),
            #f5f7fb;
        color: var(--ink);
    }
    [data-testid="stHeader"] { background: rgba(245, 247, 251, .82); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #eef3fb 0%, #f7f9fc 100%);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] h2 {
        color: var(--ink);
        font-size: 1.05rem;
        letter-spacing: -.02em;
    }
    .block-container {
        max-width: 1500px;
        padding-top: 2.4rem;
        padding-bottom: 3rem;
    }
    h1 {
        color: var(--ink);
        font-size: 2.35rem !important;
        font-weight: 750 !important;
        letter-spacing: -.045em;
        padding-bottom: .15rem;
    }
    h2, h3 { color: var(--ink); letter-spacing: -.025em; }
    [data-testid="stCaptionContainer"] p {
        color: var(--muted);
        font-size: .92rem;
    }
    div[data-testid="stMetric"] {
        min-height: 124px;
        background: var(--surface);
        padding: 21px 22px;
        border-radius: 16px;
        border: 1px solid var(--line);
        box-shadow: 0 5px 18px rgba(23, 43, 77, .045);
        transition: transform .18s ease, box-shadow .18s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(23, 43, 77, .08);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--muted);
        font-size: .88rem;
        font-weight: 550;
    }
    div[data-testid="stMetricValue"] {
        color: var(--ink);
        font-size: 1.8rem;
        font-weight: 720;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface);
        border-color: var(--line);
        border-radius: 16px;
    }
    .stButton > button {
        min-height: 2.7rem;
        background: var(--accent);
        color: white;
        border: 1px solid var(--accent);
        border-radius: 10px;
        font-weight: 650;
        transition: background .15s ease, transform .15s ease;
    }
    .stButton > button:hover {
        background: #1d4ed8;
        border-color: #1d4ed8;
        color: white;
        transform: translateY(-1px);
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 14px;
        overflow: hidden;
    }
    [data-testid="stAlert"] { border-radius: 12px; }
    hr { border-color: var(--line); }
    @media (max-width: 700px) {
        .block-container { padding: 1.3rem 1rem 2rem; }
        h1 { font-size: 1.8rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=5)
def load_measurements(api_url: str, limit: int) -> list[dict[str, Any]]:
    """Fetch the newest measurements from the REST API."""
    _require_http_url(api_url)
    url = f"{api_url.rstrip('/')}?{urlencode({'limit': limit})}"
    try:
        # _require_http_url restricts urllib to HTTP(S).
        with urlopen(url, timeout=30) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API'en svarede med HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Kunne ikke forbinde til API'en på {api_url}: {exc.reason}"
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("API'en returnerede ugyldig JSON.") from exc

    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise RuntimeError("API'en returnerede data i et uventet format.")
    return data


def _require_http_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise RuntimeError(
            "API-adressen skal være en gyldig HTTP- eller HTTPS-URL."
        ) from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("API-adressen skal være en gyldig HTTP- eller HTTPS-URL.")


def _control_api_url(api_url: str, endpoint: str) -> str:
    _require_http_url(api_url)
    parsed = urlsplit(api_url)
    path = parsed.path.rstrip("/")
    path = path.removesuffix("/measurements")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}{endpoint}", "", ""))


def _request_control_api(
    url: str, method: str = "GET", payload: dict[str, str] | None = None
) -> Any:
    _require_http_url(url)
    request_data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=request_data,
        headers={"Content-Type": "application/json"} if request_data else {},
        method=method,
    )
    try:
        # _require_http_url restricts urllib to HTTP(S).
        with urlopen(request, timeout=10) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API'en svarede med HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Kunne ikke forbinde til API'en på {url}: {exc.reason}"
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("API'en returnerede ugyldige kontrol-data.") from exc
    return data


def load_turbine_controls(api_url: str) -> list[dict[str, str]]:
    """Fetch the current simulated control state for all turbines."""
    data = _request_control_api(_control_api_url(api_url, "/turbines/control"))
    if not isinstance(data, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("Turbine_ID"), str)
        or item.get("status") not in {"RUNNING", "STOPPED"}
        for item in data
    ):
        raise RuntimeError("API'en returnerede kontrol-data i et uventet format.")
    return data


def set_turbine_control(
    api_url: str, turbine_id: str, command: Literal["start", "stop"]
) -> dict[str, str]:
    """Send a simulated start/stop command to the API."""
    url = _control_api_url(api_url, f"/turbines/{quote(turbine_id, safe='')}/control")
    data = _request_control_api(url, "POST", {"command": command})
    if (
        not isinstance(data, dict)
        or data.get("Turbine_ID") != turbine_id
        or data.get("status") not in {"RUNNING", "STOPPED"}
    ):
        raise RuntimeError("API'en returnerede kontrol-data i et uventet format.")
    return data


def main() -> None:
    st.title("🌬️ Turbine Monitor")
    st.caption("Overblik over vindmøllemålinger gemt i MongoDB Atlas")

    with st.sidebar:
        st.header("API-forbindelse")
        api_url = st.text_input(
            "Målingers API-adresse",
            value=os.getenv("API_URL", "http://127.0.0.1:8000/measurements"),
        ).strip()
        row_limit = st.select_slider(
            "Maks. seneste målinger",
            options=[500, 1000, 2500, 5000, 10000],
            value=2500,
        )
        if st.button("Opdater data", use_container_width=True):
            load_measurements.clear()

    if not api_url:
        st.error("Angiv API-adressen i sidepanelet.")
        st.stop()

    st.subheader("Simuleret turbinestyring")
    st.warning(
        "Demo-funktion: styringen ændrer kun simulatorens tilstand. "
        "Den sender ikke kommandoer til fysisk turbineudstyr."
    )
    try:
        controls = load_turbine_controls(api_url)
    except RuntimeError as exc:
        st.error(f"Kunne ikke hente turbinernes tilstand: {exc}")
        st.stop()

    control_columns = st.columns(max(len(controls), 1))
    for column, control in zip(control_columns, controls):
        turbine_id = control["Turbine_ID"]
        is_running = control["status"] == "RUNNING"
        with column:
            st.markdown(f"#### {turbine_id}")
            st.markdown(
                "🟢 **I drift (simulation)**"
                if is_running
                else "🔴 **Stoppet (simulation)**"
            )
            command = "stop" if is_running else "start"
            button_label = "Stop turbine" if is_running else "Start turbine"
            if st.button(
                button_label,
                key=f"{command}_{turbine_id}",
                use_container_width=True,
            ):
                try:
                    set_turbine_control(api_url, turbine_id, command)
                except RuntimeError as exc:
                    st.error(f"Kunne ikke ændre tilstanden for {turbine_id}: {exc}")
                else:
                    st.rerun()

    try:
        documents = load_measurements(api_url, row_limit)
    except RuntimeError as exc:
        st.error(f"Kunne ikke hente data fra API'en: {exc}")
        st.stop()

    if not documents:
        st.warning("API'en har endnu ikke modtaget nogen målinger.")
        st.stop()

    data = pd.DataFrame(documents)
    required = {
        "Timestamp",
        "Turbine_ID",
        "Wind_Speed_m_s",
        "Power_Output_kW",
        "Gearbox_Temp_C",
        "Generator_Temp_C",
        "Vibration_mm_s",
        "Alarm_Flag",
        "Status",
        "Maintenance_Required",
    }
    missing = required.difference(data.columns)
    if missing:
        st.error("API-data mangler felter: " + ", ".join(sorted(missing)))
        st.stop()

    data["Timestamp"] = pd.to_datetime(data["Timestamp"], utc=True, errors="coerce")
    data = data.dropna(subset=["Timestamp"]).sort_values("Timestamp")
    if data.empty:
        st.warning("API-data indeholder ingen gyldige tidsstempler.")
        st.stop()

    with st.sidebar:
        st.header("Filtre")
        turbine_options = sorted(data["Turbine_ID"].dropna().unique().tolist())
        selected_turbines = st.multiselect(
            "Vindmølle", turbine_options, default=turbine_options
        )
        status_options = sorted(data["Status"].dropna().unique().tolist())
        selected_statuses = st.multiselect(
            "Status", status_options, default=status_options
        )
        first_date = data["Timestamp"].min().date()
        last_date = data["Timestamp"].max().date()
        selected_dates = st.date_input(
            "Dato",
            value=(first_date, last_date),
            min_value=first_date,
            max_value=last_date,
        )

    filtered = data[
        data["Turbine_ID"].isin(selected_turbines)
        & data["Status"].isin(selected_statuses)
    ]
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        start_time = pd.Timestamp(start_date, tz="UTC")
        end_time = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
        filtered = filtered[
            (filtered["Timestamp"] >= start_time) & (filtered["Timestamp"] < end_time)
        ]

    st.caption(
        f"Viser {len(filtered):,} af de seneste {len(data):,} indlæste målinger "
        f"· brug “Opdater data” i sidepanelet for at hente nye målinger"
    )
    if filtered.empty:
        st.info("Ingen målinger matcher de valgte filtre.")
        st.stop()

    latest = filtered.iloc[-1]
    alarm_count = int(filtered["Alarm_Flag"].fillna(False).astype(bool).sum())
    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Seneste vindhastighed", f"{latest['Wind_Speed_m_s']:.1f} m/s"
    )
    metric_columns[1].metric("Seneste effekt", f"{latest['Power_Output_kW']:.1f} kW")
    metric_columns[2].metric("Alarmer i perioden", f"{alarm_count:,}")
    metric_columns[3].metric("Aktiv status", str(latest["Status"]))

    st.subheader("Målinger over tid")
    left_chart, right_chart = st.columns(2)
    with left_chart:
        wind_chart = px.line(
            filtered,
            x="Timestamp",
            y="Wind_Speed_m_s",
            color="Turbine_ID",
            title="Vindhastighed",
            labels={
                "Timestamp": "Tidspunkt",
                "Wind_Speed_m_s": "Vind (m/s)",
                "Turbine_ID": "Vindmølle",
            },
        )
        wind_chart.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "sans-serif", "color": "#64748b"},
            legend_title_text="",
            margin={"t": 55, "b": 20, "l": 12, "r": 12},
        )
        st.plotly_chart(wind_chart, use_container_width=True)
    with right_chart:
        power_chart = px.line(
            filtered,
            x="Timestamp",
            y="Power_Output_kW",
            color="Turbine_ID",
            title="Effektproduktion",
            labels={
                "Timestamp": "Tidspunkt",
                "Power_Output_kW": "Effekt (kW)",
                "Turbine_ID": "Vindmølle",
            },
        )
        power_chart.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "sans-serif", "color": "#64748b"},
            legend_title_text="",
            margin={"t": 55, "b": 20, "l": 12, "r": 12},
        )
        st.plotly_chart(power_chart, use_container_width=True)

    temperature_columns = ["Gearbox_Temp_C", "Generator_Temp_C"]
    temperature_chart = px.line(
        filtered,
        x="Timestamp",
        y=temperature_columns,
        color="Turbine_ID",
        title="Temperaturer",
        labels={
            "Timestamp": "Tidspunkt",
            "value": "Temperatur (°C)",
            "variable": "Sensor",
            "Turbine_ID": "Vindmølle",
            "Gearbox_Temp_C": "Gearkasse",
            "Generator_Temp_C": "Generator",
        },
    )
    temperature_chart.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif", "color": "#64748b"},
        legend_title_text="",
        margin={"t": 55, "b": 20, "l": 12, "r": 12},
    )
    st.plotly_chart(temperature_chart, use_container_width=True)

    st.subheader("Seneste målinger")
    table_columns = [
        "Timestamp",
        "Turbine_ID",
        "Wind_Speed_m_s",
        "Power_Output_kW",
        "Gearbox_Temp_C",
        "Generator_Temp_C",
        "Vibration_mm_s",
        "Alarm_Flag",
        "Status",
        "Maintenance_Required",
    ]
    table = filtered.sort_values("Timestamp", ascending=False)[table_columns].head(100)
    st.dataframe(table, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
