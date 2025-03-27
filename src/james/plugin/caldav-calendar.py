import os
import time

from datetime import datetime, timedelta
import pytz
from caldav import DAVClient

from james.plugin import *


class CaldavCalendarPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CaldavCalendarPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('show', 'Show calendar entries from caldav', self.cmd_calendar_show)
        self.commands.create_subcommand('speak', 'Speak calendar entries from caldav', self.cmd_calendar_speak)
        self.commands.create_subcommand('list', 'List all caldav calendars', self.cmd_calendars_list)

        self.timezone = pytz.timezone(self.core.config['core']['timezone'])

        self.eventFetches = 0
        self.eventsFetched = 0
        self.load_state('eventFetches', 0)
        self.load_state('eventsFetched', 0)

        self.client = DAVClient(
            url=self.config['server'],
            username=self.config['username'],
            password=self.config['password'],
        )

        self.event_cache = []
        self.event_cache_timestamp = 0
        if 'cache_timeout' in self.config.keys():
            self.event_cache_timeout = self.config['cache_timeout']
        else:
            self.event_cache_timeout = 10

        self.core.add_timeout(10, self.update_automatically)

    # internal commands
    def update_automatically(self):
        self.core.add_timeout(0, self.request_events, False)
        now = datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        seconds_until_midnight: int = int(86400 - seconds_since_midnight) # a day has 86400 seconds
        seconds_until_next_quarter_day: int = int(seconds_until_midnight % 21600 + 30) # 21600 seconds is 1/4 day
            # adding 30 seconds just to be sure it's the next day at midnight
        self.logger.debug(f"CalDAV calendar was just fetched. Will fetch again in {seconds_until_next_quarter_day} seconds")
        self.core.add_timeout(seconds_until_next_quarter_day, self.update_automatically)

    def fetch_events(self, calendar_name):
        timezone = pytz.timezone("Europe/Zurich")
        today = datetime.now(timezone).date()
        midnight_today = timezone.localize(datetime.combine(today, datetime.min.time()))
        last_second_tomorrow = timezone.localize(datetime.combine(today + timedelta(days=1), datetime.max.time()))
        midnight_today_utc = midnight_today.astimezone(pytz.utc)
        last_second_tomorrow_utc = last_second_tomorrow.astimezone(pytz.utc)

        midnight_today_utc_rfc3339 = midnight_today_utc.isoformat()
        last_second_tomorrow_utc_rfc3339 = last_second_tomorrow_utc.isoformat()

        # Fetch calendars
        principal = self.client.principal()
        calendars = principal.calendars()

        # Filter calendars
        self.logger.debug(f"Available CalDAV calendars: {', '.join([x.name for x in calendars])}")
        selected_calendars = [cal for cal in calendars if cal.name == calendar_name]
        self.logger.debug(f"Selected calendar: f{", ".join(selected_calendars)}")

        events = []
        for calendar in selected_calendars:
            self.logger.debug(f"Fetching calendar: {calendar.name}")
            results = calendar.search(
                start=midnight_today_utc_rfc3339, end=last_second_tomorrow_utc_rfc3339 + timedelta(days=30), event=True
            )
            self.logger.debug(f"Found {len(results)} results: {results}")

            for event in results:
                ical = event.icalendar_component
                self.logger.debug(f"Event: {event}")
                for comp in ical.walk():
                    if comp.name != "VEVENT":
                        continue

                    summary = comp.get("SUMMARY", "No Title")
                    if summary in self.ignored:
                        continue
                    # replace birthday emoji with ascii
                    summary = summary.replace("🎂", "[_i_]")

                    start = comp.get("DTSTART").dt
                    if isinstance(start, datetime):  # Ensure it's datetime, not date
                        start_str = start.isoformat()
                    else:
                        start = datetime.combine(start, datetime.min.time())
                        start_str = start.isoformat()

                    events.append((start_str, summary))

        # Sort events by start date
        return events.sort()

    def get_calendar_names(self):
        person_calendar_name = {}
        for person in self.core.get_present_users_here():
            self.logger.debug("Found person: %s" % person)
            person_calendar_name[person] = []
            try:
                for calendar_name in self.core.config['persons'][person]['caldavs']:
                    person_calendar_name[person].append(calendar_name)
                    self.logger.debug("Found calendar: %s" % calendar_name)
            except KeyError:
                pass
        self.logger.debug("get_calendar_names returns: %s" % person_calendar_name)
        return person_calendar_name

    def request_events(self, show=True):
        self.logger.debug("requestEvents from caldav calendar")
        if time.time() < (self.event_cache_timestamp + self.event_cache_timeout):
            self.logger.debug("Cache is still valid, answering with the cache data")

        else:
            self.logger.debug("Cache is invalid, fetching new data")
            self.event_cache = []
            person_calendar_names = self.get_calendar_names()

            for person in person_calendar_names.keys():
                self.logger.debug(f"Fetching calendars for person: {person}")
                for calendar in person_calendar_names[person]:
                    self.logger.debug(f"Fetching calendar: {calendar}")
                    calendar_events = []
                    events = self.fetch_events(calendar)
                    if not events:
                        continue

                    while True:
                        for event in events:
                            calendar_events.append(event)
                            self.event_cache.append((person, event))

                    self.logger.debug(f"Fetched %s events for calendar {(len(calendar_events), calendar)}:")
                    for event in calendar_events:
                        self.logger.debug(event)
                else:
                    self.logger.debug(f"No calendars for: {person}")

                self.event_cache_timestamp = time.time()

        return_list = []
        event_words = []
        no_alarm_clock_active = False
        events_today = []
        for (person, event) in self.event_cache:
            self.logger.debug(f"Analyzing event for {person}: {event['summary']}")
            self.eventsFetched += 1
            return_string = False
            happening_today = False
            now = datetime.now()

            # TODO Start here

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

                # we collect all words to check for the no_alarm_clock_active override at the end.
                if happening_today:
                    event_words.extend(event['summary'].split())
                    events_today.append(event['summary'])

            # check there is a "don't wake up" event present in caldav calendar
            for no_alarm_clock_entry in [x.lower() for x in self.config['no_alarm_clock']]:
                if no_alarm_clock_entry in event['summary'].lower() and happening_today:
                    self.logger.info(f"Found the event <{event['summary'].lower()}> which activates "
                                     f"no_alarm_clock because of <{no_alarm_clock_entry}>")
                    no_alarm_clock_active = True

            # ignore ignored_events from config
            if event['summary'].lower() in [x.lower() for x in self.config['ignored_events']]:
                self.logger.debug("Ignoring event because of ignored_events: %s" % event)
                continue

            # normal event (with start and end time):
            elif 'dateTime' in list(event['start'].keys()):
                eventTimeStart = datetime.strptime(event['start']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                eventTimeEnd = datetime.strptime(event['end']['dateTime'][:-6], '%Y-%m-%dT%H:%M:%S')
                if eventTimeStart.day > datetime.now().day:
                    return_string = "Tomorrow at %02d:%02d: " % (eventTimeStart.hour, eventTimeStart.minute)
                else:

                    # we collect all words to check for the no_alarm_clock_active override at the end
                    event_words.extend(event['summary'].split())
                    events_today.append(event['summary'])

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

        self.core.events_today_update(events_today, 'gcal')

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
            retList = ['CalDAV calendars:', 'ID: Name']
            calendars = self.service.calendarList().list().execute()
            for cal in calendars['items']:
                if cal['kind'] == 'calendar#calendarListEntry':
                    retList.append(cal['id'] + ": " + cal['summary'])
            return retList
        except Exception as e:
            print(e)

    # internal
    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("CalDAV calendar processing presence event")
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
    'help_text': 'CalDAV Calendar integration',
    'command': 'gcal',
    'mode': PluginMode.MANAGED,
    'class': CaldavCalendarPlugin,
    'detailsNames': {'eventFetches': "Amount of event fetches",
                     'eventsFetched': "Amount of events fetched"}
}
