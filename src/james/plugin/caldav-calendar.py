import os
import time

from datetime import datetime, timedelta, date
from caldav import DAVClient
from operator import itemgetter
import pytz
import re

from james.plugin import *


def create_birthday_message(summary):
    match = re.search(r"\((\d{4})\)", summary)  # Find (YYYY)
    if match:
        birth_year = int(match.group(1))
        current_year = datetime.now().year
        age = current_year - birth_year
        summary = summary.replace(f" ({birth_year})", "")
    return f"Happy {age}th birthday {summary}"


class CaldavCalendarPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CaldavCalendarPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('events', 'Show calendar entries from caldav', self.cmd_events_show)
        self.commands.create_subcommand('speak', 'Speak calendar entries from caldav', self.cmd_calendar_speak)
        self.commands.create_subcommand('all_calendars', 'List all available caldav calendars', self.cmd_calendars_list_all)
        self.commands.create_subcommand('active_calendars', 'List currently active caldav calendars', self.cmd_calendars_list_active)

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
        # self.core.add_timeout(0, self.request_events, False)
        self.core.add_timeout(0, self.request_events)
        now = datetime.now()
        seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        seconds_until_midnight: int = int(86400 - seconds_since_midnight) # a day has 86400 seconds
        seconds_until_next_quarter_day: int = int(seconds_until_midnight % 21600 + 30) # 21600 seconds is 1/4 day
            # adding 30 seconds just to be sure it's the next day at midnight
        self.logger.debug(f"CalDAV calendar was just fetched. Will fetch again in {seconds_until_next_quarter_day} seconds")
        self.core.add_timeout(seconds_until_next_quarter_day, self.update_automatically)

    def get_all_calendars(self):
        # Fetch calendars
        principal = self.client.principal()
        calendars = principal.calendars()
        self.logger.debug(f"Available CalDAV calendars: {', '.join([x.name for x in calendars])}")
        return calendars

    def get_current_calendars(self):
        wanted_calendars = []
        persons_here = self.core.get_present_users_here()
        for person in self.core.config['persons'].keys():
            if person in persons_here:
                if 'caldavs' in self.core.config['persons'][person].keys():
                    self.logger.debug(f"Person {person} is here, fetching calendar entries")
                    wanted_calendars += self.core.config['persons'][person]['caldavs']
            else:
                self.logger.debug(f"Person {person} is not here, not fetching calendar entries")
        self.logger.debug(f"Wanted CalDAV calendars: {', '.join(wanted_calendars)}")
        selected_calendars = [cal for cal in self.get_all_calendars() if cal.name in wanted_calendars]
        self.logger.debug(f"Selected calendar: {', '.join([x.name for x in selected_calendars])}")
        return list(set(selected_calendars))

    def request_events(self, show=True):
        self.logger.debug("requestEvents from caldav calendar")
        if time.time() < (self.event_cache_timestamp + self.event_cache_timeout):
            self.logger.debug("Cache is still valid, answering with the cache data")
        else:
            self.logger.debug("Cache is no longer valid, requesting events")
            today = datetime.now(self.timezone).date()
            midnight_today = self.timezone.localize(datetime.combine(today, datetime.min.time()))
            last_second_tomorrow = self.timezone.localize(datetime.combine(today + timedelta(days=1), datetime.max.time()))

            # today = datetime.now(pytz.utc).date()
            # midnight_today_utc = pytz.utc.localize(datetime.combine(today, datetime.min.time()))
            # last_second_tomorrow_utc = pytz.utc.localize(datetime.combine(today + timedelta(days=1), datetime.max.time()))

            events = []
            for calendar in self.get_current_calendars():
                self.logger.debug(f"Fetching calendar: {calendar.name}")
                results = calendar.search(start=midnight_today, end=last_second_tomorrow, event=True)
                # results = calendar.search(start=midnight_today_utc, end=last_second_tomorrow_utc, event=True)
                self.logger.debug(f"Found {len(results)} results:")

                for event in results:
                    self.eventsFetched += 1
                    ical = event.icalendar_component
                    self.logger.debug(f"Event: {event}")
                    for comp in ical.walk():
                        if comp.name != "VEVENT":
                            continue

                        summary = comp.get("SUMMARY", "No Title")
                        if summary in self.config['ignored_events']:
                            continue
                        # replace birthday emoji with ascii
                        summary = summary.replace("🎂 ", "")
                        new_event = {'summary': summary,
                                     'start': comp.get("DTSTART").dt,
                                     'start_str': comp.get("DTSTART").dt.isoformat()}

                        if "DTEND" in comp.keys():
                            new_event['end'] = comp["DTEND"].dt

                        events.append(new_event)

            # Sort events by start date and store to cache
            self.event_cache = []
            for event in sorted(events, key=itemgetter('start_str')):
                self.event_cache.append(event)
            self.event_cache_timestamp = time.time()

        return_list = []
        event_words = []
        no_alarm_clock_active = False
        events_today = []
        today = datetime.now(self.timezone).date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        now = datetime.now(self.timezone)

        for event in self.event_cache:
            self.logger.debug(f"Analyzing event {event['summary']} which starts at {event['start_str']}")

            start = event['start']
            end = event['end'] if 'end' in event.keys() else None  # Some events may not have an end time

            return_string = False
            happening_today = False
            happening_tomorrow = False
            birthday = False

            # Convert start and end times for comparison
            if isinstance(start, date) and not isinstance(start, datetime):
                start_date = start  # All-day events
                end_date = end if isinstance(end, date) else (end.date() if end else start_date)

                if start.year < today.year and start.month == today.month and start.day == today.day:
                    self.logger.debug(f"Most likely a birthday: {event['summary']}")
                    happening_today = True
                    birthday = True
                elif start_date == today:
                    self.logger.debug(f"Today's event: {event['summary']}")
                    happening_today = True
                    return_string = "Today "
                elif start_date == tomorrow:
                    self.logger.debug(f"Tomorrow's event: {event['summary']}")
                    happening_tomorrow = True
                    return_string = "Tomorrow "
                elif start_date == yesterday and end_date >= today:
                    self.logger.debug(f"Ongoing event from yesterday: {event['summary']}")
                    happening_today = True
                    return_string = "Still "
                else:
                    self.logger.debug(f"Ignoring future event: {event['summary']}")

            else:
                start_date = start.date()  # Timed events
                end_date = end.date() if end else start_date  # Convert end time if available

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
                self.logger.debug(f"Ignoring event because of ignored_events: {event}")
                continue

            # normal event (with start and end time):
            elif isinstance(start, datetime):
                # always make sure `now` and `start/end` are timezone-aware in same tz
                if start.tzinfo is None:
                    start = self.timezone.localize(start)
                else:
                    start = start.astimezone(self.timezone)

                if end and end.tzinfo is None:
                    end = self.timezone.localize(end)
                elif end:
                    end = end.astimezone(self.timezone)

                now = datetime.now(self.timezone)

                if happening_tomorrow:
                    return_string = f"Tomorrow at {start.strftime('%H:%M')}: "
                else:
                    # we collect all words to check for the no_alarm_clock_active override at the end
                    event_words.extend(event['summary'].split())
                    events_today.append(event['summary'])

                    if start < now < end:
                        return_string = f"Until {end.strftime('%H:%M')} today: "

                    elif now < end:
                        return_string = f"Today at {start.strftime('%H:%M')}: "

            if birthday:
                return_list.append(create_birthday_message(event['summary']))
            elif return_string:
                return_string += event['summary']
                return_list.append(return_string)

        for word in event_words:
            if word.lower() in [x.lower() for x in self.config['no_alarm_clock_override']]:
                self.logger.info("Found a event which overrides no_alarm_clock: %s" % word)
                no_alarm_clock_active = False

        self.logger.debug("There are %s events in the cache." % len(return_list))

        self.core.no_alarm_clock_update(no_alarm_clock_active, 'caldav')

        self.core.events_today_update(events_today, 'caldav')

        if len(return_list):
            self.logger.debug("Returning %s events" % len(return_list))
            if show:
                return return_list
        return []

    # commands
    def cmd_events_show(self, args):
        return self.request_events()

    def cmd_calendar_speak(self, args):
        events = self.request_events()
        if len(events):
            self.send_command(['espeak', 'say', '. '.join(events)])

    def cmd_calendars_list_all(self, args):
        try:
            ret_list = ['All available CalDAV calendars:']
            for calendar in self.get_all_calendars():
                ret_list.append(calendar.name)
            return ret_list
        except Exception as e:
            print(e)

    def cmd_calendars_list_active(self, args):
        try:
            ret_list = ['Currently active CalDAV calendars:']
            for calendar in self.get_current_calendars():
                ret_list.append(calendar.name)
            return ret_list
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
    'name': 'caldav',
    'help_text': 'CalDAV Calendar integration',
    'command': 'caldav',
    'mode': PluginMode.MANAGED,
    'class': CaldavCalendarPlugin,
    'detailsNames': {'eventFetches': "Amount of event fetches",
                     'eventsFetched': "Amount of events fetched"}
}
