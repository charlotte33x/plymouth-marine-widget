import streamlit as st
import requests
import arrow
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from astral import moon
from datetime import date, datetime, UTC
from math import cos, pi

# -----------------------
# CONFIG
# -----------------------

API_EY = st.secrets["STORMGLASS_API_KEY"]

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

if phase < 3 or phase > 27:
    tidal_influence = "🌊 Spring Tide Period"
elif 12 <= phase <= 17:
    tidal_influence = "🌊 Approaching Spring Tide"
elif 6 <= phase <= 9:
    tidal_influence = "🌊 Neap Tide Period"
elif 20 <= phase <= 23:
    tidal_influence = "🌊 Approaching Neap Tide"
else:
    tidal_influence = "🌊 Transition Between Spring and Neap"

# -----------------------
# STORMGLASS
# -----------------------

@st.cache_data(ttl=86400)
def get_stormglass_data():

    start = arrow.now().floor("day")
    end = arrow.now().shift(days=1).floor("day")

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
sea_level_data = stormglass["sea_level"]
sea_temp = water_data["hours"][0]["waterTemperature"]["sg"]

# -----------------------
# CURRENT TIDE
# -----------------------

now = datetime.now(UTC)

closest_point = min(
    sea_level_data["data"],
    key=lambda x: abs(
        datetime.fromisoformat(x["time"])
        - now
    )
)

current_height = closest_point["sg"]

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

    event_time = datetime.fromisoformat(
        event["time"]
    )

    if event_time > now:
        future_extremes.append(event)

if future_extremes:

    next_tide = future_extremes[0]

    next_tide_time = datetime.fromisoformat(
        next_tide["time"]
    ).strftime("%H:%M")

    next_tide_height = next_tide["height"]

else:

    next_tide_time = "--:--"
    next_tide_height = 0

# -----------------------
# STREAMLIT
# -----------------------

st.set_page_config(
    page_title="Plymouth Marine Conditions",
    page_icon="🌊",
    layout="wide"
)

st.title("🌊 Plymouth Marine Conditions")

weather_col, moon_col = st.columns(2)

with weather_col:

    st.info("🌤️ Weather")

    st.metric(
        "Temperature",
        f"{temperature}°C"
    )

    st.write(weather)

with moon_col:

    st.info("🌙 Moon")

    st.write(phase_name)
    st.write(f"Illumination: {illumination_percent}%")
    st.write(tidal_influence)

st.divider()

tide_col, sea_col = st.columns(2)

with tide_col:

    st.info("🌊 Tides")

    st.metric(
        "Current Height",
        f"{current_height:.2f} m"
    )

    st.write(status)

    st.write(f"🕖 {next_tide_time}")

    st.write(
        f"Height: {next_tide_height:.2f} m"
    )

with sea_col:

    st.info("🌡️ Sea Temperature")

    st.metric(
        "Sea Surface Temperature",
        f"{sea_temp:.1f}°C"
    )

# -----------------------
# LIVE TIDAL CURVE
# -----------------------

st.divider()

st.subheader("📈 Tidal Curve")

df = pd.DataFrame(sea_level_data["data"])

df["time"] = pd.to_datetime(df["time"])
df["height"] = df["sg"]

fig = px.line(
    df,
    x="time",
    y="height",
    title="Plymouth Tide Today"
)

fig.update_traces(
    line=dict(
        color="#e07ab2",
        width=5
    )
)

fig.add_trace(
    go.Scatter(
        x=[pd.to_datetime(closest_point["time"])],
        y=[current_height],
        mode="markers+text",
        text=["Now"],
        textposition="top center",
        marker=dict(
            size=18,
            color="#ff1493",
            symbol="diamond"
        ),
        showlegend=False
    )
)

fig.update_layout(
    height=500,
    plot_bgcolor="white",
    paper_bgcolor="white",
    xaxis_title="Time",
    yaxis_title="Tide Height (m)",
    title_x=0.5
)

st.plotly_chart(
    fig,
    use_container_width=True
)
