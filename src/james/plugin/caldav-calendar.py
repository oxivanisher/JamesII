import os
import time

from datetime import datetime, timedelta, date
from dateutil.rrule import rrulestr
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
        def ensure_aware(dt_obj, timezone):
            if isinstance(dt_obj, datetime):
                return timezone.localize(dt_obj) if dt_obj.tzinfo is None else dt_obj.astimezone(timezone)
            elif isinstance(dt_obj, date):
                return timezone.localize(datetime.combine(dt_obj, datetime.min.time()))
            else:
                raise ValueError("Unsupported date/time object")

        self.logger.debug("requestEvents from caldav calendar")

        if time.time() < (self.event_cache_timestamp + self.event_cache_timeout):
            self.logger.debug("Cache is still valid, answering with the cache data")
        else:
            self.logger.debug("Cache is no longer valid, requesting events")
            today = datetime.now(self.timezone).date()
            start_range = self.timezone.localize(datetime.combine(today, datetime.min.time()))
            end_range = self.timezone.localize(datetime.combine(today + timedelta(days=1), datetime.max.time()))

            events = []
            for calendar in self.get_current_calendars():
                self.logger.debug(f"Fetching calendar: {calendar.name}")
                results = calendar.search(start=start_range, end=end_range, event=True, expand=True)

                self.logger.debug(f"Found {len(results)} results:")
                for event in results:
                    self.eventsFetched += 1
                    ical = event.icalendar_component
                    self.logger.debug(f"Event object: {event}")
                    for comp in ical.walk():
                        if comp.name != "VEVENT":
                            continue

                        summary = comp.get("SUMMARY", "No Title").replace("🎂 ", "")
                        if summary in self.config['ignored_events']:
                            continue

                        dtstart = comp.get("RECURRENCE-ID", comp.get("DTSTART"))
                        dtend = comp.get("DTEND") if "DTEND" in comp else None

                        if not dtstart:
                            self.logger.warning(f"Skipping event without DTSTART: {summary}")
                            continue

                        self.logger.debug(
                            f"Parsed VEVENT: DTSTART={dtstart.dt} (type={type(dtstart.dt)}), SUMMARY={summary}")

                        events.append({
                            'summary': summary,
                            'start': dtstart.dt,
                            'end': dtend.dt if dtend else None
                        })

            self.event_cache = events
            self.event_cache_timestamp = time.time()

        return_list = []
        event_words = []
        no_alarm_clock_active = False
        events_today = []

        today = datetime.now(self.timezone).date()
        tomorrow = today + timedelta(days=1)
        now = datetime.now(self.timezone)

        for event in self.event_cache:
            summary = event['summary']
            start = event['start']
            end = event.get('end')
            return_string = None
            happening_today = False
            birthday = False

            self.logger.debug(f"Analyzing event {summary} with raw start={start}")

            # All-day event handling
            if isinstance(start, date) and not isinstance(start, datetime):
                start_date = start
                end_date = end if isinstance(end, date) else (end.date() if end else start_date)

                if start.year < today.year and start.month == today.month and start.day == today.day:
                    self.logger.debug(f"Birthday detected: {summary}")
                    happening_today = True
                    birthday = True
                elif start_date <= today < end_date:
                    self.logger.debug(f"Active all-day event: {summary}")
                    happening_today = True
                    return_string = "Today "
                elif start_date == tomorrow:
                    self.logger.debug(f"Tomorrow's all-day event: {summary}")
                    return_string = "Tomorrow "
                elif start_date < today and end_date > today:
                    self.logger.debug(f"Ongoing all-day event from earlier: {summary}")
                    happening_today = True
                    return_string = "Still "
                else:
                    self.logger.debug(f"Ignoring all-day event: {summary}")

                if happening_today:
                    event_words.extend(summary.split())
                    events_today.append(summary)

                for no_alarm_clock_entry in [x.lower() for x in self.config['no_alarm_clock']]:
                    if no_alarm_clock_entry in summary.lower():
                        if happening_today:
                            self.logger.info(f"No-alarm clock triggered by all-day event: {summary}")
                            no_alarm_clock_active = True

                start_dt = ensure_aware(start_date, self.timezone)

                if birthday:
                    return_list.append({'text': create_birthday_message(summary), 'start': start_dt})
                elif return_string:
                    return_list.append({'text': return_string + summary, 'start': start_dt})

                continue

            # Timed event handling
            start = ensure_aware(start, self.timezone)
            if end:
                end = ensure_aware(end, self.timezone)

            if start.date() == now.date():
                event_words.extend(summary.split())
                events_today.append(summary)

                if start < now < end:
                    self.logger.debug(f"Event ongoing: {summary}")
                    return_string = f"Until {end.strftime('%H:%M')} today: "
                elif now < end:
                    self.logger.debug(f"Upcoming today: {summary}")
                    return_string = f"Today at {start.strftime('%H:%M')}: "
                else:
                    self.logger.warning(f"Past event still in list? {summary}")
            else:
                self.logger.debug(f"Future event: {summary}")
                return_string = f"Tomorrow at {start.strftime('%H:%M')}: "

            for no_alarm_clock_entry in [x.lower() for x in self.config['no_alarm_clock']]:
                if no_alarm_clock_entry in summary.lower() and start.date() == today:
                    self.logger.info(f"No-alarm clock triggered by timed event: {summary}")
                    no_alarm_clock_active = True

            if summary.lower() in [x.lower() for x in self.config['ignored_events']]:
                self.logger.debug(f"Ignored via config: {summary}")
                continue

            if return_string:
                return_list.append({'text': return_string + summary, 'start': start})

        for word in event_words:
            if word.lower() in [x.lower() for x in self.config['no_alarm_clock_override']]:
                self.logger.info(f"Found override word '{word}', disabling no-alarm mode.")
                no_alarm_clock_active = False

        self.logger.debug(f"{len(return_list)} events prepared for output.")

        self.core.no_alarm_clock_update(no_alarm_clock_active, 'caldav')
        self.core.events_today_update(events_today, 'caldav')

        if show and return_list:
            sorted_list = sorted(return_list, key=lambda e: e['start'])

            for e in sorted_list:
                self.logger.debug(f"Sorted event: {e['start']} -> {e['text']}")

            return [e['text'] for e in sorted_list]

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
