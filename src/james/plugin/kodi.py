import json
import uuid
import http.client
import base64

from james.plugin import *


class KodiPlugin(Plugin):

    def __init__(self, core, descriptor):
        super().__init__(core, descriptor)

        self.show_broadcast = False

        self.commands.create_subcommand('update', 'Initiates a Database update', self.cmd_update)
        self.commands.create_subcommand('info', 'Shows information about current playback', self.cmd_info)
        self.commands.create_subcommand('pause', 'Pause current playback', self.cmd_pause)
        self.commands.create_subcommand('stop', 'Stop current playback', self.cmd_stop)
        self.commands.create_subcommand('toggle', 'Toggle current playback', self.cmd_toggle)
        broadcast_cmd = self.commands.create_subcommand('broadcast', 'Should broadcast messages be sent', None)
        broadcast_cmd.create_subcommand('on', 'Activates broadcast messages', self.cmd_broadcast_on)
        broadcast_cmd.create_subcommand('off', 'Deactivates broadcast messages', self.cmd_broadcast_off)

        auth_string = ""
        if self.config['nodes'][self.core.hostname]['username']:
            auth_string = self.config['nodes'][self.core.hostname]['username']
        if self.config['nodes'][self.core.hostname]['password']:
            auth_string = auth_string + ":" + self.config['nodes'][self.core.hostname]['password']

        self.connection_headers = {'Content-Type': 'application/json'}
        if auth_string:
            self.connection_headers["Authorization"] = "Basic {}".format(base64.b64encode(bytes(f"{auth_string}",
                                                                                                "utf-8")).decode(
                "ascii"))
        self.updateNode = False
        if self.core.hostname in self.config['updatenodes']:
            self.updateNode = True
        self.updates = 0
        self.load_state('updates', 0)

        self.commands.create_subcommand('test', 'test msg', self.get_active_player_details)

    def send_rpc(self, method, params={}):
        my_id = str(uuid.uuid1())
        rawData = [{"jsonrpc": "2.0", 'id': my_id, 'method': method, 'params': params}]
        self.logger.debug(f'Kodi RPC request: ({rawData}) ({method})')

        data = json.dumps(rawData)
        try:
            h = http.client.HTTPConnection(self.config['nodes'][self.core.hostname]['host'],
                                           port=self.config['nodes'][self.core.hostname]['port'])
            h.request('POST', '/jsonrpc', data, self.connection_headers)
            r = h.getresponse()
            rpcReturn = json.loads(r.read())[0]
            if 'error' in rpcReturn.keys():
                self.logger.debug(f'Kodi unable to process RPC request: ({rawData}) ({rpcReturn})')
                return False
            else:
                self.logger.debug(f'Kodi RPC request successful: ({rawData}) ({rpcReturn})')
                return rpcReturn

        except Exception as e:
            sys_msg = f"Unable to connect to Kodi: {e}"
            self.logger.warning(sys_msg)
            self.system_message_add(sys_msg)
            return False

    def send_rpc_message(self, title, message):
        return self.send_rpc("GUI.ShowNotification", {"title": title, "msg": message})

    def cmd_pause(self, args):
        playerId = self.get_active_player()
        pause = False
        if playerId:
            if self.get_active_player_details(playerId)['speed'] == 1:
                pause = True
        if pause:
            self.send_rpc("Player.PlayPause", {"playerid": playerId})
            return ["Paused"]
        return ["Not paused"]

    def cmd_toggle(self, args):
        playerId = self.get_active_player()
        pause = False
        if playerId:
            self.send_rpc("Player.PlayPause", {"playtogglederid": playerId})
            return ["Toggled"]
        return ["Not toggled"]

    def cmd_stop(self, args):
        playerId = self.get_active_player()
        if playerId:
            self.send_rpc("Player.STOP", {"playerid": playerId})
            return ["Stopped"]
        return ["Not stopped"]

    def cmd_broadcast_on(self, args):
        self.show_broadcast = True
        return ["Broadcast messages will be shown"]

    def cmd_broadcast_off(self, args):
        self.show_broadcast = False
        return ["Broadcast messages will no longer be shown"]

    def cmd_update(self, args):
        if self.updateNode:
            self.core.add_timeout(0, self._send_kodi_update)
            self.logger.info("Database update scheduled")
            return ["Video database update scheduled."]
        else:
            self.logger.debug("Not updating database because I am not an updateNode")
            return ["Not updateNode, no database update."]

    def _send_kodi_update(self):
        """This will be called later, safely outside of the event loop."""
        if self.send_rpc("VideoLibrary.Scan"):
            self.logger.info("Database update sent successfully")
            return []
        else:
            sys_msg = "Failed to send database update"
            self.logger.error(sys_msg)
            self.system_message_add(sys_msg)

            return []

    def cmd_info(self, args):
        status = self.return_status()
        niceStatus = "Stopped"
        if status['actId']:
            niceStatus = f"{status['niceStatus']}: {status['niceName']} {status['niceTime']}"
        return niceStatus

    def alert(self, args):
        data = ' '.join(args).split(";")
        if len(data) > 1:
            self.send_rpc_message(data[0], data[1])
        elif len(data) == 1:
            self.send_rpc_message("JamesII Alert", data[0])

    def process_message(self, message):
        if message.level > 0:
            header = f'{message.sender_name}@{message.sender_host} ({message.level})'
            body_list = []
            for line in self.utils.list_unicode_cleanup([message.header]):
                body_list.append(line)
            try:
                for line in self.utils.list_unicode_cleanup([message.body]):
                    body_list.append(line)
            except Exception:
                pass
            body = ' '.join(body_list)

            if self.send_rpc_message(header, body):
                self.logger.debug(f"Showing msg: header ({header}) body ({body})")
            else:
                return ["Could not send notification."]

    def process_broadcast_command_response(self, args, host, plugin):
        if self.show_broadcast:
            header = f"{plugin}@{host}"
            body = ' '.join(self.utils.convert_from_unicode(args))
            if self.send_rpc_message(header, body):
                self.logger.debug(f"Showing broadcast msg: header ({header}) body ({body})")
            else:
                return ["Could not send notification."]

    def get_active_player(self):
        # get active player
        activePlayerRaw = self.utils.convert_from_unicode(self.send_rpc("Player.GetActivePlayers"))
        try:
            for activePlayer in activePlayerRaw['result']:
                if activePlayer['playerid']:
                    return activePlayer['playerid']
        except TypeError:
            pass

        return False

    def get_active_file(self, player=None):
        if not player:
            player = self.get_active_player()

        # get active item
        if player:
            playItemRaw = self.send_rpc("Player.GetItem", {"playerid": player})

            try:
                fLabel = playItemRaw['result']['item']['label']
                fType = playItemRaw['result']['item']['type']
                fId = -1

                if playItemRaw['result']['item']['type'] != 'unknown':
                    fId = playItemRaw['result']['item']['id']

                return {'label': fLabel,
                        'type': fType,
                        'id': fId}
            except TypeError:
                pass

        return False

    def get_active_player_details(self, player=None):
        if not player:
            player = self.get_active_player()

        if player:
            playItemRaw = self.send_rpc("Player.GetProperties", {"playerid": player,
                                                                 "properties": ["speed", "percentage", "time",
                                                                                "totaltime"]})
            try:
                return {'speed': playItemRaw['result']['speed'],
                        'percentage': playItemRaw['result']['percentage'],
                        'time': playItemRaw['result']['time'],
                        'totaltime': playItemRaw['result']['totaltime']}
            except TypeError:
                pass

        return False

    def get_episode_details(self, ep_id):
        episodeDBRaw = self.send_rpc("VideoLibrary.GetEpisodeDetails", {"episodeid": ep_id,
                                                                        "properties": ["episode", "showtitle", "season",
                                                                                       "firstaired"]})
        return {'label': episodeDBRaw['result']['episodedetails']['label'],
                'episode': episodeDBRaw['result']['episodedetails']['episode'],
                'showtitle': episodeDBRaw['result']['episodedetails']['showtitle'],
                'firstaired': episodeDBRaw['result']['episodedetails']['firstaired'],
                'season': episodeDBRaw['result']['episodedetails']['season']}

    def get_movie_details(self, movie_id):
        movieDBRaw = self.send_rpc("VideoLibrary.GetMovieDetails",
                                   {"movieid": movie_id, "properties": ["year", "originaltitle"]})
        return {'year': movieDBRaw['result']['moviedetails']['year'],
                'originaltitle': movieDBRaw['result']['moviedetails']['originaltitle']}

    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("Kodi Processing presence event")
        if not len(presence_now):
            self.core.add_timeout(0, self.cmd_stop, None)

    def return_status(self, verbose=False):
        player = self.get_active_player()
        actSpeed = ""
        actPercentage = 0.0
        actTime = {}
        actTotaltime = {}
        actFile = "unknown"
        actFileId = "unknown"
        actType = "unknown"
        niceName = ""
        niceStatus = "Stopped"
        niceTime = ""
        actDetails = {}
        if player:
            actPlayerData = self.get_active_player_details(player)

            try:
                actSpeed = actPlayerData['speed']
            except TypeError:
                pass

            actPercentage = actPlayerData['percentage']
            actTime = actPlayerData['time']
            actTotaltime = actPlayerData['totaltime']

            try:
                actFile = self.get_active_file(player)['label']
            except TypeError:
                pass

            try:
                actType = self.get_active_file(player)['type']
            except TypeError:
                pass

            try:
                actFileId = self.get_active_file(player)['id']
            except TypeError:
                pass

            if actType == 'unknown':
                niceName = actFile
                niceType = "Youtube"

            elif actType == 'episode':
                actDetails = self.get_episode_details(actFileId)
                niceName = f"{actDetails['showtitle']} S{actDetails['season']:02d}E{actDetails['episode']:02d} {actDetails['label']} ({actDetails['firstaired']})"
                niceType = "Series"

            elif actType == 'movie':
                niceType = "Movie"
                actDetails = self.get_movie_details(actFileId)
                if actDetails['year'] > 0:
                    niceName = f"{actDetails['originaltitle']} ({actDetails['year']})"
                else:
                    niceName = actDetails['originaltitle']

            niceTime = f"{round(actPercentage, 0)}% ({actTime['hours']}:{actTime['minutes']:02d}:{actTime['seconds']:02d}/{actTotaltime['hours']}:{actTotaltime['minutes']:02d}:{actTotaltime['seconds']:02d})"
            if actSpeed == 0:
                niceStatus = f"Paused ({niceType})"
            if actSpeed == 1:
                niceStatus = f"Playing ({niceType})"
            else:
                niceStatus = f"Playing at {actSpeed}x ({niceType})"

        ret = {'updates': self.updates, 'niceName': niceName, 'updateNode': self.updateNode, 'actFile': actFile,
               'actId': actFileId, 'actType': actType, 'actDetails': actDetails, 'actSpeed': actSpeed,
               'actPercentage': actPercentage, 'actTime': actTime, 'actTotaltime': actTotaltime,
               'niceStatus': niceStatus, 'niceTime': niceTime}
        return ret


descriptor = {
    'name': 'kodi',
    'help_text': 'Kodi module',
    'command': 'kodi',
    'mode': PluginMode.MANAGED,
    'class': KodiPlugin,
    'detailsNames': {'updates': "Database updates initated",
                     'niceName': "Active nice name",
                     'niceTime': "Active nice time",
                     'niceStatus': "Active nice status",
                     'updateNode': "DB update node",
                     'actSpeed': "Active speed",
                     'actPercentage': "Active percentage",
                     'actTime': "Active time",
                     'actTotaltime': "Active totaltime",
                     'actFile': "Active file",
                     'actId': "Active id",
                     'actType': "Active type",
                     'actDetails': "Active details"}
}
