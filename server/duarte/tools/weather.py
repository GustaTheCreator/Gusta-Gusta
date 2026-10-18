"""Meteorologia via Open-Meteo (sem chave)."""
import httpx

from ..config import settings

WMO = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    80: "light showers", 81: "showers", 82: "heavy showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}


def get_weather(city: str | None = None) -> str:
    city = (city or settings.default_city).strip()
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en"},
        timeout=8,
    ).json()
    if not geo.get("results"):
        return f"Could not find a place called '{city}'."
    place = geo["results"][0]
    data = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": 2,
        },
        timeout=8,
    ).json()
    cur, day = data["current"], data["daily"]
    lines = [
        f"{place['name']} ({place.get('country', '')}) now: {cur['temperature_2m']}°C "
        f"(feels like {cur['apparent_temperature']}°C), {WMO.get(cur['weather_code'], 'changeable')}, "
        f"wind {cur['wind_speed_10m']} km/h."
    ]
    for i, label in enumerate(["Today", "Tomorrow"]):
        lines.append(
            f"{label}: low {day['temperature_2m_min'][i]}°C, high {day['temperature_2m_max'][i]}°C, "
            f"{WMO.get(day['weather_code'][i], 'changeable')}, "
            f"chance of rain {day['precipitation_probability_max'][i]}%."
        )
    return "\n".join(lines)
