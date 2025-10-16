import json
import threading
import time

from james.plugin import *

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


class MqttThread(PluginThread):
    """Background thread for MQTT client loop"""

    def work(self):
        self.logger.info("MQTT thread starting")
        loop_count = 0
        while not self.plugin.terminated:
            if self.plugin.mqtt_client:
                try:
                    # Run MQTT network loop
                    rc = self.plugin.mqtt_client.loop(timeout=1.0)
                    if rc != 0:
                        self.logger.warning(f"MQTT loop returned non-zero code: {rc}")

                    loop_count += 1
                    if loop_count % 60 == 0:  # Log every 60 iterations (roughly every minute)
                        connected_str = "connected" if self.plugin.mqtt_connected else "not connected"
                        self.logger.debug(f"MQTT thread alive, status: {connected_str}, loop iterations: {loop_count}")
                except Exception as e:
                    self.logger.error(f"MQTT loop error: {e}", exc_info=True)
                    time.sleep(1)
            else:
                self.logger.debug("MQTT client not initialized, waiting...")
                time.sleep(1)

        self.logger.info("MQTT thread terminating")


class MqttPlugin(Plugin):

    def __init__(self, core, descriptor):
        if not MQTT_AVAILABLE:
            raise Exception("paho-mqtt library not available. Install with: pip install paho-mqtt")

        super().__init__(core, descriptor)

        self.logger.debug("Initializing MQTT plugin...")

        # MQTT connection state
        self.mqtt_client = None
        self.mqtt_connected = False
        self.terminated = False
        self.mqtt_thread = None

        # Configuration with defaults
        self.mqtt_host = self.config.get('host', 'localhost')
        self.mqtt_port = self.config.get('port', 1883)
        self.mqtt_username = self.config.get('username', None)
        self.mqtt_password = self.config.get('password', None)
        self.mqtt_base_topic = self.config.get('base_topic', 'james2/')

        self.logger.debug(f"Config loaded - host: {self.mqtt_host}, port: {self.mqtt_port}, username: {self.mqtt_username}, base_topic: {self.mqtt_base_topic}")

        # Ensure base topic ends with /
        if not self.mqtt_base_topic.endswith('/'):
            self.mqtt_base_topic += '/'
            self.logger.debug(f"Added trailing slash to base_topic: {self.mqtt_base_topic}")

        # Retain configuration for published states
        self.retain_nodes = self.config.get('retain_nodes', True)
        self.retain_presence = self.config.get('retain_presence', True)
        self.retain_alarmclock = self.config.get('retain_alarmclock', True)
        self.retain_cron = self.config.get('retain_cron', True)
        self.retain_stations = self.config.get('retain_stations', True)
        self.retain_events = self.config.get('retain_events', False)

        self.logger.debug(f"Retain settings - nodes: {self.retain_nodes}, presence: {self.retain_presence}, alarmclock: {self.retain_alarmclock}, cron: {self.retain_cron}, stations: {self.retain_stations}, events: {self.retain_events}")

        # Topics
        self.topic_command = self.mqtt_base_topic + 'command'
        self.topic_nodes = self.mqtt_base_topic + 'state/nodes'
        self.topic_presence = self.mqtt_base_topic + 'state/presence'
        self.topic_alarmclock = self.mqtt_base_topic + 'state/alarmclock'
        self.topic_cron = self.mqtt_base_topic + 'state/cron'
        self.topic_stations = self.mqtt_base_topic + 'state/stations'
        self.topic_events = self.mqtt_base_topic + 'events'

        self.logger.debug(f"Topics configured: command={self.topic_command}, nodes={self.topic_nodes}, presence={self.topic_presence}, events={self.topic_events}")

        # State tracking for change detection
        self.last_nodes_state = None
        self.last_presence_state = None
        self.last_alarmclock_state = None
        self.last_cron_state = None
        self.last_stations_state = None

        # Update interval in seconds
        self.update_interval = self.config.get('update_interval', 30)

        self.logger.debug(f"Update interval: {self.update_interval}s")

        # Commands
        self.commands.create_subcommand('status', 'Show MQTT connection status', self.cmd_status)
        self.commands.create_subcommand('reconnect', 'Reconnect to MQTT broker', self.cmd_reconnect)
        self.commands.create_subcommand('publish_all', 'Publish all states immediately', self.cmd_publish_all)
        self.commands.create_subcommand('send', 'Send custom event to MQTT (mqtt send topic payload...)', self.cmd_send)

        self.logger.info(f"MQTT plugin initialized - broker: {self.mqtt_host}:{self.mqtt_port}, base_topic: {self.mqtt_base_topic}")

    def start(self):
        """Start the MQTT connection"""
        self.logger.info("Starting MQTT plugin...")
        try:
            self.connect_mqtt()
            self.logger.debug("MQTT connection initiated")
        except Exception as e:
            self.logger.error(f"Failed to start MQTT connection: {e}", exc_info=True)
            return

        # Start periodic state publishing
        self.logger.debug("Scheduling periodic state updates")
        self.core.add_timeout(5, self.periodic_state_update)

    def terminate(self):
        """Clean shutdown of MQTT connection"""
        self.logger.info("Terminating MQTT plugin...")
        self.terminated = True

        if self.mqtt_client and self.mqtt_connected:
            try:
                self.logger.debug("Disconnecting from MQTT broker...")
                self.mqtt_client.disconnect()
                self.logger.info("MQTT client disconnected")
            except Exception as e:
                self.logger.error(f"Error disconnecting MQTT: {e}")

        # Wait for thread to exit
        if self.mqtt_thread:
            self.logger.debug("Waiting for MQTT thread to exit...")
            self.wait_for_threads([self.mqtt_thread])
            self.logger.debug("MQTT thread exited")

    def connect_mqtt(self):
        """Establish connection to MQTT broker"""
        try:
            client_id = f"james2_{self.core.hostname}_{self.name}"
            self.logger.debug(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Set callbacks
            self.logger.debug("Setting MQTT callbacks")
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message

            # Set authentication if provided
            if self.mqtt_username and self.mqtt_password:
                self.logger.debug(f"Setting MQTT authentication for user: {self.mqtt_username}")
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            else:
                self.logger.debug("No MQTT authentication configured (anonymous connection)")

            # Connect
            self.logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.logger.debug(f"Connection parameters - host: {self.mqtt_host}, port: {self.mqtt_port}, keepalive: 60")

            try:
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
                self.logger.debug("MQTT connect() called successfully")
            except Exception as conn_err:
                self.logger.error(f"MQTT connect() failed: {conn_err}", exc_info=True)
                raise

            # Start background thread for MQTT loop
            self.logger.debug("Starting MQTT background thread")
            self.mqtt_thread = MqttThread(self)
            self.mqtt_thread.start()
            self.worker_threads.append(self.mqtt_thread)
            self.logger.debug(f"MQTT thread started: {self.mqtt_thread.name}")

        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}", exc_info=True)
            raise

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        self.logger.debug(f"MQTT on_connect callback triggered - rc: {rc}, flags: {flags}")

        # MQTT return codes
        rc_messages = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }

        if rc == 0:
            self.mqtt_connected = True
            self.logger.info(f"Successfully connected to MQTT broker ({rc_messages.get(rc, 'Unknown')})")
            self.logger.debug(f"Connection flags: {flags}")

            # Subscribe to command topic
            self.logger.debug(f"Subscribing to command topic: {self.topic_command}")
            result, mid = client.subscribe(self.topic_command)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Subscribed to {self.topic_command} (mid: {mid})")
            else:
                self.logger.error(f"Failed to subscribe to {self.topic_command}, result code: {result}")

            # Publish initial states
            self.logger.debug("Scheduling initial state publish in 1 second")
            self.core.add_timeout(1, self.publish_all_states)
        else:
            error_msg = rc_messages.get(rc, f"Unknown error code: {rc}")
            self.logger.error(f"Failed to connect to MQTT broker - {error_msg} (rc={rc})")
            if rc == 4:
                self.logger.error("Check your MQTT username and password configuration")
            elif rc == 5:
                self.logger.error("Client is not authorized - check broker ACL configuration")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.logger.debug(f"MQTT on_disconnect callback triggered - rc: {rc}")
        self.mqtt_connected = False

        disconnect_reasons = {
            0: "Clean disconnect",
            1: "Unexpected disconnect - protocol error",
            7: "Connection lost"
        }

        if rc != 0:
            reason = disconnect_reasons.get(rc, f"Unknown reason (code: {rc})")
            self.logger.warning(f"Unexpected MQTT disconnection - {reason}, will auto-reconnect")
        else:
            self.logger.info("MQTT disconnected cleanly")

    def on_mqtt_message(self, client, userdata, msg):
        """Callback when MQTT message received"""
        self.logger.debug(f"MQTT message received - topic: {msg.topic}, qos: {msg.qos}, retain: {msg.retain}")
        try:
            payload = msg.payload.decode('utf-8')
            self.logger.info(f"MQTT command received on {msg.topic}: {payload}")

            # Parse command and send to James
            command_args = payload.split()
            if command_args:
                self.logger.debug(f"Scheduling command execution: {command_args}")
                self.core.add_timeout(0, self.send_command, command_args)
            else:
                self.logger.warning("Received empty command payload")
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    def periodic_state_update(self):
        """Periodically publish state updates"""
        if not self.terminated and self.mqtt_connected:
            self.logger.debug(f"Periodic state update triggered (interval: {self.update_interval}s)")
            self.publish_all_states()
            self.core.add_timeout(self.update_interval, self.periodic_state_update)
        elif self.terminated:
            self.logger.debug("Skipping periodic update - plugin is terminating")
        elif not self.mqtt_connected:
            self.logger.debug("Skipping periodic update - MQTT not connected, will retry")
            self.core.add_timeout(self.update_interval, self.periodic_state_update)

    def publish_all_states(self, force=False):
        """Publish all state topics"""
        if not self.mqtt_connected:
            self.logger.debug("Skipping state publish - MQTT not connected")
            return

        self.logger.debug(f"Publishing all states (force={force})")
        self.publish_nodes_state(force)
        self.publish_presence_state(force)
        self.publish_alarmclock_state(force)
        self.publish_cron_state(force)
        self.publish_stations_state(force)
        self.logger.debug("All states published")

    def publish_nodes_state(self, force=False):
        """Publish nodes online state"""
        try:
            # Build list of online nodes
            nodes_dict = {}
            for uuid in self.core.nodes_online:
                hostname = self.core.nodes_online[uuid]
                if hostname not in nodes_dict:
                    nodes_dict[hostname] = []
                nodes_dict[hostname].append(uuid)

            nodes_list = []
            for hostname in sorted(nodes_dict):
                nodes_list.append({
                    'hostname': hostname,
                    'instances': len(nodes_dict[hostname]),
                    'uuids': nodes_dict[hostname]
                })

            state = {
                'nodes': nodes_list,
                'total_nodes': len(nodes_list),
                'total_instances': len(self.core.nodes_online),
                'timestamp': int(time.time())
            }

            state_json = json.dumps(state)

            # Only publish if changed or forced
            if force or state_json != self.last_nodes_state:
                self.logger.debug(f"Publishing to {self.topic_nodes} (retain={self.retain_nodes})")
                result = self.mqtt_client.publish(self.topic_nodes, state_json, retain=self.retain_nodes)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.last_nodes_state = state_json
                    self.logger.debug(f"Published nodes state: {len(nodes_list)} nodes online (mid: {result.mid})")
                else:
                    self.logger.error(f"Failed to publish nodes state, rc: {result.rc}")
            else:
                self.logger.debug("Nodes state unchanged, skipping publish")

        except Exception as e:
            self.logger.error(f"Error publishing nodes state: {e}", exc_info=True)

    def publish_presence_state(self, force=False):
        """Publish presence state"""
        try:
            # Get all present users by location
            presence_by_location = {}

            for presence in self.core.presences.presences:
                location = presence.location
                if location not in presence_by_location:
                    presence_by_location[location] = {
                        'users': [],
                        'sources': []
                    }

                for user in presence.users:
                    if user not in presence_by_location[location]['users']:
                        presence_by_location[location]['users'].append(user)

                source_info = f"{presence.plugin}@{presence.host}"
                if source_info not in presence_by_location[location]['sources']:
                    presence_by_location[location]['sources'].append(source_info)

            # Build presence state
            locations = []
            for location, data in presence_by_location.items():
                locations.append({
                    'location': location,
                    'users': sorted(data['users']),
                    'count': len(data['users']),
                    'sources': data['sources']
                })

            # Check if anybody is home (at this node's location)
            users_here = self.core.get_present_users_here()

            state = {
                'somebody_home': bool(users_here),
                'users_here': users_here,
                'this_location': self.core.location,
                'all_locations': locations,
                'timestamp': int(time.time())
            }

            state_json = json.dumps(state)

            # Only publish if changed or forced
            if force or state_json != self.last_presence_state:
                self.logger.debug(f"Publishing to {self.topic_presence} (retain={self.retain_presence})")
                result = self.mqtt_client.publish(self.topic_presence, state_json, retain=self.retain_presence)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.last_presence_state = state_json
                    self.logger.debug(f"Published presence state: {len(users_here)} users at {self.core.location} (mid: {result.mid})")
                else:
                    self.logger.error(f"Failed to publish presence state, rc: {result.rc}")
            else:
                self.logger.debug("Presence state unchanged, skipping publish")

        except Exception as e:
            self.logger.error(f"Error publishing presence state: {e}", exc_info=True)

    def publish_alarmclock_state(self, force=False):
        """Publish alarm clock status"""
        try:
            # Only master node has alarm clock state
            if not self.core.master:
                return

            alarmclock_disabled = self.core.check_no_alarm_clock()

            # Get details about which plugins are disabling alarm
            disabling_plugins = []
            for plugin_name, is_disabling in self.core.no_alarm_clock_data.items():
                if is_disabling:
                    disabling_plugins.append(plugin_name)

            state = {
                'enabled': not alarmclock_disabled,
                'disabled': alarmclock_disabled,
                'disabling_plugins': disabling_plugins,
                'timestamp': int(time.time())
            }

            state_json = json.dumps(state)

            # Only publish if changed or forced
            if force or state_json != self.last_alarmclock_state:
                self.mqtt_client.publish(self.topic_alarmclock, state_json, retain=self.retain_alarmclock)
                self.last_alarmclock_state = state_json
                status_text = "disabled" if alarmclock_disabled else "enabled"
                self.logger.debug(f"Published alarmclock state: {status_text}")

        except Exception as e:
            self.logger.error(f"Error publishing alarmclock state: {e}")

    def publish_cron_state(self, force=False):
        """Publish cron/timer status (mcp show equivalent)"""
        try:
            # Check if timer plugin is available
            timer_plugin = None
            for plugin in self.core.plugins:
                if plugin.command == 'mcp':
                    timer_plugin = plugin
                    break

            if not timer_plugin:
                self.logger.debug("Timer plugin not available, skipping cron state")
                return

            # Get timed commands
            timed_commands = []
            for (timestamp, command) in timer_plugin.saved_commands:
                timed_commands.append({
                    'timestamp': timestamp,
                    'time_str': self.utils.get_nice_age(timestamp),
                    'command': ' '.join(command),
                    'type': 'adhoc'
                })

            # Get calendar-based events if configured
            calendar_events = []
            if 'timed_calendar_events' in timer_plugin.config:
                import pytz
                import datetime

                timezone = pytz.timezone(self.core.config['core']['timezone'])
                target_time = datetime.datetime.now(timezone)

                for event in timer_plugin.config['timed_calendar_events']:
                    event_active = False
                    event_active_plugin = ""

                    for plugin in self.core.events_today.keys():
                        for event_name in event['event_names']:
                            if event_name.lower() in [x.lower() for x in self.core.events_today[plugin]]:
                                event_active = True
                                event_active_plugin = plugin

                    target_time_copy = target_time.replace(second=0)
                    target_time_copy = target_time_copy.replace(hour=event['hour'])
                    target_time_copy = target_time_copy.replace(minute=event['minute'])
                    target_timestamp = int(target_time_copy.strftime('%s'))

                    calendar_events.append({
                        'timestamp': target_timestamp,
                        'time_str': self.utils.get_nice_age(target_timestamp),
                        'command': event['command'],
                        'type': 'calendar',
                        'active': event_active,
                        'active_plugin': event_active_plugin if event_active else None,
                        'event_names': event['event_names']
                    })

            state = {
                'adhoc_commands': timed_commands,
                'calendar_events': calendar_events,
                'total_adhoc': len(timed_commands),
                'total_calendar': len(calendar_events),
                'timestamp': int(time.time())
            }

            state_json = json.dumps(state)

            # Only publish if changed or forced
            if force or state_json != self.last_cron_state:
                self.mqtt_client.publish(self.topic_cron, state_json, retain=self.retain_cron)
                self.last_cron_state = state_json
                self.logger.debug(f"Published cron state: {len(timed_commands)} adhoc, {len(calendar_events)} calendar")

        except Exception as e:
            self.logger.error(f"Error publishing cron state: {e}")

    def publish_stations_state(self, force=False):
        """Publish radio stations list from mpd-client plugin"""
        try:
            # Check if mpd-client plugin is available
            mpd_plugin = None
            for plugin in self.core.plugins:
                if plugin.command == 'mpd':
                    mpd_plugin = plugin
                    break

            if not mpd_plugin:
                self.logger.debug("MPD plugin not available, skipping stations state")
                return

            # Check if mpd-client plugin has stations configured
            if not hasattr(mpd_plugin, 'stations') or not mpd_plugin.stations:
                self.logger.debug("No stations configured in MPD plugin, skipping stations state")
                return

            # Build stations list
            stations_list = []
            for station_name in sorted(mpd_plugin.stations):
                stations_list.append({
                    'name': station_name,
                    'url': mpd_plugin.stations[station_name]
                })

            # Get special station assignments
            special_stations = {}
            try:
                if 'default_st' in mpd_plugin.config:
                    special_stations['default'] = mpd_plugin.config['default_st']
                if 'wakeup_st' in mpd_plugin.config:
                    special_stations['wakeup'] = mpd_plugin.config['wakeup_st']
                if 'sleep_st' in mpd_plugin.config:
                    special_stations['sleep'] = mpd_plugin.config['sleep_st']
            except Exception:
                pass

            state = {
                'stations': stations_list,
                'total': len(stations_list),
                'special': special_stations,
                'timestamp': int(time.time())
            }

            state_json = json.dumps(state)

            # Only publish if changed or forced
            if force or state_json != self.last_stations_state:
                self.logger.debug(f"Publishing to {self.topic_stations} (retain={self.retain_stations})")
                result = self.mqtt_client.publish(self.topic_stations, state_json, retain=self.retain_stations)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.last_stations_state = state_json
                    self.logger.debug(f"Published stations state: {len(stations_list)} stations (mid: {result.mid})")
                else:
                    self.logger.error(f"Failed to publish stations state, rc: {result.rc}")
            else:
                self.logger.debug("Stations state unchanged, skipping publish")

        except Exception as e:
            self.logger.error(f"Error publishing stations state: {e}", exc_info=True)

    def process_discovery_event(self, msg):
        """Handle node discovery events (nodes coming online/offline)"""
        # Publish updated nodes state when topology changes
        if self.mqtt_connected:
            self.core.add_timeout(1, self.publish_nodes_state, True)

    def process_presence_event(self, presence_before, presence_now):
        """Handle presence change events"""
        # Publish updated presence state immediately
        if self.mqtt_connected:
            self.logger.debug("Presence change detected, publishing MQTT update")
            self.core.add_timeout(0, self.publish_presence_state, True)

    def process_no_alarm_clock_event(self):
        """Handle alarm clock state change events"""
        # Publish updated alarm clock state immediately
        if self.mqtt_connected and self.core.master:
            self.logger.debug("Alarm clock state changed, publishing MQTT update")
            self.core.add_timeout(0, self.publish_alarmclock_state, True)

    # Command handlers
    def cmd_status(self, args):
        """Show MQTT connection status"""
        status = "connected" if self.mqtt_connected else "disconnected"
        ret = [
            f"MQTT Status: {status}",
            f"Broker: {self.mqtt_host}:{self.mqtt_port}",
            f"Base Topic: {self.mqtt_base_topic}",
            f"Update Interval: {self.update_interval}s",
            "",
            "Topics:",
            f"  Command (sub): {self.topic_command}",
            f"  Nodes (pub): {self.topic_nodes} (retain: {self.retain_nodes})",
            f"  Presence (pub): {self.topic_presence} (retain: {self.retain_presence})",
            f"  Alarmclock (pub): {self.topic_alarmclock} (retain: {self.retain_alarmclock})",
            f"  Cron (pub): {self.topic_cron} (retain: {self.retain_cron})",
            f"  Stations (pub): {self.topic_stations} (retain: {self.retain_stations})",
            f"  Events (pub): {self.topic_events} (retain: {self.retain_events})"
        ]
        return ret

    def cmd_reconnect(self, args):
        """Reconnect to MQTT broker"""
        self.logger.info("Manual reconnect requested")
        if self.mqtt_client:
            try:
                self.mqtt_client.reconnect()
                return ["Reconnecting to MQTT broker..."]
            except Exception as e:
                return [f"Reconnect failed: {e}"]
        else:
            return ["MQTT client not initialized"]

    def cmd_publish_all(self, args):
        """Force publish all states"""
        if self.mqtt_connected:
            self.publish_all_states(force=True)
            return ["Published all MQTT states"]
        else:
            return ["MQTT not connected"]

    def cmd_send(self, args):
        """Send custom event/message to MQTT events topic
        Usage: mqtt send <subtopic> <payload...>
        Example: mqtt send button/pressed "Living room button"
        Example: mqtt send ir/remote "KEY_POWER"
        """
        if not self.mqtt_connected:
            return ["MQTT not connected"]

        if len(args) < 2:
            return ["Usage: mqtt send <subtopic> <payload...>"]

        subtopic = args[0]
        payload = ' '.join(args[1:])

        # Build full topic: base_topic + events/ + subtopic
        # For example: james2/events/button/pressed
        full_topic = self.topic_events + '/' + subtopic

        try:
            self.logger.info(f"Publishing custom event to {full_topic}: {payload}")

            # Create event message with metadata
            event = {
                'topic': subtopic,
                'payload': payload,
                'hostname': self.core.hostname,
                'timestamp': int(time.time())
            }

            event_json = json.dumps(event)

            result = self.mqtt_client.publish(full_topic, event_json, retain=self.retain_events)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Published event (mid: {result.mid})")
                return [f"Published to {full_topic}"]
            else:
                self.logger.error(f"Failed to publish event, rc: {result.rc}")
                return [f"Failed to publish (error code: {result.rc})"]

        except Exception as e:
            self.logger.error(f"Error sending MQTT event: {e}", exc_info=True)
            return [f"Error: {e}"]

    def return_status(self, verbose=False):
        """Return plugin status"""
        return {
            'connected': self.mqtt_connected,
            'broker': f"{self.mqtt_host}:{self.mqtt_port}",
            'base_topic': self.mqtt_base_topic
        }


descriptor = {
    'name': 'mqtt',
    'help_text': 'MQTT integration for Node-RED and other systems',
    'command': 'mqtt',
    'mode': PluginMode.MANAGED,
    'class': MqttPlugin,
    'detailsNames': {
        'connected': 'Connection Status',
        'broker': 'MQTT Broker',
        'base_topic': 'Base Topic'
    }
}
