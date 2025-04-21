import hashlib
import os
import pandas as pd
import pytz
import requests
import sqlite3
import uuid
from datetime import datetime, timedelta
from dateutil import parser
from dotenv import load_dotenv
from icalendar import Calendar, Event
import baikal

load_dotenv()

AIRTRAIL_ENDPOINT = os.environ["AIRTRAIL_ENDPOINT"]
AIRTRAIL_KEY = os.environ["AIRTRAIL_KEY"]

UTC = pytz.UTC
NOW = UTC.localize(datetime.now())

def is_future(flight):
    arrival = parser.parse(flight["arrival"])
    return arrival > NOW

def iata(airport: str) -> str:
    return f"SELECT name, iata_code, iso_country, iso_region, municipality " \
           f"FROM airports WHERE iata_code = '{airport}'"

def get_airport_details(cursor, airport: str):
    name, code, country, region, municipality = cursor.execute(iata(airport)).fetchone()
    region = region.replace("US-", "") if country == "US" else region
    return name, code, country, region, municipality

def format_airport_details(name, code, country, region, municipality):
    loc = region if country == "US" else country
    return f"{code} ({name} — {municipality}, {loc})"

def make_ical_data(cursor, flight):
    m = hashlib.md5()
    airport_from = format_airport_details(*get_airport_details(cursor, flight["from"]["iata"]))
    airport_to = format_airport_details(*get_airport_details(cursor, flight["to"]["iata"]))
    flight_number = flight["flightNumber"]
    summary = f"{flight_number} {airport_from} ➠ {airport_to}"
    depart = parser.parse(flight["departure"])
    arrive = parser.parse(flight["arrival"])
    m.update(summary.encode("utf-8"))
    uid = uuid.UUID(m.hexdigest())
    return {
        "name": summary,
        "begin": depart,
        "end": arrive,
        "categories": ["FLIGHT"],
        "uid": f"{uid}@emilygorcenski.com"
    }

def make_boarding_blocker(flight):
    m = hashlib.md5()
    flight_number = flight["flightNumber"]
    summary = f"Boarding {flight_number}"
    depart = parser.parse(flight["departure"])
    boarding = depart - timedelta(hours=0, minutes=30)
    m.update(summary.encode("utf-8"))
    uid = uuid.UUID(m.hexdigest())
    return {
        "name": summary,
        "begin": boarding,
        "end": depart,
        "uid": f"{uid}@emilygorcenski.com"
    }

def fetch_airtrail_events():
    db = sqlite3.connect(":memory:")
    df = pd.read_csv("data/airports.csv")
    df.to_sql("airports", db)
    cursor = db.cursor()

    r = requests.get(AIRTRAIL_ENDPOINT, headers={"Authorization": f"Bearer {AIRTRAIL_KEY}"})

    if r.ok:
        data = r.json()["flights"]
        future_flights = list(filter(is_future, data))
        for flight in future_flights:
            flight_ics = Calendar()
            flight_event = Event(**make_ical_data(cursor, flight))
            flight_ics.add_component(flight_event)
            boarding_ics = Calendar()
            boarding_event = Event(**make_boarding_blocker(flight))
            boarding_ics.add_component(boarding_event)
            baikal.add_event(f"{flight_event.get('uid')}.ics",
                             flight_ics)
            baikal.add_event(f"{flight_event.get('uid')}.ics",
                             boarding_ics)
