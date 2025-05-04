from functools import partial
import importlib
import logging
from baikal import Baikal
from events import EventsImporter
import event_types as et

if __name__ == "__main__":
    print("starting sync...")
    base_url = "https://baikal.emilygorcenski.com/cal.php/calendars/"
    username = "emily"
    sources = {
        "airtrail": "AirtrailImporter",
        "imap": "ImapImporter",
        "baikal": "BaikalImporter",
    }
    calendar_data = [
        {
            "url": f"{base_url}{username}/default/",
            "default_privacy": et.Privacy.PUBLIC,
            "except_list": []
        },
        {
            "url": f"{base_url}{username}/work/",
            "default_privacy": et.Privacy.PRIVATE,
            "except_list": [
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

    importers = [partial(Baikal.add_event,**c) for c in calendar_data]
    for m, c in sources.items():
        try:
            module = importlib.import_module(m)
            class_ = getattr(module, c)
            instance = class_(None)
            if isinstance(instance, EventsImporter):
                events = instance.fetch_events()
                for importer in importers:
                    logging.info(f"Adding events from {type(importer)}")
                    instance.add_event(events, importer)
        except ImportError as e:
            print(f"Error importing {m}: {e}")
    
    for c in calendar_data:
        Baikal.write_to_file(c["url"])
