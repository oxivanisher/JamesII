# MQTT Plugin for JamesII

The MQTT plugin enables integration between JamesII and MQTT-based systems like Node-RED, Home Assistant, and other smart home platforms.

## Features

- **Command Subscription**: Send commands to JamesII via MQTT
- **State Publishing**: Automatically publishes JamesII state information
  - Online nodes
  - Presence detection (who is home)
  - Alarm clock status
  - Scheduled commands (cron/timer status)
  - Radio stations list (from mpd-client plugin)
- **Event Publishing**: Send user-initiated events to MQTT (button presses, IR remotes, etc.)
- **Configurable Retain**: Control whether MQTT messages are retained
- **Auto-reconnect**: Automatically reconnects to MQTT broker on connection loss

## Installation

1. Install the required MQTT library:
```bash
pip install -r requirements-mqtt.txt
```

2. Add the MQTT plugin configuration to your `config.yaml`

## Configuration

Add the following to your `config/config.yaml`:

```yaml
mqtt:
  # MQTT broker connection settings
  host: localhost              # MQTT broker hostname (default: localhost)
  port: 1883                   # MQTT broker port (default: 1883)
  username: your_username      # Optional: MQTT username
  password: your_password      # Optional: MQTT password

  # Topic configuration
  base_topic: james2/          # Base topic for all MQTT messages (default: james2/)

  # Retain settings - whether messages should be retained on the broker
  retain_nodes: true           # Retain nodes online state (default: true)
  retain_presence: true        # Retain presence state (default: true)
  retain_alarmclock: true      # Retain alarmclock state (default: true)
  retain_cron: true            # Retain cron/timer state (default: true)
  retain_stations: true        # Retain radio stations list (default: true)
  retain_events: false         # Retain user events (default: false)

  # Update interval for periodic state publishing (in seconds)
  update_interval: 30          # How often to publish state updates (default: 30)

  # Node configuration - which hosts should run this plugin
  nodes:
    - your_node_name
```

### Minimal Configuration

```yaml
mqtt:
  nodes:
    - your_node_name
```
This will use all defaults: localhost:1883, base_topic `james2/`, all retain enabled, 30s update interval.

## MQTT Topics

### Command Topic (Subscribe)
**Topic**: `james2/command`

Send JamesII commands via MQTT. The payload should be the command string, just like you would type in the CLI.

**Examples**:
```
james2/command → "sys status"
james2/command → "mpd radio on"
james2/command → "@mynode espeak say hello world"
james2/command → "mcp in 30s mpd radio off"
```

### State Topics (Publish)

#### Nodes Online
**Topic**: `james2/state/nodes`

Publishes information about online JamesII nodes.

**Example payload**:
```json
{
  "nodes": [
    {
      "hostname": "pi-living",
      "instances": 1,
      "uuids": ["abc123..."]
    },
    {
      "hostname": "pi-bedroom",
      "instances": 2,
      "uuids": ["def456...", "ghi789..."]
    }
  ],
  "total_nodes": 2,
  "total_instances": 3,
  "timestamp": 1703001234
}
```

#### Presence State
**Topic**: `james2/state/presence`

Publishes user presence information (who is home).

**Example payload**:
```json
{
  "somebody_home": true,
  "users_here": ["john", "jane"],
  "this_location": "home",
  "all_locations": [
    {
      "location": "home",
      "users": ["john", "jane"],
      "count": 2,
      "sources": ["btpresence@pi-living"]
    }
  ],
  "timestamp": 1703001234
}
```

#### Alarm Clock Status
**Topic**: `james2/state/alarmclock`

Publishes alarm clock enabled/disabled status (only from master node).

**Example payload**:
```json
{
  "enabled": false,
  "disabled": true,
  "disabling_plugins": ["gcal"],
  "timestamp": 1703001234
}
```

#### Cron/Timer Status
**Topic**: `james2/state/cron`

Publishes scheduled commands (equivalent to `mcp show` command).

**Example payload**:
```json
{
  "adhoc_commands": [
    {
      "timestamp": 1703010000,
      "time_str": "in 2 hours",
      "command": "mpd radio off",
      "type": "adhoc"
    }
  ],
  "calendar_events": [
    {
      "timestamp": 1703022000,
      "time_str": "in 5 hours",
      "command": "wakeup",
      "type": "calendar",
      "active": true,
      "active_plugin": "gcal",
      "event_names": ["Get up early"]
    }
  ],
  "total_adhoc": 1,
  "total_calendar": 1,
  "timestamp": 1703001234
}
```

#### Radio Stations
**Topic**: `james2/state/stations`

Publishes available radio stations from the mpd-client plugin.

**Example payload**:
```json
{
  "stations": [
    {
      "name": "chillout",
      "url": "http://www.oxi.ch/chillout.m3u"
    },
    {
      "name": "srf1_be",
      "url": "http://stream.srg-ssr.ch/regi_be_fr_vs/mp3_128.m3u"
    },
    {
      "name": "srf3",
      "url": "http://stream.srg-ssr.ch/drs3/mp3_128.m3u"
    }
  ],
  "total": 3,
  "special": {
    "default": "srf1_be",
    "wakeup": "srf1_be",
    "sleep": "chillout"
  },
  "timestamp": 1703001234
}
```

### Event Topic (Publish)

#### User-Initiated Events
**Topic**: `james2/events/<subtopic>`

Publish custom events from JamesII to MQTT using the `mqtt send` command. This is useful for sending notifications about button presses, IR remote commands, motion detection, or any other user-initiated or sensor-triggered events.

**Command**: `mqtt send <subtopic> <payload...>`

**Examples**:
```bash
# Button press in living room
mqtt send button/pressed "Living room button"

# IR remote key
mqtt send ir/remote "KEY_POWER"

# Motion detection
mqtt send motion/detected "Front door"

# Custom sensor reading
mqtt send sensor/temperature "23.5C"
```

**Example MQTT topics and payloads**:
- Topic: `james2/events/button/pressed`
- Payload:
```json
{
  "topic": "button/pressed",
  "payload": "Living room button",
  "hostname": "pi-living",
  "timestamp": 1703001234
}
```

- Topic: `james2/events/ir/remote`
- Payload:
```json
{
  "topic": "ir/remote",
  "payload": "KEY_POWER",
  "hostname": "pi-bedroom",
  "timestamp": 1703001235
}
```

## Commands

### View Plugin Status
```
mqtt status
```
Shows MQTT connection status, broker info, topics, and retain settings.

### Reconnect to Broker
```
mqtt reconnect
```
Manually trigger a reconnection to the MQTT broker.

### Publish All States
```
mqtt publish_all
```
Force an immediate publish of all state topics.

### Send Custom Event
```
mqtt send <subtopic> <payload...>
```
Send a custom event to MQTT. Useful for publishing button presses, IR remote events, sensor readings, or any user-initiated events.

**Examples**:
```
mqtt send button/pressed "Living room"
mqtt send ir/remote "KEY_POWER"
mqtt send motion/detected "Front door"
mqtt send sensor/temp "23.5C"
```

The event will be published to `james2/events/<subtopic>` with JSON payload including the message, hostname, and timestamp.

## Node-RED Integration Example

### Flow 1: Send Commands to JamesII
```json
[
    {
        "id": "mqtt_out",
        "type": "mqtt out",
        "topic": "james2/command",
        "broker": "mqtt_broker"
    },
    {
        "id": "inject",
        "type": "inject",
        "payload": "sys status",
        "wires": [["mqtt_out"]]
    }
]
```

### Flow 2: Monitor Presence
```json
[
    {
        "id": "mqtt_in",
        "type": "mqtt in",
        "topic": "james2/state/presence",
        "broker": "mqtt_broker",
        "wires": [["json_parse"]]
    },
    {
        "id": "json_parse",
        "type": "json"
    },
    {
        "id": "somebody_home",
        "type": "switch",
        "property": "payload.somebody_home",
        "rules": [
            {"t": "true"},
            {"t": "false"}
        ]
    }
]
```

### Flow 3: Turn on Radio When Someone Arrives Home
```json
[
    {
        "id": "presence_in",
        "type": "mqtt in",
        "topic": "james2/state/presence",
        "broker": "mqtt_broker",
        "wires": [["json", "check_home"]]
    },
    {
        "id": "json",
        "type": "json"
    },
    {
        "id": "check_home",
        "type": "switch",
        "property": "payload.somebody_home",
        "rules": [{"t": "true"}],
        "wires": [["delay"]]
    },
    {
        "id": "delay",
        "type": "delay",
        "pauseType": "rate",
        "timeout": 1,
        "timeoutUnits": "minutes",
        "wires": [["send_command"]]
    },
    {
        "id": "send_command",
        "type": "mqtt out",
        "topic": "james2/command",
        "payload": "mpd radio on",
        "broker": "mqtt_broker"
    }
]
```

### Flow 4: Listen for JamesII Events (Button Presses, etc.)
```json
[
    {
        "id": "events_in",
        "type": "mqtt in",
        "topic": "james2/events/#",
        "broker": "mqtt_broker",
        "wires": [["json", "process_event"]]
    },
    {
        "id": "json",
        "type": "json"
    },
    {
        "id": "process_event",
        "type": "switch",
        "property": "payload.topic",
        "rules": [
            {"t": "eq", "v": "button/pressed"},
            {"t": "eq", "v": "ir/remote"}
        ],
        "wires": [["handle_button"], ["handle_ir"]]
    },
    {
        "id": "handle_button",
        "type": "debug",
        "name": "Button pressed"
    },
    {
        "id": "handle_ir",
        "type": "debug",
        "name": "IR remote"
    }
]
```

### Flow 5: Display Available Radio Stations
```json
[
    {
        "id": "stations_in",
        "type": "mqtt in",
        "topic": "james2/state/stations",
        "broker": "mqtt_broker",
        "wires": [["json", "extract_stations"]]
    },
    {
        "id": "json",
        "type": "json"
    },
    {
        "id": "extract_stations",
        "type": "function",
        "func": "const stations = msg.payload.stations;\nconst dropdown = stations.map(s => ({label: s.name, value: s.name}));\nmsg.payload = dropdown;\nreturn msg;",
        "wires": [["ui_dropdown"]]
    },
    {
        "id": "ui_dropdown",
        "type": "ui_dropdown",
        "label": "Radio Station",
        "name": "Select Station"
    }
]
```

## Behavior

### State Publishing
- States are published periodically based on `update_interval` (default: 30 seconds)
- States are also published **immediately** when changes are detected:
  - **Nodes online**: when a node joins or leaves
  - **Presence**: when someone arrives or leaves (via `process_presence_event`)
  - **Alarm clock**: when alarm clock is enabled/disabled (via `process_no_alarm_clock_event`)
- Force publish all states with `mqtt publish_all` command

### Message Retention
- By default, all state messages are retained (`retain: true`)
- Retained messages allow new MQTT clients to immediately see the last known state
- Configure individually per state type with `retain_*` settings
- Command topic is never retained (commands should not be replayed)

### Auto-Reconnect
- The plugin automatically reconnects if connection to MQTT broker is lost
- Uses paho-mqtt's built-in reconnection logic

## Troubleshooting

### Plugin Not Loading
Check that paho-mqtt is installed:
```bash
pip install paho-mqtt
```

### Connection Issues
1. Verify MQTT broker is running: `mosquitto -v` (if using Mosquitto)
2. Check host/port in config
3. Check username/password if authentication is enabled
4. View connection status: `mqtt status`

### Debug Logging
Enable debug output in config:
```yaml
mqtt:
  debug: true
  nodes:
    - your_node_name
```

Or at runtime:
```
mqtt debug on
```

### Testing with Mosquitto
Subscribe to all JamesII topics:
```bash
mosquitto_sub -h localhost -t "james2/#" -v
```

Publish a command:
```bash
mosquitto_pub -h localhost -t "james2/command" -m "sys status"
```

## Architecture Notes

- **Plugin Mode**: `MANAGED` - only runs on configured nodes
- **Threading**: Uses background thread for MQTT event loop
- **Thread Safety**: All James commands are scheduled via `core.add_timeout()` to run in main thread
- **State Changes**: Hooks into James events (`process_discovery_event`, `process_presence_event`)

## Example Use Cases

1. **Home Assistant Integration**: Publish JamesII presence to HA, control JamesII devices from HA
2. **Node-RED Automation**: Create complex automations that trigger JamesII commands
3. **Mobile Apps**: Use MQTT apps (IoT MQTT Dashboard) to control JamesII
4. **Monitoring**: Display JamesII node status on dashboards
5. **External Triggers**: React to MQTT events from other systems
6. **Button/IR Integration**: Forward button presses and IR remote events to Home Assistant or Node-RED
7. **Radio Station Selection**: Build UI dashboards with available radio stations

## Integration with Physical Buttons and IR Remotes

You can integrate physical buttons (Raspberry Pi GPIO) or IR remotes with MQTT by using the `mqtt send` command in your button/IR configurations.

### Example: evdev Plugin Button Configuration
```yaml
evdev-client:
  nodes:
    node_name:
      gpio_ir_recv:
        KEY_ENTER: "mpd radio off && mqtt send ir/remote KEY_ENTER"
        KEY_PLAYPAUSE: "mpd radio toggle && mqtt send ir/remote KEY_PLAYPAUSE"
        KEY_POWER: "sys quit all_nodes && mqtt send ir/remote KEY_POWER"
```

### Example: Raspberry Plugin Button Configuration
```yaml
raspberry:
  nodes:
    node_name:
      buttons:
        - pin: 23
          seconds: 0
          command: "mpd radio toggle && mqtt send button/gpio23 short_press"
        - pin: 23
          seconds: 2
          command: "gn8 && mqtt send button/gpio23 long_press"
```

This way, every button press or IR remote command will:
1. Execute the JamesII command (turn on radio, etc.)
2. Send an event to MQTT that Node-RED/Home Assistant can react to

## Related Configuration

If using presence detection with MQTT, ensure presence plugins are configured:
- `btpresence`: Bluetooth presence detection
- `gcal` or `caldav`: Calendar-based presence

If using cron/timer states, ensure timer plugin is configured:
```yaml
timer:
  nodes:
    - your_node_name
```

## Security Considerations

- Use MQTT authentication (username/password) in production
- Consider using MQTT over TLS (port 8883) for sensitive environments
- Restrict MQTT topic access with ACLs on the broker
- The command topic allows full control of JamesII - protect it accordingly
