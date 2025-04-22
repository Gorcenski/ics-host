from enum import Enum
import os
import re
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from icalendar import Calendar, Event
from requests.auth import HTTPDigestAuth
from event_types import Privacy

class Baikal:
    def __init__(self, url : str,
                 privacy,
                 except_list):
        self.url = url
        self.privacy = privacy
        self.except_list = except_list

    @staticmethod
    def get_credentials() -> tuple[str, str]:
        load_dotenv()
        username = os.environ["BAIKAL_USERNAME"]
        password = os.environ["BAIKAL_PASSWORD"]
        return username, password
    
    @staticmethod
    def classify_event(event : Event, privacy : Privacy, except_list : Enum):
        event.update({"CLASSIFICATION": privacy.name})
        categories = set() if "CATEGORIES" not in event else set(event["CATEGORIES"])
        if categories.issubset({s.name for s in except_list}) and categories:
            event.update({"CLASSIFICATION": Privacy((privacy.value + 1) % 2).name})

    def fetch_remote_events(self) -> list[Event]:
        username, password = self.get_credentials()
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": "infinity"
        }

        propfind_body = """<?xml version="1.0" encoding="utf-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
            <d:prop>
                <d:displayname/>
                <c:calendar-data/>
            </d:prop>
        </d:propfind>
        """
        response = requests.request("PROPFIND",
                                    self.url,
                                    headers=headers,
                                    data=propfind_body,
                                    auth=HTTPDigestAuth(username, password))

        if response.ok:
            root = ET.fromstring(response.content)

            propstats       = [r.find('{DAV:}propstat')
                               for r in root.findall('{DAV:}response')]
            calendar_data   = [p.find('{DAV:}prop')
                               .find('{urn:ietf:params:xml:ns:caldav}calendar-data')
                               for p in filter(lambda x: x is not None, propstats)]
            events          = [event
                               for data in filter(lambda x: x is not None, calendar_data)
                               for event in Calendar.from_ical(data.text).events]
            return events
        return []

    def add_event(self, filename : str, event_ics : Calendar):
        username, password = Baikal.get_credentials()
        header = {
            "Content-Type": "text/calendar; charset=utf-8"
        }
        filename = filename.replace("@emilygorcenski.com", "")
        for e in event_ics.events:
            self.classify_event(e, self.privacy, self.except_list)
            
        event_ics = event_ics \
                    .to_ical() \
                    .decode("utf-8") \
                    .replace("METHOD:REQUEST\r\n", "")

        r = requests.put(f"{self.url}{filename}",
                            data=event_ics,
                            headers=header,
                            auth=HTTPDigestAuth(username, password))
        return r.status_code

    def write_to_file(self):
        username, password = Baikal.get_credentials()
        response = requests.request("GET",
                                    f"{self.url}?export",
                                    auth=HTTPDigestAuth(username, password))
        if response.ok:
            calendar_name = os.path.basename(os.path.dirname(self.url))
            try:
                with open(f"/www/calendar/{calendar_name}.ics", "wt") as ics_file:
                    ics_file.write(response.text)
            except:
                pass