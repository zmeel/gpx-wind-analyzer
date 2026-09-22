# GPX Wind Analyzer

Upload a cycling route (`.gpx`), pick a ride date/time, and see which parts of
the route will be headwind, tailwind, or crosswind, on a map.

## Running locally

```bash
pip install -r requirements.txt
cd app
uvicorn main:app --reload
```

Then open http://localhost:8000.

## Running with Docker

```bash
docker compose up --build
```

Then open http://localhost:8085.

## Past vs. future rides

Wind data comes from [Open-Meteo](https://open-meteo.com/):

- Rides up to **16 days in the future** (and roughly the last 92 days) use
  Open-Meteo's forecast endpoint.
- Older rides use Open-Meteo's historical archive endpoint, which does not
  cover future dates at all.

The app picks the right endpoint automatically based on the selected date,
and rejects dates further out than the forecast horizon with a clear error
instead of returning empty or zeroed wind data. See `app/weather.py` for the
exact boundary logic.

No API key is required for Open-Meteo's free tier.
