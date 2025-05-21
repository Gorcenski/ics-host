import hashlib
import os
from typing import Callable
import pandas as pd
import pytz
import requests
import sqlite3
import uuid
from datetime import datetime, timedelta
from dateutil import parser
from dotenv import load_dotenv
from icalendar import Event, vDatetime
from events import EventHelper, EventsImporter, EventFile


class AirtrailImporter(EventsImporter):
    @staticmethod
    def get_time() -> datetime:
        utc = pytz.UTC
        return utc.localize(datetime.now())
    
    @staticmethod
    def get_credentials() -> tuple[str, str]:
        load_dotenv()
        airtrail_endpoint = os.environ["AIRTRAIL_ENDPOINT"]
        airtrail_key = os.environ["AIRTRAIL_KEY"]
        return airtrail_endpoint, airtrail_key
    
    @staticmethod
    def get_airport_details(cursor, airport: str):
        iata = f"SELECT name, iata_code, iso_country, iso_region, municipality " \
               f"FROM airports WHERE iata_code = '{airport}'"
        name, code, country, region, municipality = cursor.execute(iata).fetchone()
        region = region.replace("US-", "") if country == "US" else region
        return name, code, country, region, municipality

    @staticmethod
    def format_airport_details(name, code, country, region, municipality):
        loc = region if country == "US" else country
        return f"{code} ({name} — {municipality}, {loc})"

    @staticmethod
    def make_ical_data(origin, destination, flight):
        m = hashlib.md5()
        flight_number = flight["flightNumber"]
        summary = f"{flight_number} {origin} ➠ {destination}"
        depart = parser.parse(flight["departure"])
        arrive = parser.parse(flight["arrival"])
        m.update(summary.encode("utf-8"))
        uid = uuid.UUID(m.hexdigest())
        return {
            "SUMMARY": summary,
            "DTSTART": vDatetime(depart),
            "DTEND": vDatetime(arrive),
            "CATEGORIES": ["FLIGHT"],
            "UID": f"{uid}@emilygorcenski.com"
        }

    @staticmethod
    def make_boarding_blocker(flight):
        m = hashlib.md5()
        flight_number = flight["flightNumber"]
        summary = f"Boarding {flight_number}"
        depart = parser.parse(flight["departure"])
        boarding = depart - timedelta(hours=0, minutes=30)
        m.update(summary.encode("utf-8"))
        uid = uuid.UUID(m.hexdigest())
        return {
            "SUMMARY": summary,
            "DTSTART": vDatetime(boarding),
            "DTEND": vDatetime(depart),
            "UID": f"{uid}@emilygorcenski.com"
        }
    
    @staticmethod
    def load_airport_db() -> sqlite3.Connection:
        db = sqlite3.connect(":memory:")
        df = pd.read_csv("data/airports.csv")
        df.to_sql("airports", db)
        cursor = db.cursor()
        return cursor

    @classmethod
    def fetch_events(cls) -> list[Event]:
        airtrail_endpoint, airtrail_key = cls.get_credentials()
        cursor = cls.load_airport_db()        
        r = requests.get(airtrail_endpoint,
                         headers={"Authorization": f"Bearer {airtrail_key}"})
        
        now = cls.get_time()
        is_future = lambda flight: parser.parse(flight["departure"]) > now
        
        events = []
        if r.ok:
            future_flights = list(filter(is_future, r.json()["flights"]))
            for flight in future_flights:
                origin      = cls.format_airport_details(
                                *cls.get_airport_details(cursor,
                                                          flight["from"]["iata"]))
                destination = cls.format_airport_details(
                                *cls.get_airport_details(cursor,
                                                          flight["to"]["iata"]))
                flight_event = Event(**cls.make_ical_data(origin,
                                                           destination,
                                                           flight))
                boarding_event = Event(**cls.make_boarding_blocker(flight))
                print(flight_event.to_ical())
                events.extend([
                    EventFile(filename=f"{flight_event.get('uid')}.ics",
                              event_ics=EventHelper.wrap_event(flight_event)),
                    EventFile(filename=f"{boarding_event.get('uid')}.ics",
                              event_ics=EventHelper.wrap_event(boarding_event))
                ])
        else:
            print("Failed to fetch data from Airtrail API.")
            print(r.status_code, r.text)
        return events
