import email
import hashlib
import os
from typing import Callable
from datetime import datetime
from icalendar import Calendar
from imapclient import IMAPClient
from imapclient.response_types import BodyData
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from events import EventHelper, EventsImporter

class ImapImporter(EventsImporter):
    def __init__(self, dispatch: Callable[..., None]):
        super().__init__(dispatch)
        self.dispatch = dispatch

    @staticmethod
    def get_credentials() -> tuple[str, str]:
        load_dotenv()
        email_username = os.environ["DREAMHOST_USERNAME"]
        email_password = os.environ["DREAMHOST_PASSWORD"]
        email_server = os.environ["DREAMHOST_SERVER"]
        return email_username, email_password, email_server
    
    @staticmethod
    def get_ical_attachments(msg) -> list[Calendar]:
        m = hashlib.md5()
        cal_attachments = []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':  
                continue 
            try:
                ics = part.get_payload(decode=True).decode('utf-8')
                cal = Calendar.from_ical(ics)
                cal_attachments.append(cal)
            except:
                continue
        return cal_attachments

    @classmethod
    def fetch_events(cls):
        email_username, email_password, email_server = cls.get_credentials()
        server = IMAPClient(email_server, use_uid=True, ssl=993)
        server.login(email_username, email_password)
        server.select_folder('INBOX', readonly=True)
        message_ids = server.search([b'NOT', b'SEEN']) # UNSEEN
        messages = server.fetch(message_ids, data=['ENVELOPE', 'BODYSTRUCTURE',  'RFC822.SIZE', 'RFC822'])

        events = []
        for _, content in messages.items():
            raw = email.message_from_bytes(content[b'RFC822'])
            ics_attachments = cls.get_ical_attachments(raw)
            for cal in ics_attachments:
                events.extend(EventHelper.split_multiple_events(cal))
        return events
