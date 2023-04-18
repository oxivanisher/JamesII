# -*- coding: utf-8 -*-
# pip install google-api-python-client

import gflags
import httplib2
import datetime
import pytz

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
from oauth2client import tools

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

        flags = gflags.FLAGS
        flags.auth_local_webserver = False
        flow = OAuth2WebServerFlow(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            scope='https://www.googleapis.com/auth/calendar',
            user_agent='james2/001a')

        storage = Storage(os.path.join(os.path.expanduser("~"), ".james_gcal_dat"))
        credentials = storage.get()
        if credentials is None or credentials.invalid is True:
            credentials = tools.run_flow(flow, storage, flags)

        http = httplib2.Http()
        http = credentials.authorize(http)

        self.service = build(serviceName='calendar', version='v3', http=http,
                             developerKey=self.config['developer_key'])

    # internal commands
    def fetchEvents(self, calendar_id, page_token=None):
        events = {}
        today = True
        tzStr = datetime.datetime.now(self.timeZone).strftime('%z')
        tzStr2 = tzStr[:3] + ':' + tzStr[3:]

        tStart = datetime.datetime.now(self.timeZone)
        tEnd = datetime.datetime.now(self.timeZone)
        if int(datetime.datetime.now(self.timeZone).strftime('%H')) > 12:
            tEnd += datetime.timedelta(days=1)

        try:
            events = self.service.events().list(
                calendarId=calendar_id,
                singleEvents=True,
                maxResults=1000,
                orderBy='startTime',
                timeMin=tStart.strftime('%Y-%m-%dT00:00:00') + "+00:00",
                timeMax=tEnd.strftime('%Y-%m-%dT23:59:59') + "+00:00",
                pageToken=page_token,
            ).execute()
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
        allEvents = []
        personClientIds = self.getCalendarIds()

        for person in list(personClientIds.keys()):
            self.logger.debug("fetching calendars for person: %s" % person)
            for calendar in personClientIds[person]:
                self.logger.debug("fetching calendar: %s" % calendar)
                events = False
                while not events:
                    events = self.fetchEvents(calendar)
                    if not events:
                        time.sleep(1)

                while True:
                    for event in events['items']:
                        allEvents.append((person, event))
                    page_token = events.get('nextPageToken')
                    if page_token:
                        events = getEvents(calendar, page_token)
                    else:
                        break

                self.logger.debug("fetched %s events" % len(allEvents))

        retList = []
        for (person, event) in allEvents:
            self.eventsFetched += 1
            retStr = False
            now = datetime.datetime.now()

            # ignore ignored_events from config
            if event['summary'] in self.config['ignored_events']:
                self.logger.debug("Ignoring event because of ignored_events: %s" % event)
                continue

            # whole day event:
            if 'date' in list(event['start'].keys()):
                if event['start']['date'] == datetime.datetime.now(self.timeZone).strftime('%Y-%m-%d'):
                    retStr = "Today "
                else:
                    retStr = "Tomorrow "

            # normal event:
            elif 'dateTime' in list(event['start'].keys()):
                eventTimeStart = datetime.datetime.strptime(event['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                eventTimeEnd = datetime.datetime.strptime(event['end']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if eventTimeStart.day > datetime.datetime.now().day:
                    retStr = "Tomorrow at %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)
                else:

                    if eventTimeStart < now < eventTimeEnd:
                        retStr = "Until %02d:%02d: " % (eventTimeEnd.hour, eventTimeEnd.minute)
                    elif now < eventTimeStart:
                        retStr = "At %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)

            if retStr:
                if event['status'] == "tentative":
                    retStr += " possibly "
                    # evil is:
                retStr += event['summary']
                retList.append(retStr)

        if len(retList):
            self.logger.debug("Returning %s events" % len(retList))
            return retList

    # commands
    def cmd_calendar_show(self, args):
        return self.requestEvents()

    def cmd_calendar_speak(self, args):
        try:
            self.send_command(['espeak', 'say', '. '.join(self.requestEvents())])
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
