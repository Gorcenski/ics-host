import email
import hashlib
import os
import uuid
from datetime import datetime
from icalendar import Calendar
from imapclient import IMAPClient
from imapclient.response_types import BodyData
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import baikal
from events import EventHelper

load_dotenv()

# Email server information
email_username = os.environ["DREAMHOST_USERNAME"]
email_password = os.environ["DREAMHOST_PASSWORD"]
email_server = os.environ["DREAMHOST_SERVER"]

def get_ical_attachments(msg) -> list[Calendar]:
    m = hashlib.md5()
    cal_attachments = []
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':  
            continue 

        # if part.get('Content-Disposition') is None: 
        #     continue

        if ('application/ics' not in part.get('Content-Type') and
            'text/calendar' not in part.get('Content-Type') and
            'text/plain' not in part.get('Content-Type')):
            continue
        try:
            ics = part.get_payload(decode=True).decode('utf-8')
            cal = Calendar.from_ical(ics)
            cal_attachments.append(cal)
        except Exception as e:
            continue

    return cal_attachments

def upload_attached_events(cal : Calendar):
    events = EventHelper.split_multiple_events(cal)
    for filename, cal in events.items():
        baikal.add_event(filename, cal)

def fetch_email_events():
    server = IMAPClient(email_server, use_uid=True, ssl=993)
    server.login(email_username, email_password)
    server.select_folder('INBOX', readonly=True)
    message_ids = server.search([b'NOT', b'SEEN']) # UNSEEN
    messages = server.fetch(message_ids, data=['ENVELOPE', 'BODYSTRUCTURE',  'RFC822.SIZE', 'RFC822'])

    for mid, content in messages.items():
        raw = email.message_from_bytes(content[b'RFC822'])
        ics_attachments = get_ical_attachments(raw)
        for cal in ics_attachments:
            upload_attached_events(cal)
