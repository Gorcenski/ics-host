"""Publish read-only .ics feeds from the Baikal `default` calendar.

Replaces compile.py. The model is deliberately one-directional:

    Baikal `default` (source of truth)  ->  family.ics  (verbatim)
                                        ->  work.ics    (selectively redacted)

Nothing is ever written back into Baikal, which removes the whole class of
resource-name/UID collisions the old script had, and means a bug here can never
damage the source data.

Redaction actually strips the details rather than setting CLASS:PRIVATE. CLASS is
advisory — Google Calendar imports a CLASS:PRIVATE event and still shows its
SUMMARY — so a privacy scheme built on it leaks. Redacted events keep only their
times and UID and are retitled "Busy".

Usage:  python publish.py [--dry-run]
Env:    BAIKAL_URL, BAIKAL_USERNAME, BAIKAL_PASSWORD, ICS_OUTPUT_DIR
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from icalendar import Calendar
from requests.auth import HTTPDigestAuth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Categories that keep their full detail in the work feed. Everything else —
# including anything untagged — is redacted to a busy block. Fail closed: a new
# event with a category not listed here is hidden rather than exposed.
KEEP_DETAIL = {
    # travel
    "HOTEL", "BNB", "COUCH", "RESORT", "TRIP",
    "BUS", "TRAIN", "FLIGHT", "FERRY", "CAR",
    # work-relevant commitments
    "MEETING", "CONFERENCE", "CLASS", "TRAINING",
}

# Properties a redacted event may keep. Anything else is dropped, so new or
# unexpected properties fail closed too.
REDACTED_KEEP = {
    "UID", "DTSTAMP", "DTSTART", "DTEND", "DURATION",
    "RRULE", "RDATE", "EXDATE", "RECURRENCE-ID",
    "SEQUENCE", "STATUS", "TRANSP", "CREATED", "LAST-MODIFIED",
}

BUSY_TITLE = "Busy"


def categories_of(event) -> set[str]:
    """Normalised category names for an event.

    Handles the icalendar vCategory type, plain strings, and the stray
    "{'DINNER'}" set-repr that the old script wrote into a record.
    """
    raw = event.get("CATEGORIES")
    if raw is None:
        return set()
    out: set[str] = []
    out = set()
    for item in (raw if isinstance(raw, list) else [raw]):
        cats = getattr(item, "cats", None)
        vals = [str(c) for c in cats] if cats else [str(item)]
        for v in vals:
            v = v.strip().strip("{}").strip("'\"").upper()
            if v:
                out.add(v)
    return out


def redact(event):
    """Return a copy of `event` reduced to a busy block."""
    from icalendar import Event

    slim = Event()
    for key in event.keys():
        if key.upper() in REDACTED_KEEP:
            slim.add(key, event[key], encode=False)
    slim["SUMMARY"] = BUSY_TITLE
    slim["CLASS"] = "PRIVATE"
    # Belt and braces: if the source had no TRANSP, an opaque block is what a
    # colleague's scheduler should see.
    slim.setdefault("TRANSP", "OPAQUE")
    return slim


def build(source: Calendar, name: str, redact_private: bool) -> tuple[Calendar, int, int]:
    out = Calendar()
    out.add("prodid", "-//ics-host//publish//EN")
    out.add("version", "2.0")
    out.add("x-wr-calname", name)
    # Carry timezone definitions over or floating times shift for subscribers.
    for tz in source.walk("VTIMEZONE"):
        out.add_component(tz)

    kept = redacted = 0
    for ev in source.walk("VEVENT"):
        if not redact_private:
            out.add_component(ev)
            kept += 1
            continue
        cats = categories_of(ev)
        if cats and cats.issubset(KEEP_DETAIL):
            out.add_component(ev)
            kept += 1
        else:
            out.add_component(redact(ev))
            redacted += 1
    return out, kept, redacted


def write_atomic(path: Path, data: bytes) -> None:
    """Write via temp file + rename so a subscriber never reads a partial feed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def main() -> int:
    load_dotenv()
    dry = "--dry-run" in sys.argv
    base = os.environ["BAIKAL_URL"].rstrip("/")
    user = os.environ["BAIKAL_USERNAME"]
    pw = os.environ["BAIKAL_PASSWORD"]
    outdir = Path(os.environ.get("ICS_OUTPUT_DIR", "/www/calendar"))

    url = f"{base}/{user}/default/?export"
    resp = requests.get(url, auth=HTTPDigestAuth(user, pw), timeout=60)
    if not resp.ok:
        logger.error("fetch failed: HTTP %s from %s", resp.status_code, url)
        return 1

    source = Calendar.from_ical(resp.content)
    total = len(list(source.walk("VEVENT")))
    logger.info("fetched %d events from default", total)
    if total == 0:
        # Never overwrite good feeds with an empty one because of a transient fault.
        logger.error("source calendar is empty — refusing to publish")
        return 1

    for filename, display, do_redact in (
        ("family.ics", "Emily (full)", False),
        ("work.ics", "Emily (work)", True),
    ):
        cal, kept, red = build(source, display, do_redact)
        data = cal.to_ical()
        logger.info("%-11s %5d events  (%d detailed, %d busy)  %d bytes",
                    filename, kept + red, kept, red, len(data))
        if not dry:
            write_atomic(outdir / filename, data)

    if dry:
        logger.info("dry run — nothing written")
    else:
        logger.info("wrote feeds to %s", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
