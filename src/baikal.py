import os
import re
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from icalendar import Calendar, Event
from requests.auth import HTTPDigestAuth
from events import EventHelper

load_dotenv()

# Baikal server information
USERNAME = os.environ["BAIKAL_USERNAME"]
PASSWORD = os.environ["BAIKAL_PASSWORD"]
BASE_URL = "https://baikal.emilygorcenski.com/cal.php/calendars/emily/default/"

HEADERS = {
    "Content-Type": "application/xml; charset=utf-8",
    "Depth": "infinity"
}

PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
    <d:prop>
        <d:displayname/>
        <c:calendar-data/>
    </d:prop>
</d:propfind>
"""

def fetch_remote_events() -> list[Event]:
    response = requests.request("PROPFIND",
                                BASE_URL,
                                headers=HEADERS,
                                data=PROPFIND_BODY,
                                auth=HTTPDigestAuth(USERNAME, PASSWORD))

    if response.ok:
        root = ET.fromstring(response.content)

        propstats       = [r.find('{DAV:}propstat')
                           for r in root.findall('{DAV:}response')]
        calendar_data   = [p
                           .find('{DAV:}prop')
                           .find('{urn:ietf:params:xml:ns:caldav}calendar-data')
                           for p in filter(lambda x: x is not None, propstats)]
        events          = [event
                           for data in filter(lambda x: x is not None, calendar_data)
                           for event in Calendar.from_ical(data.text).events]
        return events
    return []

def add_event(filename : str, event_ics : Calendar):
    header = {
        "Content-Type": "text/calendar; charset=utf-8"
    }
    filename = filename.replace("@emilygorcenski.com", "")
    event_ics = event_ics \
                .to_ical() \
                .decode("utf-8") \
                .replace("METHOD:REQUEST\r\n", "")
    print(filename)

    r = requests.put(f"{BASE_URL}{filename}",
                     data=event_ics,
                     headers=header,
                     auth=HTTPDigestAuth(USERNAME, PASSWORD))
    print(r.status_code)
    return r.status_code
