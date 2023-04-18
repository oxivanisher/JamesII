# -*- coding: utf-8 -*-
# pip install google-api-python-client

import os
import time

import datetime
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from james.plugin import *


class GoogleCalendarPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(GoogleCalendarPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('show', 'Show calendar entries from google', self.cmd_calendar_show)
        self.commands.create_subcommand('speak', 'Speak calendar entries from google', self.cmd_calendar_speak)
        self.commands.create_subcommand('list', 'List all google calendars', self.cmd_calendars_list)

        self.timeZone = pytz.timezone(self.core.config['core']['timezone'])

        self.load_state('eventFetches', 0)
        self.load_state('eventsFetched', 0)

        self.event_cache = []
        self.event_cache_timestamp = 0
        self.last_fetch = 0

        if 'cache_timeout' in self.config.keys():
            self.event_cache_timeout = self.config['cache_timeout']
        else:
            self.event_cache_timeout = 10

        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = None

        tokens_file = os.path.join(os.path.expanduser("~"), ".james_gcal_token.json")
        client_secret_file = os.path.join(os.path.expanduser("~"), ".james2_google_client_secret.json")

        if os.path.exists(tokens_file):
            creds = Credentials.from_authorized_user_file(tokens_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secret_file):
                    raise Exception("Please provide the google client_secret.jason file (see README.md) in location: %s"
                                    % client_secret_file)
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(tokens_file, 'w') as token:
                token.write(creds.to_json())

        try:
            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            self.logger.warning("Google calendar was unable to update due to error: %s" % e)

        self.core.add_timeout(10, self.update_after_midnight)

    # internal commands
    def update_after_midnight(self):
        self.requestEvents()
        now = datetime.datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        seconds_until_midnight = 86400 - seconds_since_midnight + 30 # adding 30 seconds just to be sure its the next day
        self.logger.debug("Google calendar was just fetched. Will fetch again in %s seconds" % seconds_until_midnight)
        self.core.add_timeout(seconds_until_midnight, self.update_after_midnight)

    def fetchEvents(self, calendar_id, page_token=None):
        events = {}

        tStart = datetime.datetime.now(self.timeZone)
        tEnd = datetime.datetime.now(self.timeZone)

        try:
            events = self.service.events().list(calendarId=calendar_id,
                                                maxResults=100,
                                                singleEvents=True,
                                                timeMin=tStart.strftime('%Y-%m-%dT00:00:00') + "+00:00",
                                                timeMax=tEnd.strftime('%Y-%m-%dT23:59:59') + "+00:00",
                                                orderBy='startTime').execute()
            self.eventFetches += 1
        except Exception as e:
            if e == '':
                self.logger.error("Event fetching error, probably oauth2 session refresh")
                return False
            else:
                self.logger.error("Event fetching error: %s" % e)
        return events

    def getCalendarIds(self):
        personClientIds = {}
        for person in self.core.persons_status:
            self.logger.debug("Found person: %s" % person)
            personClientIds[person] = []
            try:
                if self.core.persons_status[person]:
                    for calendarId in self.core.config['persons'][person]['gcals']:
                        personClientIds[person].append(calendarId)
                        self.logger.debug("Found calendar: %s" % calendarId)
            except KeyError:
                pass
        self.logger.debug("getCalendarIds: %s" % personClientIds)
        return personClientIds

    def requestEvents(self):
        self.logger.debug("requestEvents from google calendar")
        if time.time() < (self.event_cache_timestamp + self.event_cache_timeout):
            self.logger.debug("cache is still valid, answering with the cache data")
            return self.event_cache

        all_events = []
        person_client_ids = self.getCalendarIds()

        no_alarm_clock_active = False

        for person in list(person_client_ids.keys()):
            self.logger.debug("fetching calendars for person: %s" % person)
            for calendar in person_client_ids[person]:
                self.logger.debug("fetching calendar: %s" % calendar)
                calendar_events = []
                events = False
                while not events:
                    events = self.fetchEvents(calendar)
                    if not events:
                        time.sleep(1)

                while True:
                    for event in events['items']:
                        calendar_events.append(event)
                        all_events.append((person, event))
                    page_token = events.get('nextPageToken')
                    if page_token:
                        events = getEvents(calendar, page_token)
                    else:
                        break

                self.logger.debug("fetched %s events for calendar %s:" % (len(calendar_events), calendar))
                for event in calendar_events:
                    self.logger.debug(event)

        self.event_cache = []
        for (person, event) in all_events:
            self.eventsFetched += 1
            return_string = False
            now = datetime.datetime.now()

            # whole day event:
            if 'date' in list(event['start'].keys()):
                if event['start']['date'] == datetime.datetime.now(self.timeZone).strftime('%Y-%m-%d'):
                    happening_today = True
                    return_string = "Today "
                else:
                    happening_today = False
                    return_string = "Tomorrow "

            # check there is a "don't wake up" event present in google calendar
            if event['summary'].lower() in self.config['no_alarm_clock'].lower():
                self.logger.info("Found a event which activates no_alarm_clock: %s" % event['summary'])
                no_alarm_clock_active = True

            # ignore ignored_events from config
            if event['summary'].lower() in self.config['ignored_events'].lower():
                self.logger.debug("Ignoring event because of ignored_events: %s" % event)
                return_string = False
                continue

            # normal event:
            elif 'dateTime' in list(event['start'].keys()):
                eventTimeStart = datetime.datetime.strptime(event['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                eventTimeEnd = datetime.datetime.strptime(event['end']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if eventTimeStart.day > datetime.datetime.now().day:
                    return_string = "Tomorrow at %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)
                else:

                    if eventTimeStart < now < eventTimeEnd:
                        return_string = "Until %02d:%02d: " % (eventTimeEnd.hour, eventTimeEnd.minute)
                    elif now < eventTimeStart:
                        return_string = "At %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)

            if return_string:
                if event['status'] == "tentative":
                    return_string += " possibly "
                    # evil is:
                return_string += event['summary']
                self.event_cache.append(return_string)

        self.event_cache_timestamp = time.time()

        self.core.no_alarm_clock_update(no_alarm_clock_active, 'gcal')

        if len(self.event_cache):
            self.logger.debug("Returning %s events" % len(self.event_cache))
            return self.event_cache

    # commands
    def cmd_calendar_show(self, args):
        return self.requestEvents

    def cmd_calendar_speak(self, args):
        try:
            self.send_command(['espeak', 'say', '. '.join(self.requestEvents)])
        except Exception:
            return []

    def cmd_calendars_list(self, args):
        try:
            retList = ['Google calendars:', 'ID: Name']
            calendars = self.service.calendarList().list().execute()
            for cal in calendars['items']:
                if cal['kind'] == 'calendar#calendarListEntry':
                    retList.append(cal['id'] + ": " + cal['summary'])
            return retList
        except Exception as e:
            print(e)

    # internal
    def process_proximity_event(self, newstatus):
        self.logger.debug("Google Calendar Processing proximity event")
        if newstatus['status'][self.core.location]:
            self.core.add_timeout(0, self.cmd_calendar_speak, None)

    # status
    def return_status(self, verbose=False):
        ret = {'eventFetches': self.eventFetches, 'eventsFetched': self.eventsFetched}
        return ret


descriptor = {
    'name': 'gcal',
    'help': 'Google Calendar integration',
    'command': 'gcal',
    'mode': PluginMode.MANAGED,
    'class': GoogleCalendarPlugin,
    'detailsNames': {'eventFetches': "Amount of event fetches",
                     'eventsFetched': "Amount of events fetched"}
}
