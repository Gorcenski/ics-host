import importlib
from baikal import Baikal
from events import EventsImporter
import event_types as et

if __name__ == "__main__":
    base_url = "https://baikal.emilygorcenski.com/cal.php/calendars/"
    username = "emily"
    sources = {
        "airtrail": "AirtrailImporter",
        "imap": "ImapImporter",
    }
    calendar_data = [
        {
            "name": "default",
            "privacy": et.Privacy.PUBLIC,
            "except": []
        },
        {
            "name": "work",
            "privacy": et.Privacy.PRIVATE,
            "except": [
                et.TerminType.MEETING,
                et.TerminType.CONFERENCE,
                et.TerminType.CLASS,
                et.TerminType.TRAINING,
                et.AwayType.TRIP,
                et.AwayType.HOTEL,
                et.AwayType.BNB,
                et.AwayType.COUCH,
                et.AwayType.RESORT,
                et.TransportType.BUS,
                et.TransportType.TRAIN,
                et.TransportType.FLIGHT,
                et.TransportType.FERRY,
                et.TransportType.CAR,
            ]
        },
    ]
    calendar_names = [
        "default",
        "work",
    ]
    a = et.Privacy.PUBLIC

    calendars = [Baikal(f"{base_url}{username}/{c['name']}/",
                        c['privacy'],
                        c['except']) for c in calendar_data]
    for m, c in sources.items():
        try:
            module = importlib.import_module(m)
            class_ = getattr(module, c)
            for cal in calendars:
                instance = class_(cal.add_event)
                if isinstance(instance, EventsImporter):
                    instance.import_events()
        except ImportError as e:
            print(f"Error importing {m}: {e}")
    
    for c in calendars:
        c.write_to_file()
