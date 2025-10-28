import hashlib
import random
from datetime import datetime

from langchain.tools import tool  # , ToolRuntime


@tool
def get_weather_for_location(city: str) -> str:
    """
    Return an engaging, deterministic mock weather report for a given city.
    (This tool does not call an external weather API — it generates a friendly
    and replayable forecast based on the city name.)
    """
    if not city or not city.strip():
        return "Please provide a city name so I can check the skies for you."

    seed = int(hashlib.sha256(city.strip().lower().encode()).hexdigest(), 16)
    rng = random.Random(seed)

    conditions = [
        "sunny",
        "partly cloudy",
        "cloudy",
        "light rain",
        "heavy rain",
        "thunderstorms",
        "snow",
        "foggy",
        "windy",
        "drizzle",
        "clear night",
    ]
    emojis = {
        "sunny": "☀️",
        "partly cloudy": "⛅",
        "cloudy": "☁️",
        "light rain": "🌦️",
        "heavy rain": "🌧️",
        "thunderstorms": "⛈️",
        "snow": "❄️",
        "foggy": "🌫️",
        "windy": "🌬️",
        "drizzle": "🌦️",
        "clear night": "🌙",
    }

    condition = rng.choice(conditions)
    emoji = emojis.get(condition, "")
    temp_c = rng.randint(-8, 35) + (len(city) % 6)  # deterministic, varies by city
    feels_like = temp_c + rng.randint(-3, 3)
    precip_chance = (
        rng.randint(0, 95)
        if any(term in condition for term in ("rain", "snow", "drizzle", "thunder"))
        else rng.randint(0, 30)
    )
    wind_kph = rng.randint(5, 45) if "windy" in condition or "thunder" in condition else rng.randint(0, 25)
    visibility = rng.choice(["good", "moderate", "reduced"]) if "fog" in condition or "snow" in condition else "good"

    # Simple recommendation based on condition and temperature
    if "rain" in condition or "drizzle" in condition or "thunder" in condition:
        tip = "Carry an umbrella and consider waterproof shoes."
    elif "snow" in condition:
        tip = "Dress warmly and watch for slippery spots — boots recommended."
    elif temp_c >= 28:
        tip = "Stay hydrated and use sunscreen if you'll be outside."
    elif temp_c <= 5:
        tip = "Layer up — a warm coat and gloves will help."
    elif "cloudy" in condition or "partly cloudy" in condition:
        tip = "A light jacket should do; the day looks mild."
    else:
        tip = "Looks pleasant — enjoy your day!"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    confidence = rng.randint(65, 95)

    report = (
        f"Weather for {city.strip()} — {emoji} {condition.title()}\n"
        f"Observed at: {timestamp}\n"
        f"Temperature: {temp_c}°C (feels like {feels_like}°C)\n"
        f"Precipitation chance: {precip_chance}%  •  Wind: {wind_kph} km/h  •  Visibility: {visibility}\n"
        f"Confidence: {confidence}%\n\n"
        f"Quick tip: {tip}"
    )

    return report
