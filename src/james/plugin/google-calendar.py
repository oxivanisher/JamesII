
import gflags
import httplib2

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

        FLAGS = gflags.FLAGS
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
    def fetchEvents(self, pageToken=None):
        events = self.service.events().list(
            calendarId = self.config['calendarId'],
            singleEvents = True,
            maxResults = 1000,
            orderBy = 'startTime',
            timeMin = '2014-03-01T00:00:00-08:00',
            timeMax = '2014-03-31T00:00:00-08:00',
            pageToken = pageToken,
            ).execute()
        return events

    def requestEvents(self):
        allEvents = []
        events = self.fetchEvents()
        while True:
            for event in events['items']:
                allEvents.append(event)
            page_token = events.get('nextPageToken')
            if page_token:
                events = getEvents(page_token)
            else:
                break
        return allEvents

    # commands
    def cmd_calendar_show(self, args):
        return self.requestEvents()

    # commands
    def cmd_calendar_speak(self, args):
        return self.requestEvents()


descriptor = {
    'name' : 'gcal',
    'help' : 'Google Calendar integration',
    'command' : 'gcal',
    'mode' : PluginMode.MANAGED,
    'class' : GoogleCalendarPlugin,
    'detailsNames' : { }
}