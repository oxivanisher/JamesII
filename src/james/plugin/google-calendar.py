import os
import time

from datetime import datetime, timedelta
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from james.plugin import *


class GoogleCalendarPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(GoogleCalendarPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('show', 'Show calendar entries from google', self.cmd_calendar_show)
        self.commands.create_subcommand('speak', 'Speak calendar entries from google', self.cmd_calendar_speak)
        self.commands.create_subcommand('list', 'List all google calendars', self.cmd_calendars_list)

        self.timezone = pytz.timezone(self.core.config['core']['timezone'])

        self.eventFetches = 0
        self.eventsFetched = 0
        self.load_state('eventFetches', 0)
        self.load_state('eventsFetched', 0)

        self.event_cache = []
        self.event_cache_timestamp = 0
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
        self.core.add_timeout(0, self.request_events, False)
        now = datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        seconds_until_midnight = int(
            86400 - seconds_since_midnight + 30)  # adding 30 seconds just to be sure it's the next day
        self.logger.debug("Google calendar was just fetched. Will fetch again in %s seconds" % seconds_until_midnight)
        self.core.add_timeout(seconds_until_midnight, self.update_after_midnight)

    def fetch_events(self, calendar_id, page_token=None):
        timezone = pytz.timezone("Europe/Zurich")
        today = datetime.now(timezone).date()
        midnight_today = timezone.localize(datetime.combine(today, datetime.min.time()))
        last_second_tomorrow = timezone.localize(datetime.combine(today + timedelta(days=1), datetime.max.time()))
        midnight_today_utc = midnight_today.astimezone(pytz.utc)
        last_second_tomorrow_utc = last_second_tomorrow.astimezone(pytz.utc)

        midnight_today_utc_rfc3339 = midnight_today_utc.isoformat()
        last_second_tomorrow_utc_rfc3339 = last_second_tomorrow_utc.isoformat()

        self.logger.debug("fetching events from <%s> to <%s>" % (midnight_today_utc_rfc3339,
                                                                 last_second_tomorrow_utc_rfc3339))

        try:
            events = self.service.events().list(calendarId=calendar_id,
                                                maxResults=100,
                                                singleEvents=True,
                                                timeMin=midnight_today_utc_rfc3339,
                                                timeMax=last_second_tomorrow_utc_rfc3339,
                                                orderBy='startTime',
                                                pageToken=page_token).execute()
            self.eventFetches += 1
        except Exception as e:
            if e == '':
                self.logger.error("Event fetching error, probably oauth2 session refresh")
            else:
                self.logger.error("Event fetching error: %s" % e)
            return False

        self.logger.debug("fetch_events returns: %s" % events)
        return events

    def get_calendar_ids(self):
        person_client_ids = {}
        for person in self.core.get_present_users_here():
            self.logger.debug("Found person: %s" % person)
            person_client_ids[person] = []
            try:
                for calendarId in self.core.config['persons'][person]['gcals']:
                    person_client_ids[person].append(calendarId)
                    self.logger.debug("Found calendar: %s" % calendarId)
            except KeyError:
                pass
        self.logger.debug("get_calendar_ids returns: %s" % person_client_ids)
        return person_client_ids

    def request_events(self, show=True):
        self.logger.debug("requestEvents from google calendar")
        if time.time() < (self.event_cache_timestamp + self.event_cache_timeout):
            self.logger.debug("Cache is still valid, answering with the cache data")

        else:
            self.logger.debug("Cache is invalid, fetching new data")
            self.event_cache = []
            person_client_ids = self.get_calendar_ids()

            for person in person_client_ids.keys():
                self.logger.debug("Fetching calendars for person: %s" % person)
                for calendar in person_client_ids[person]:
                    self.logger.debug("Fetching calendar: %s" % calendar)
                    calendar_events = []
                    events = self.fetch_events(calendar)
                    if not events:
                        continue

                    while True:
                        for event in events['items']:
                            calendar_events.append(event)
                            self.event_cache.append((person, event))
                        page_token = events.get('nextPageToken')
                        if page_token:
                            events = self.fetch_events(calendar, page_token)
                        else:
                            break

                    self.logger.debug("Fetched %s events for calendar %s:" % (len(calendar_events), calendar))
                    for event in calendar_events:
                        self.logger.debug(event)
                else:
                    self.logger.debug("No calendars for: %s" % person)

                self.event_cache_timestamp = time.time()

        return_list = []
        event_words = []
        no_alarm_clock_active = False
        for (person, event) in self.event_cache:
            self.logger.debug("Analyzing event for %s: %s" % (person, event['summary']))
            self.eventsFetched += 1
            return_string = False
            happening_today = False
            now = datetime.now()

            # whole day event:
            if 'date' in list(event['start'].keys()):
                if event['start']['date'] == datetime.now(self.timezone).strftime('%Y-%m-%d'):
                    happening_today = True
                    return_string = "Today "
                elif event['start']['date'] < datetime.now(self.timezone).strftime('%Y-%m-%d'):
                    happening_today = True
                    return_string = "Still "
                else:
                    return_string = "Tomorrow "

            # check there is a "don't wake up" event present in google calendar
            if event['summary'].lower() in [x.lower() for x in self.config['no_alarm_clock']]:
                if happening_today:
                    self.logger.info("Found a event which activates no_alarm_clock: %s" % event['summary'])
                    no_alarm_clock_active = True

            # we collect all words to check for the no_alarm_clock_active override at the end
            if happening_today:
                event_words.extend(event['summary'].split())

            # ignore ignored_events from config
            if event['summary'].lower() in [x.lower() for x in self.config['ignored_events']]:
                self.logger.debug("Ignoring event because of ignored_events: %s" % event)
                continue

            # normal event:
            elif 'dateTime' in list(event['start'].keys()):
                eventTimeStart = datetime.strptime(event['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                eventTimeEnd = datetime.strptime(event['end']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if eventTimeStart.day > datetime.now().day:
                    return_string = "Tomorrow at %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)
                else:

                    # we collect all words to check for the no_alarm_clock_active override at the end
                    event_words.extend(event['summary'].split())

                    if eventTimeStart < now < eventTimeEnd:
                        return_string = "Until %02d:%02d today: " % (eventTimeEnd.hour, eventTimeEnd.minute)
                    elif now < eventTimeStart:
                        return_string = "Today at %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)

            if return_string:
                if event['status'] == "tentative":
                    return_string += " possibly "
                    # evil is:
                return_string += event['summary']
                return_list.append(return_string)

        for word in event_words:
            if word.lower() in [x.lower() for x in self.config['no_alarm_clock_override']]:
                self.logger.info("Found a event which overrides no_alarm_clock: %s" % word)
                no_alarm_clock_active = False

        self.logger.debug("There are %s events in the cache." % len(return_list))

        self.core.no_alarm_clock_update(no_alarm_clock_active, 'gcal')

        if len(return_list):
            self.logger.debug("Returning %s events" % len(return_list))
            if show:
                return return_list
        return []

    # commands
    def cmd_calendar_show(self, args):
        # self.core.add_timeout(0, self.requestEvents, True)
        return self.request_events()

    def cmd_calendar_speak(self, args):
        events = self.request_events()
        if len(events):
            self.send_command(['espeak', 'say', '. '.join(events)])

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
    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("Google calendar processing presence event")
        if len(presence_now):
            self.event_cache_timestamp = 0
            self.core.add_timeout(1, self.request_events, False)
            self.core.add_timeout(2, self.cmd_calendar_speak, None)

    # status
    def return_status(self, verbose=False):
        ret = {'eventFetches': self.eventFetches, 'eventsFetched': self.eventsFetched}
        return ret


descriptor = {
    'name': 'gcal',
    'help_text': 'Google Calendar integration',
    'command': 'gcal',
    'mode': PluginMode.MANAGED,
    'class': GoogleCalendarPlugin,
    'detailsNames': {'eventFetches': "Amount of event fetches",
                     'eventsFetched': "Amount of events fetched"}
}
