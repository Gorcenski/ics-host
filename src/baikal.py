import os
import re
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from icalendar import Calendar, Event
from requests.auth import HTTPDigestAuth

class Baikal:
    @staticmethod
    def get_credentials() -> tuple[str, str]:
        load_dotenv()
        username = os.environ["BAIKAL_USERNAME"]
        password = os.environ["BAIKAL_PASSWORD"]
        base_url = "https://baikal.emilygorcenski.com/cal.php/calendars/emily/default/"
        return username, password, base_url

    @staticmethod
    def fetch_remote_events() -> list[Event]:
        username, password, base_url = Baikal.get_credentials()
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
                                    base_url,
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

    @staticmethod
    def add_event(filename : str, event_ics : Calendar):
        username, password, base_url = Baikal.get_credentials()
        header = {
            "Content-Type": "text/calendar; charset=utf-8"
        }
        filename = filename.replace("@emilygorcenski.com", "")
        event_ics = event_ics \
                    .to_ical() \
                    .decode("utf-8") \
                    .replace("METHOD:REQUEST\r\n", "")

        r = requests.put(f"{base_url}{filename}",
                            data=event_ics,
                            headers=header,
                            auth=HTTPDigestAuth(username, password))
        return r.status_code
