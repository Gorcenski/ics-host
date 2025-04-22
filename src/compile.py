import importlib
import event_types as Categories
from enum import Enum
from icalendar import Calendar, Event
from baikal import Baikal
from events import EventsImporter
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

def get_events_from_server():
    all_events = Baikal.fetch_remote_events()
    for event in all_events:
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

if __name__ == "__main__":
    family = Calendar()
    work = Calendar()

    sources = {
        "airtrail": "AirtrailImporter",
        "imap": "ImapImporter",
    }

    for m, c in sources.items():
        try:
            module = importlib.import_module(m)
            class_ = getattr(module, c)
            instance = class_(Baikal.add_event)
            if isinstance(instance, EventsImporter):
                instance.import_events()
        except ImportError as e:
            print(f"Error importing {m}: {e}")
        

    get_events_from_server()    
