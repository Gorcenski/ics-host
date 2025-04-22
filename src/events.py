from abc import ABC
import re
from datetime import datetime
from icalendar import Calendar, Event
from zoneinfo import ZoneInfo
from event_types import all_event_names

class EventHelper:
    @classmethod
    def set_event_tzinfo_params(cls, event : datetime, tz_name : str):
        return {
            "year":     event.year,
            "month":    event.month,
            "day":      event.day,
            "hour":     event.hour,
            "minute":   event.minute,
            "second":   event.second,
            "tzinfo":   ZoneInfo(tz_name)
        }

    @classmethod
    def split_multiple_events(cls, calendar : Calendar) -> list[dict[str,Calendar]]:
        if calendar.timezones:
            tzids = calendar.timezones[0].tz_name

        events = {}
        for event in calendar.events:
            if calendar.timezones:
                event.start = datetime(**cls.set_event_tzinfo_params(event.start, tzids))
                event.end = datetime(**cls.set_event_tzinfo_params(event.end, tzids))
            
            filename = f"{event.get('uid')}.ics"
            cal = cls.wrap_event(event)
            events[filename] = cal
        return events

    @classmethod
    def wrap_event(cls, event : Event) -> Calendar:
        cal = Calendar()
        cal.add_component(event)
        return cal
    
    @classmethod
    def categorize(cls, event : Event) -> Event:
    # ignores any user-input values that we don't care about, and focuses on what we do
    # this is to convert the description field in an event into categories fields
    # this allows manual categorization by editing the event description
        if not event.get("description"):
            return event
        category_match = re.search(r'\b(CATEGORIES:)(\S+)\b', event.get("description"))
        if category_match:
            label = category_match.group(1) # this should always be "CATEGORIES:""
            cat_list = category_match.group(2)
            categories = set(cat_list.split(","))
            event.set_inline("categories", categories.intersection(all_event_names))
            event.set_inline("description", event.get("description")
                                            .replace(label + cat_list, "")
                                            .replace("  ", " ")
                                            .strip())
            event = cls.wrap_event(event)
            # add_event(filename, event_ics)
        return event

class EventsImporter(ABC):
    def __init__(self, dispatch : callable):
        self.dispatch = dispatch
        
    def import_events(self) -> list[Event]:
        raise NotImplementedError("Subclasses must implement this method")
