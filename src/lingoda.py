import re
import requests
from functools import partial
from icalendar import Calendar, Event
from typing import TypedDict
from .event_types import TerminType

class LanguageCourse(TypedDict):
    langauge_iso: str
    url: str

def get_class_title(description: str) -> str:
    regex = r"(Lingoda class:)(.*)(\n--)"
    m = re.match(regex, description)
    try:
        return m.group(2)
    except:
        return None

def fetch_remote_events(url : str) -> str:
    r = requests.get(url)
    if r.ok:
        return r.text
    else:
        return None

def format_event(language : str, event : Event):
    title = get_class_title(event.description)
    # assign more contextual name and type
    event.name = f"Lingoda ({language}): {title}"
    event.categories = {str(TerminType.CLASS).upper()}
    return event

def parse_lingoda_events(language : str, ical_text : str) -> list[Event]:
    # assume multiple BEGIN:VCALENDAR events but only take the first one
    cal = iter(Calendar.parse_multiple(ical_text)).__next__()
    format = partial(format_event, language)
    return [format(e) for e in cal.events]

def get_lingoda_events(courses : list[LanguageCourse]):
    classes = []
    for course in courses:
        classes.extend(parse_lingoda_events(course["langauge_iso"],
                                            fetch_remote_events(course["url"])))
    return classes
