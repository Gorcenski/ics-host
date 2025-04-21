import event_types as Categories
from enum import Enum
from icalendar import Calendar, Event
import airtrail
import baikal
import imap
# import lingoda

def is_work_public(event : Event) -> bool:
    def get_value(type : Enum, category):
        try:
            return type[category].value < 10
        except:
            return False
        
    if not event.get("categories"):
        return False
    
    return all((get_value(Categories.TerminType, c) |
                get_value(Categories.AwayType, c) |
                get_value(Categories.TransportType, c))
               for c in event.get("categories"))

if __name__ == "__main__":
    family = Calendar()
    work = Calendar()

    # these add events to baikal directly
    airtrail_events = airtrail.fetch_airtrail_events(baikal.add_event)
    imap.fetch_email_events()

    events = baikal.fetch_remote_events()
    # events.extend(lingoda.fetch_lingoda_events())

    for event in events:
        family.events.append(event)

        if "egorcens@thoughtworks.com" not in event.to_ical().decode("utf-8"):
            if is_work_public(event):
                event.set_inline("classification", "PUBLIC")
            else:
                event.set_inline("classification", "PRIVATE")
            work.events.append(event)

    try:
        with open("/www/calendar/emilygorcenski.ics", "wt") as ics_file:
            ics_file.write(family.to_ical().decode("utf-8"))
        with open("/www/calendar/emilygorcenski_work.ics", "wt") as ics_file:
            ics_file.write(work.to_ical().decode("utf-8"))
    except:
        pass
