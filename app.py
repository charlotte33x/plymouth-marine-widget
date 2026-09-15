import streamlit as st
import requests
import arrow
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from astral import moon
from datetime import date, datetime, UTC
from math import cos, pi
st.markdown("""
<style>

.stApp {
    background-color: #fcb8c9;
}

div[data-testid="stMetric"] {
    background-color: #ffeef7;
    padding: 8px;
    border-radius: 12px;
}

div[data-testid="stAlert"] {
    background-color: #FFFAE2;
    border: none;
}

h1 {
    color: #d63384;
}

h2, h3 {
    color: #e754a6;
}

</style>
""", unsafe_allow_html=True)
# -----------------------
# CONFIG
# -----------------------

API_KEY = st.secrets["STORMGLASS_API_KEY"]

LAT = 50.3755
LNG = -4.1427

# -----------------------
# WEATHER
# -----------------------

weather_url = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=50.3755"
    "&longitude=-4.1427"
    "&current=temperature_2m,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min"
    "&forecast_days=3"
)


weather_response = requests.get(weather_url)
weather_data = weather_response.json()

temperature = weather_data["current"]["temperature_2m"]
weather_code = weather_data["current"]["weather_code"]

weather_descriptions = {
    0: "☀️ Clear Sky",
    1: "🌤️ Mainly Clear",
    2: "⛅ Partly Cloudy",
    3: "☁️ Overcast",
    45: "🌫️ Fog",
    61: "🌧️ Rain"
}

weather = weather_descriptions.get(weather_code, "Unknown")
forecast_dates = weather_data["daily"]["time"]
forecast_max = weather_data["daily"]["temperature_2m_max"]
forecast_min = weather_data["daily"]["temperature_2m_min"]


# -----------------------
# MOON
# -----------------------

phase = moon.phase(date.today())

if phase < 1:
    phase_name = "🌑 New Moon"
elif phase < 8:
    phase_name = "🌒 Waxing Crescent"
elif phase < 15:
    phase_name = "🌔 Waxing Gibbous"
elif phase < 16:
    phase_name = "🌕 Full Moon"
elif phase < 22:
    phase_name = "🌖 Waning Gibbous"
else:
    phase_name = "🌘 Waning Crescent"

illumination = (1 - cos(2 * pi * phase / 29.53)) / 2
illumination_percent = round(illumination * 100)
LUNAR_CYCLE = 29.53
FULL_MOON_AGE = 14.77

if phase <= FULL_MOON_AGE:
    days_until_full = FULL_MOON_AGE - phase
else:
    days_until_full = (
        LUNAR_CYCLE - phase + FULL_MOON_AGE
    )

days_until_full = round(days_until_full, 1)

if phase < 4 or phase > 25:
    tidal_influence = "Spring Tide"

elif 11 < phase < 18:
    tidal_influence = "Spring Tide"

elif 5 < phase < 10:
    tidal_influence = "Neap Tide"

elif 19 < phase < 24:
    tidal_influence = "Neap Tide"

else:
    tidal_influence = "Transitional"

# -----------------------
# STORMGLASS
# -----------------------

@st.cache_data(ttl=86400)
def get_stormglass_data():

    start = arrow.now().floor("day")
    end = arrow.now().shift(days=2).floor("day")

    headers = {
        "Authorization": API_KEY
    }

    # Sea temperature

    water_response = requests.get(
        "https://api.stormglass.io/v2/weather/point",
        params={
            "lat": LAT,
            "lng": LNG,
            "params": "waterTemperature"
        },
        headers=headers
    )

    water_data = water_response.json()

    # Tide extremes

    extremes_response = requests.get(
        "https://api.stormglass.io/v2/tide/extremes/point",
        params={
            "lat": LAT,
            "lng": LNG,
            "start": start.to("UTC").timestamp(),
            "end": end.to("UTC").timestamp()
        },
        headers=headers
    )

    extremes_data = extremes_response.json()

    # Sea level

    sea_response = requests.get(
        "https://api.stormglass.io/v2/tide/sea-level/point",
        params={
            "lat": LAT,
            "lng": LNG,
            "start": start.to("UTC").timestamp(),
            "end": end.to("UTC").timestamp()
        },
        headers=headers
    )

    sea_level_data = sea_response.json()

    return {
        "water": water_data,
        "extremes": extremes_data,
        "sea_level": sea_level_data
    }


stormglass = get_stormglass_data()

water_data = stormglass["water"]
extremes_data = stormglass["extremes"]
high_tides = [
    tide for tide in extremes_data["data"]
    if tide["type"] == "high"
]

low_tides = [
    tide for tide in extremes_data["data"]
    if tide["type"] == "low"
]
high_times = []

for tide in high_tides:
    high_times.append(
        pd.to_datetime(
            tide["time"]
        ).tz_convert(
            "Europe/London"
        ).strftime("%H:%M")
    )

low_times = []

for tide in low_tides:
    low_times.append(
        pd.to_datetime(
            tide["time"]
        ).tz_convert(
            "Europe/London"
        ).strftime("%H:%M")
    )
sea_level_data = stormglass["sea_level"]
sea_temp = water_data["hours"][0]["waterTemperature"]["sg"]

# -----------------------
# CURRENT TIDE
# -----------------------



now = datetime.now(UTC)
sea_df = pd.DataFrame(sea_level_data["data"])

sea_df["time"] = pd.to_datetime(sea_df["time"])

sea_df = sea_df.sort_values("time")

current_timestamp = pd.Timestamp.now(tz="UTC")

sea_df["seconds"] = (
    sea_df["time"] - sea_df["time"].min()
).dt.total_seconds()

current_seconds = (
    current_timestamp - sea_df["time"].min()
).total_seconds()

current_height = float(
    np.interp(
        current_seconds,
        sea_df["seconds"],
        sea_df["sg"]
    )
)

closest_point = min(
    sea_level_data["data"],
    key=lambda x: abs(
        datetime.fromisoformat(x["time"])
        - now
    )
)


current_index = sea_level_data["data"].index(
    closest_point
)

if current_index > 0:

    previous_height = sea_level_data["data"][current_index - 1]["sg"]

    if current_height > previous_height:
        status = "⬆ Rising Tide"
    else:
        status = "⬇ Falling Tide"

else:
    status = "🌊 Tide"

# -----------------------
# NEXT TIDE
# -----------------------
future_extremes = []

for event in extremes_data["data"]:

    event_time = pd.to_datetime(
        event["time"],
        utc=True
    )

    if event_time.to_pydatetime() > now:
        future_extremes.append(event)

if future_extremes:

    next_tide = future_extremes[0]

    next_tide_time = pd.to_datetime(
        next_tide["time"]
    ).tz_convert("Europe/London").strftime("%H:%M")

    next_tide_height = next_tide["height"]
    next_tide_type = next_tide["type"].title()

else:

    next_tide_time = "No Data"
    next_tide_height = 0

# -----------------------
# STREAMLIT
# -----------------------

st.set_page_config(
    page_title="Plymouth Marine Conditions",
    page_icon="🌊",
    layout="wide"
)
st.markdown(
    "<div style='color:#4A90E2;font-size:18px;font-weight:500;'>🌊 Plymouth Marine</div>",
    unsafe_allow_html=True
)
import zoneinfo

uk_time = datetime.now(
    zoneinfo.ZoneInfo("Europe/London")
)

st.caption(
    f"Updated {uk_time.strftime('%H:%M')}"
)
st.markdown(
    "<div style='color:#125f7b;font-size:18px;font-weight:500;'>🌡️ Temperature</div>",
    unsafe_allow_html=True
)
st.markdown(
    f"""
    <div style="
    background:#CBEEF3;
    color:#125f7b
    padding:8px;
    border-radius:12px;
    ">
    <b>Air:</b> {temperature}°C
    &nbsp;&nbsp;&nbsp;&nbsp;
    <b>Sea:</b> {sea_temp:.1f}°C
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown(
    "<div style='color:#b56b8d;font-size:18px;font-weight:500;'>📅 3 Day Forecast</div>",
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div style="
    background:#DE9D95;
    color:#CBEEF3;
    padding:8px;
    border-radius:12px;
    ">
    <b>{pd.to_datetime(forecast_dates[0]).strftime("%a")}</b> {round(forecast_max[0])}°
    &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>{pd.to_datetime(forecast_dates[1]).strftime("%a")}</b> {round(forecast_max[1])}°
    &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>{pd.to_datetime(forecast_dates[2]).strftime("%a")}</b> {round(forecast_max[2])}°
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown(
    "<div style='color:#4A90E2;font-size:18px;font-weight:500;'>🌊 Tides</div>",
    unsafe_allow_html=True
)
st.markdown(
    f"""
    <div style="
    background:#F49CBB;
    color:#CBEEF3;
    padding:8px;
    border-radius:12px;
    ">
    <b>Current:</b> {current_height:.2f}m
    <br>
    <b>Tide:</b> {status}
    <br>
    <b>Next {next_tide_type}:</b> {next_tide_time} • {next_tide_height:.2f}m
    <br>
    <b>High tides:</b> {high_times[0]} • {high_times[1]}
    <br>
    <b>Lows tides:</b> {low_times[0]} • {low_times[1]}
    <br>
    <b>State:</b> {tidal_influence}
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown(
    "<div style='color:#F49CBB;font-size:18px;font-weight:500;'>🌙 Moon</div>",
    unsafe_allow_html=True
)
st.markdown(
    f"""
    <div style="
    background:#CBEEF3;
    color:#F49CBB;
    padding:8px;
    border-radius:12px;
    ">
    <b>Phase:</b> {phase_name}
    <br>
    <b>Age:</b> {round(phase,1)} days
    <br>
    <b>Illumination:</b> {illumination_percent}%
    <br>
    <b>🌕 Next Full Moon:</b> {days_until_full} days
    </div>
    """,
    unsafe_allow_html=True
)
# -----------------------
# LIVE TIDAL CURVE
# -----------------------
df = pd.DataFrame(sea_level_data["data"])

df["time"] = pd.to_datetime(df["time"])
df["height"] = df["sg"]

fig = px.line(
    df,
    x="time",
    y="height"
)

fig.update_traces(
    line=dict(
        color="#e07ab2",
        width=3
    )
)

fig.add_trace(
    go.Scatter(
        x=[pd.to_datetime(closest_point["time"])],
        y=[current_height],
        mode="markers",
        text=["Now"],
        textposition="top center",
        marker=dict(
            size=8,
            color="#ff1493",
            symbol="diamond"
        ),
        showlegend=False
    )
)

fig.update_layout(
    height=150,
    plot_bgcolor="white",
    paper_bgcolor="white",
   xaxis_title="",
   yaxis_title="",
    title_x=0.5,
    margin=dict(
    l=0,
    r=0,
    t=0,
    b=0
)
)
fig.update_yaxes(
    visible=False,
    showgrid=False,
    zeroline=False
)

fig.update_xaxes(
    title_text="",
    showgrid=False
)
st.plotly_chart(
    fig,
    use_container_width=True
)
