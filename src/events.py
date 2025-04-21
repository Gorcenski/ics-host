from datetime import datetime
from icalendar import Calendar
from zoneinfo import ZoneInfo

class Event:
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
            cal = Calendar()
            cal.add_component(event)
            events[filename] = cal
        return events
