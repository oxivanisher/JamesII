# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JamesII is a distributed smart home automation system written in Python 3. It uses a plugin-based architecture where nodes communicate via RabbitMQ message broker using AMQP protocol. The system supports distributed operation with one master node that holds configuration and multiple client nodes that can run specific plugins.

## Core Architecture

### Communication Model
- **RabbitMQ Broker**: All nodes connect to a centralized RabbitMQ server for communication
- **Broadcast Channels**: Uses fanout exchanges for pub/sub messaging between nodes
  - `discovery`: Node presence, ping/pong, command registration
  - `config`: Configuration distribution from master to clients
  - `request/response`: Command execution requests and responses
  - `msg`: User messages (notifications, alerts)
  - `presence`: User presence detection (home/away)
  - `dataRequest/dataResponse`: Data queries between plugins
  - `no_alarm_clock`: Calendar-based alarm clock state
  - `events_today`: Calendar events happening today

### Node Types
- **Master Node**: Has `config/config.yaml`, distributes configuration, coordinates other nodes
- **Client Nodes**: Receive configuration from master, run assigned plugins
- **Passive Nodes**: Special mode for external integrations (e.g., CLI-only access)

### Core Component (src/james/__init__.py)
The `Core` class is the main orchestrator:
- Manages RabbitMQ connection and broadcast channels
- Loads and instantiates plugins based on configuration
- Processes timeouts and events in main loop (configurable sleep time)
- Handles node discovery and presence tracking
- Thread-safe operations using `core_lock` RLock

### Plugin System (src/james/plugin/__init__.py)
Plugins are the functional units of JamesII:

**Plugin Modes**:
- `AUTOLOAD`: Loads automatically on all nodes if requirements met
- `MANAGED`: Only loads if specified in config under plugin name's `nodes` list
- `MANUAL`: Must be started manually (e.g., CLI, HTTP server)

**Plugin Structure**:
- Each plugin file must define a `descriptor` dict with: `name`, `help_text`, `command`, `mode`, `class`, `detailsNames`
- Plugin classes inherit from `Plugin` base class
- Plugins register commands via hierarchical `Command` objects
- Plugins can spawn `PluginThread` workers for background tasks

**Key Plugin Methods**:
- `start()`: Called when core is ready, register timeouts here
- `terminate()`: Cleanup on shutdown
- `process_message(message)`: Handle JamesMessage broadcasts
- `process_presence_event(before, now)`: React to user presence changes
- `handle_request()/handle_response()`: Process command requests/responses
- `return_status()`: Return plugin state for monitoring

### Command System (src/james/command.py)
Commands are hierarchical: `root → plugin_command → subcommand → subsubcommand`
- Commands support `@hostname1,hostname2` prefix for targeted execution
- Commands can be chained with `&&` separator
- Command aliases defined in config for shortcuts

### Configuration
- **broker.yaml**: RabbitMQ connection settings (required on all nodes)
- **config.yaml**: Master configuration (only on master node)
  - Plugin configurations under plugin name keys
  - `nodes` list under each plugin specifies which hosts run that plugin
  - `locations` maps hostnames to location names
  - `command_aliases` for shortcut commands
- Plugin-specific configs in plugin section of main config

## Development Commands

### Setup and Installation
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install base requirements
pip install -r requirements.txt

# Install plugin-specific requirements (optional)
pip install -r requirements-mpd-client.txt
pip install -r requirements-jabber.txt
# ... etc for other plugins
```

### Running JamesII
```bash
# Start master node (from src/ directory)
cd src
python3 james.py

# Start client node
cd src
python3 james.py

# Start CLI interface
cd src
python3 cli.py

# Run single CLI command and exit
cd src
python3 cli.py help
python3 cli.py sys status
```

### Configuration
```bash
# Copy example configs and edit
cp config/broker.yaml.example config/broker.yaml
cp config/config.yaml.example config/config.yaml

# Edit broker.yaml with RabbitMQ server details
# Edit config.yaml with your plugins and settings (master node only)
```

### RabbitMQ Server Setup (Debian/Ubuntu)
```bash
apt-get install rabbitmq-server
rabbitmqctl add_user james2 password
rabbitmqctl add_vhost james2
rabbitmqctl set_permissions -p james2 james2 ".*" ".*" ".*"
```

## Working with Plugins

### Creating a New Plugin
1. Create file in `src/james/plugin/` (e.g., `my-plugin.py`)
2. Import plugin base: `from james.plugin import *`
3. Define plugin class inheriting from `Plugin`
4. Define `descriptor` dict at module level
5. Register commands in `__init__`
6. Implement event handlers as needed

### Common Plugin Patterns
- Use `self.core.add_timeout(seconds, handler, *args)` for scheduled execution
- Access config via `self.config` (auto-populated from core config)
- Use `self.logger` for logging (child of core logger)
- Save state in `return_status()`, load in `__init__` via `self.load_state(name, default)`
- Use `self.send_command(args)` to trigger other plugin commands
- Use `self.core.new_message(name)` and `message.send()` for notifications

### Testing Plugins
- Use CLI to test commands interactively
- Check logs in console output (set `debug: true` in plugin config)
- Use `plugin_name debug on` command to enable debug logging at runtime
- Use `allstatus` command to see all plugin states

## Key Files and Locations

- `src/james.py` - Main entry point for james daemon
- `src/cli.py` - CLI interface entry point
- `src/james/__init__.py` - Core class implementation (1171 lines)
- `src/james/plugin/__init__.py` - Plugin base classes
- `src/james/plugin/*.py` - Individual plugins
- `src/james/command.py` - Hierarchical command system
- `src/james/jamesmessage.py` - Message abstraction for notifications
- `src/james/broadcastchannel.py` - RabbitMQ channel wrapper
- `src/james/presence.py` - Presence tracking
- `config/broker.yaml` - RabbitMQ settings (required)
- `config/config.yaml` - Master node configuration
- `~/.james_cli_history` - CLI command history
- `~/.james_presences` - Saved presence state
- `~/.james_stats` - Plugin state persistence
- `~/.james_system_messages` - System messages log

## Important Architecture Notes

### Threading and Concurrency
- Main event loop in `Core.run()` processes RabbitMQ events and timeouts
- Use `core.lock_core()` / `core.unlock_core()` for thread-safe RabbitMQ operations
- Plugin threads should communicate via `core.add_timeout()` to synchronize with main thread
- Timeout handlers run in main thread context

### Message Flow
1. CLI/Plugin calls `send_command(args)` or `send_request()`
2. Command sent over `request` channel
3. All nodes receive via `request_listener`
4. Matching plugin's `handle_request()` processes command
5. Plugin sends response via `send_response()`
6. Response broadcast on `response` channel
7. Requesting plugin's `handle_response()` receives result

### Signal Handling
- Core catches SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGTSTP, SIGSEGV
- Signals trigger graceful shutdown via `terminate()`
- Plugins have 10 seconds to terminate, threads have 30 seconds to exit
- State is saved to files on shutdown

### Windows Compatibility
- `signal.SIGALRM` not available on Windows (timeout mechanism adjusted)
- Some signal handlers are POSIX-only
- File paths use `os.path.join()` and `os.path.expanduser()` for compatibility

## Command Syntax

### Basic Commands
```
help                        # List all commands
help <command>             # Show subcommands
sys status                 # System status
nodes                      # Show online nodes
exit                       # Exit CLI
```

### Targeted Commands
```
@hostname command args     # Run on specific host
@host1,host2 command args  # Run on multiple hosts
```

### Command Chaining
```
command1 && command2       # Execute both commands (sent sequentially, not waited)
```

### Timer Commands (MCP)
```
mcp in 30s command args           # Run in 30 seconds
mcp in 5m command args            # Run in 5 minutes
mcp at 14:30 command args         # Run at 14:30 today
mcp at 14:30:00 command args      # With seconds
mcp at 14:30 2024-12-25 command   # Run at specific date/time
mcp show                          # List scheduled commands
mcp remove <timestamp> <command>  # Remove scheduled command
```

## Special Features

### Presence Detection
Multiple plugins can detect user presence (Bluetooth, calendar, etc.). Presence events trigger `process_presence_event()` on all plugins.

### Calendar Integration
- Google Calendar plugin provides `events_today`
- CalDAV plugin for Nextcloud/other CalDAV servers
- Timer plugin can schedule commands based on calendar events

### Node-Specific Configuration
- `locations` maps hostnames to location names (e.g., "home", "office")
- `nodes_main_loop_sleep` sets per-node event loop sleep times
- Plugins configure `nodes` list to specify which hosts run them

### State Persistence
- Plugins save state in `~/.james_stats` via `return_status()`
- State restored on startup via `load_state(name, default)`
- Timer commands persist in `~/.james_timer_store`
- Presence persists in `~/.james_presences`