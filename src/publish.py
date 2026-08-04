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

import datetime
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


def snapshot(data: bytes, snapdir: Path, retention_days: int) -> None:
    """Keep a dated full-detail copy as a restore point, pruning old ones.

    Exists because on 2026-08-04 an iPhone deleting its CalDAV account issued a
    DELETE on the server collection and removed 792 events. The only surviving copy
    was the published family.ics from four minutes earlier — recovery was luck of
    timing. One dated copy per day gives a rolling month of restore points instead.

    Deliberately one file per day, overwritten by later runs, rather than one per
    15-minute run: 96 files a day is noise, and the newest run for a given day is
    the one worth keeping. Callers must only invoke this after a *successful*
    non-empty fetch, or the snapshots inherit the outage.
    """
    today = datetime.date.today().isoformat()
    snapdir.mkdir(parents=True, exist_ok=True)
    write_atomic(snapdir / f"family-{today}.ics", data)

    cutoff = datetime.date.today() - datetime.timedelta(days=retention_days)
    pruned = 0
    for old in snapdir.glob("family-*.ics"):
        # Prune on the date in the filename, not mtime: a restore or a file copy
        # would reset mtime and silently keep stale snapshots alive.
        try:
            stamp = datetime.date.fromisoformat(old.stem.removeprefix("family-"))
        except ValueError:
            continue
        if stamp < cutoff:
            old.unlink()
            pruned += 1
    kept = len(list(snapdir.glob("family-*.ics")))
    logger.info("snapshot family-%s.ics (%d kept, %d pruned) in %s",
                today, kept, pruned, snapdir)


# Which Baikal collection feeds which published file.
#   collection : the Baikal calendar URI under /calendars/<user>/
#   outputs    : (filename, X-WR-CALNAME, redact?, snapshot?)
# Each collection is fetched and published independently — see main().
SOURCES = (
    {
        "collection": "default",
        "outputs": (
            ("family.ics", "Emily (full)", False, True),
            ("work.ics", "Emily (work)", True, False),
        ),
    },
    {
        # The Bruins schedule is a whole separate collection, replaced each season.
        # Its published URL carries the season so subscribers can tell which one they
        # have; a new season means a new file and a new Caddy route, leaving last
        # season's subscribers untouched rather than silently swapping the contents.
        "collection": "bruins",
        "outputs": (
            ("bruins-2026-27.ics", "Boston Bruins 2026-27", False, False),
        ),
    },
)


def fetch(base: str, user: str, pw: str, collection: str) -> Calendar | None:
    """Fetch one collection. Returns None on failure or if empty."""
    url = f"{base}/{user}/{collection}/?export"
    try:
        resp = requests.get(url, auth=HTTPDigestAuth(user, pw), timeout=60)
    except Exception as e:
        logger.error("%s: fetch raised %s: %s", collection, type(e).__name__, e)
        return None
    if not resp.ok:
        logger.error("%s: fetch failed HTTP %s from %s", collection, resp.status_code, url)
        return None
    cal = Calendar.from_ical(resp.content)
    total = len(list(cal.walk("VEVENT")))
    logger.info("fetched %d events from %s", total, collection)
    if total == 0:
        # Never overwrite good feeds with an empty one because of a transient fault
        # or a deleted collection. This guard is why the 2026-08-04 iPhone deletion
        # was recoverable: the run that followed it errored instead of publishing
        # nothing over the last good copy.
        logger.error("%s: source is empty — refusing to publish from it", collection)
        return None
    return cal


def main() -> int:
    load_dotenv()
    dry = "--dry-run" in sys.argv
    base = os.environ["BAIKAL_URL"].rstrip("/")
    user = os.environ["BAIKAL_USERNAME"]
    pw = os.environ["BAIKAL_PASSWORD"]
    outdir = Path(os.environ.get("ICS_OUTPUT_DIR", "/www/calendar"))
    # Outside the web root on purpose: these are full-detail copies of a calendar
    # whose public feed is deliberately redacted.
    snapdir = Path(os.environ.get("ICS_SNAPSHOT_DIR", "/home/ubuntu/ics-host/snapshots"))
    retention = int(os.environ.get("ICS_SNAPSHOT_RETENTION_DAYS", "30"))

    failures = []
    for spec in SOURCES:
        collection = spec["collection"]
        # Independent per collection on purpose: a missing or emptied `bruins` must
        # not stop family.ics and work.ics from publishing. Sharing one early return
        # would let a secondary calendar take down the primary feeds.
        source = fetch(base, user, pw, collection)
        if source is None:
            failures.append(collection)
            continue

        for filename, display, do_redact, do_snapshot in spec["outputs"]:
            cal, kept, red = build(source, display, do_redact)
            data = cal.to_ical()
            logger.info("%-20s %5d events  (%d detailed, %d busy)  %d bytes",
                        filename, kept + red, kept, red, len(data))
            if not dry:
                write_atomic(outdir / filename, data)
                # Snapshot only the full-detail primary feed. work.ics is derivable
                # from it, and the Bruins schedule is re-importable from source.
                if do_snapshot:
                    snapshot(data, snapdir, retention)

    if dry:
        logger.info("dry run — nothing written")
    else:
        logger.info("wrote feeds to %s", outdir)

    if failures:
        # Non-zero so cron/logs surface it, but only after publishing what worked.
        logger.error("collections that failed to publish: %s", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
