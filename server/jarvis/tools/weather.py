"""Meteorologia via Open-Meteo (sem chave)."""
import httpx

from ..config import settings

WMO = {
    0: "céu limpo", 1: "pouco nublado", 2: "parcialmente nublado", 3: "nublado",
    45: "nevoeiro", 48: "nevoeiro com geada", 51: "chuvisco fraco", 53: "chuvisco",
    55: "chuvisco forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
    80: "aguaceiros fracos", 81: "aguaceiros", 82: "aguaceiros fortes",
    95: "trovoada", 96: "trovoada com granizo", 99: "trovoada forte com granizo",
}


def get_weather(city: str | None = None) -> str:
    city = (city or settings.default_city).strip()
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "pt"},
        timeout=8,
    ).json()
    if not geo.get("results"):
        return f"Não encontrei a localidade '{city}'."
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
        f"{place['name']} ({place.get('country', '')}) agora: {cur['temperature_2m']}°C "
        f"(sensação {cur['apparent_temperature']}°C), {WMO.get(cur['weather_code'], 'tempo variável')}, "
        f"vento {cur['wind_speed_10m']} km/h."
    ]
    for i, label in enumerate(["Hoje", "Amanhã"]):
        lines.append(
            f"{label}: mín {day['temperature_2m_min'][i]}°C, máx {day['temperature_2m_max'][i]}°C, "
            f"{WMO.get(day['weather_code'][i], 'tempo variável')}, "
            f"probabilidade de chuva {day['precipitation_probability_max'][i]}%."
        )
    return "\n".join(lines)
