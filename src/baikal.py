from enum import Enum
import os
import re
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from icalendar import Calendar, Event
from requests.auth import HTTPDigestAuth
from events import EventFile, EventsImporter, EventHelper
from event_types import Privacy
import logging

logging.getLogger().setLevel(logging.INFO)


class BaikalImporter(EventsImporter):
    @classmethod
    def fetch_events(cls):
        load_dotenv()
        baikal_url = os.environ["BAIKAL_URL"]
        username = os.environ["BAIKAL_USERNAME"]
        url = f"{baikal_url}{username}/default"
        return Baikal.fetch_remote_events(url)

class Baikal:
    @staticmethod
    def get_credentials() -> tuple[str, str]:
        load_dotenv()
        username = os.environ["BAIKAL_USERNAME"]
        password = os.environ["BAIKAL_PASSWORD"]
        return username, password
    
    @staticmethod
    def classify_event(privacy : Privacy, except_list : Enum, event : Event):
        event.update({"CLASS": privacy.name})
        categories = set()
        if "CATEGORIES" in event:
            try:
                categories = set(event.get("categories"))
            except Exception as e:
                categories = {
                    c.to_ical().decode("utf-8")
                    for c in event.get("categories")
                }                
        if categories.issubset({s.name for s in except_list}) and categories:
            event.update({"CLASS": Privacy((privacy.value + 1) % 2).name})

    @classmethod
    def fetch_remote_events(cls, url : str) -> list[Event]:
        username, password = cls.get_credentials()
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": "infinity"
        }

        response = requests.get(f"{url}?export",
                                headers=headers,
                                auth=HTTPDigestAuth(username, password))

        if response.ok:
            cal = Calendar().from_ical(response.content)
            return [EventFile(filename=f"{e['uid']}.ics",
                              event_ics=EventHelper.wrap_event(e))
                    for e in cal.events]
        return []

    @classmethod
    def add_event(cls, 
                  event_file : EventFile,
                  url : str,
                  default_privacy : Privacy,
                  except_list : Enum):
        username, password = cls.get_credentials()
        header = {
            "Content-Type": "text/calendar; charset=utf-8"
        }
        filename = event_file.filename
        event_cal = event_file.event_ics
        for e in event_cal.events:
            cls.classify_event(default_privacy, except_list, e)
        
        event_cal = event_cal \
                    .to_ical() \
                    .decode("utf-8") \
                    .replace("METHOD:REQUEST\r\n", "")
        r = requests.put(f"{url}{filename}",
                            data=event_cal,
                            headers=header,
                            auth=HTTPDigestAuth(username, password))
        return r.status_code

    @classmethod
    def write_to_file(cls, url : str):
        username, password = cls.get_credentials()
        response = requests.request("GET",
                                    f"{url}?export",
                                    auth=HTTPDigestAuth(username, password))
        if response.ok:
            calendar_name = os.path.basename(os.path.dirname(url))
            try:
                with open(f"/www/calendar/{calendar_name}.ics", "wt") as ics_file:
                    print(f"writing to {calendar_name}...")
                    ics_file.write(response.text)
            except:
                pass