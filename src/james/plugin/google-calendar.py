# -*- coding: utf-8 -*-
#pip install google-api-python-client

import gflags
import httplib2
import datetime
import pytz

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run

from james.plugin import *

class GoogleCalendarPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(GoogleCalendarPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('show', 'Show calendar entries from google', self.cmd_calendar_show)
        self.commands.create_subcommand('speak', 'Speak calendar entries from google', self.cmd_calendar_speak)
        self.commands.create_subcommand('list', 'List all google calendars', self.cmd_calendars_list)

        self.timeZone = pytz.timezone(self.core.config['core']['timezone'])

        self.eventFetches = 0
        self.eventsFetched = 0

        FLAGS = gflags.FLAGS
        FLAGS.auth_local_webserver = False
        FLOW = OAuth2WebServerFlow(
            client_id = '474730164735-f9l08rmhjihi6vhgckf1p3pmnolnf3sc.apps.googleusercontent.com',
            client_secret = self.config['client_secret'],
            scope = 'https://www.googleapis.com/auth/calendar',
            user_agent = 'jame2/001a')

        storage = Storage(os.path.join(os.path.expanduser("~"), ".james_gcal_dat"))
        credentials = storage.get()
        if credentials is None or credentials.invalid == True:
            credentials = run(FLOW, storage)

        http = httplib2.Http()
        http = credentials.authorize(http)

        self.service = build(serviceName='calendar', version='v3', http=http, developerKey='AIzaSyAIE6TwzGnQcPn4vDgXoUoOtNDK__x6ong')

    # internal commands
    def fetchEvents(self, calendarId, pageToken=None):
        events = {}
        today = True
        tzStr = datetime.datetime.now(self.timeZone).strftime('%z')
        tzStr2 = tzStr[:3] + ':' + tzStr[3:]

        tStart = datetime.datetime.now(self.timeZone)
        tEnd = datetime.datetime.now(self.timeZone)
        if datetime.datetime.now(self.timeZone).strftime('%H') > 18:
            tEnd += datetime.timedelta(days=1)

        try:
            events = self.service.events().list(
                calendarId = calendarId,
                singleEvents = True,
                maxResults = 1000,
                orderBy = 'startTime',
                timeMin = tStart.strftime('%Y-%m-%dT%H:%M:%S') + "+00:00",
                timeMax = tEnd.strftime('%Y-%m-%dT23:59:59') + "+00:00",
                pageToken = pageToken,
                ).execute()
            self.eventFetches += 1
        except Exception as e:
            if e == '':
                self.logger.error("Event fetching error, probably oauth2 session refresh")
                return False
            else:
                self.logger.error("Event fetching error: %s" % e)
        return events

    def requestEvents(self):
        allEvents = []
        for calendar in self.config['calendarIds']:
            events = False
            while not events:
                events = self.fetchEvents(calendar)
                if not events:
                    time.sleep(1)

            while True:
                for event in events['items']:
                    allEvents.append(event)
                page_token = events.get('nextPageToken')
                if page_token:
                    events = getEvents(calendar, page_token)
                else:
                    break

        retList = []
        for event in allEvents:
            self.eventsFetched += 1

            # whole day event:
            if 'date' in event['start'].keys():
                # retStr = "Today: "
                print event['start']['date']


            # normal event:
            if 'dateTime' in event['start'].keys():
                eventTime = datetime.datetime.strptime(event['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if eventTime.day != datetime.datetime.now(self.timeZone).day:
                    retStr = "Tomorrow at %02d:%02d: " % (eventTime.hour, eventTime.minute)
                else:
                    retStr = "At %02d:%02d: " % (eventTime.hour, eventTime.minute)
            if event['status'] == "tentative":
                retStr += " possibly "
                # evil is: 
            retStr += event['summary']
            retList.append(retStr)

        if len(retList):
            return ['Calendar events: '] + retList + ['End of calendar']
        else:
            return ['No calendar events']

    # commands
    def cmd_calendar_show(self, args):
        return self.requestEvents()

    def cmd_calendar_speak(self, args):
        self.send_command(['espeak', 'say', '. '.join(self.requestEvents())])

    def cmd_calendars_list(self, args):
        try:
            retList = ['Google calendars:', 'ID: Name']
            calendars = self.service.calendarList().list().execute()
            for cal in calendars['items']:
                if cal['kind'] == 'calendar#calendarListEntry':
                    retList.append(cal['id'] + ": " + cal['summary'])
            return retList
        except Exception as e:
            print e

    # internal
    def process_proximity_event(self, newstatus):
        self.logger.debug("Google Calendar Processing proximity event")
        if newstatus['status'][self.core.location]:
            self.cmd_calendar_speak(None)

    # status
    def return_status(self):
        ret = {}
        ret['eventFetches'] = self.eventFetches
        ret['eventsFetched'] = self.eventsFetched
        return ret

descriptor = {
    'name' : 'gcal',
    'help' : 'Google Calendar integration',
    'command' : 'gcal',
    'mode' : PluginMode.MANAGED,
    'class' : GoogleCalendarPlugin,
    'detailsNames' : { 'eventFetches' : "Amount of event fetches",
                       'eventsFetched' : "Amount of events fetched" }
}
