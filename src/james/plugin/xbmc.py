
import json
import uuid
import urllib
import httplib

from james.plugin import *

class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

        self.show_broadcast = False

        self.commands.create_subcommand('update', 'Initiates a Database update', self.cmd_update)
        self.commands.create_subcommand('info', 'Shows information about current playback', self.cmd_info)
        self.commands.create_subcommand('pause', 'Pause current playback', self.cmd_pause)
        self.commands.create_subcommand('stop', 'Stop current playback', self.cmd_stop)
        self.commands.create_subcommand('toggle', 'Toggle current playback', self.cmd_toggle)
        broadcase_cmd = self.commands.create_subcommand('broadcast', 'Should broadcast messages be sent', None)
        broadcase_cmd.create_subcommand('on', 'Activates broadcast messages', self.cmd_broadcast_on)
        broadcase_cmd.create_subcommand('off', 'Deactivates broadcast messages', self.cmd_broadcast_off)

        user_string = ""
        if self.config['nodes'][self.core.hostname]['username']:
            user_string = self.config['nodes'][self.core.hostname]['username']
        if self.config['nodes'][self.core.hostname]['password']:
            user_string = user_string + ":" + self.config['nodes'][self.core.hostname]['password']
        if user_string:
            user_string = user_string + "@"
        server_string = "%s:%s" % (self.config['nodes'][self.core.hostname]['host'],
                                   self.config['nodes'][self.core.hostname]['port'])
        self.connection_string = "%s%s" % (user_string, server_string)

        self.updateNode = False
        if self.core.hostname in self.config['updatenodes']:
            self.updateNode = True
        self.load_state('updates', 0)

        self.commands.create_subcommand('test', 'test message', self.get_active_player_details)

    def send_rpc(self, method, params = {}):
        id = str(uuid.uuid1())
        headers = { 'Content-Type': 'application/json' }
        rawData = [{"jsonrpc":"2.0", 'id':id, 'method':method, 'params':params}]

        data = json.dumps(rawData)
        try:
            h = httplib.HTTPConnection(self.connection_string)
            h.request('POST', '/jsonrpc', data, headers)
            r = h.getresponse()
            rpcReturn = json.loads(r.read())[0]
            if 'error' in rpcReturn.keys():
                self.logger.debug('Unable to process RPC request: (%s) (%s)' % (rawData, rpcReturn))
                return False
            else:
                return rpcReturn

            if rpcReturn['error'] == 'OK':
                return True
            else:
                self.logger.debug('Unable to process RPC request: (%s) (%s)' % (rawData, rpcReturn))
                return False
        except Exception as e:
            self.logger.warning('Unable to connect to XBMC: %s' % e)
            return False

    def send_rpc_message(self, title, message):
        return self.send_rpc("GUI.ShowNotification", {"title":title, "message":message})

    def cmd_pause(self, args):
        playerId = self.get_active_player()
        pause = False
        if playerId:
            if self.get_active_player_details(playerId)['speed'] == 1:
                pause = True
        if pause:
            self.send_rpc("Player.PlayPause", {"playerid" : playerId})
            return ["Paused"]
        return ["Not paused"]

    def cmd_toggle(self, args):
        playerId = self.get_active_player()
        pause = False
        if playerId:
            self.send_rpc("Player.PlayPause", {"playtogglederid" : playerId})
            return ["Toggled"]
        return ["Not toggled"]

    def cmd_stop(self, args):
        playerId = self.get_active_player()
        if playerId:
            self.send_rpc("Player.STOP", {"playerid" : playerId})
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
            if self.send_rpc("VideoLibrary.Scan"):
                self.updates += 1
                self.logger.info("Database updating")
                return ["Video database is updating"]
            else:
                return ["Could not send update command"]
        else:
            self.logger.debug("Not update database because i am no updateNode")

    def cmd_info(self, args):
        status = self.return_status()
        niceStatus = "Stopped"
        if status['actId']:
            niceStatus = "%s: %s %s" % (status['niceStatus'], status['niceName'], status['niceTime'])
        return niceStatus

    def alert(self, args):
        data = ' '.join(args).split(";")
        if len(data) > 1:
            self.send_rpc_message(data[0], data[1])
        elif len(data) == 1:
            self.send_rpc_message("JamesII Alert", data[0])

    def process_message(self, message):
        if message.level > 0:
            header = '%s@%s (%s)' % (message.sender_name,
                                     message.sender_host,
                                     message.level)
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
                self.logger.debug("Showing message: header (%s) body (%s)" % (header, body))
            else:
                return ["Could not send notification."]

    def process_broadcast_command_response(self, args, host, plugin):
        if self.show_broadcast:
            header = "%s@%s" % (plugin, host)
            body = ' '.join(self.utils.convert_from_unicode(args))
            if self.send_rpc_message(header, body):
                self.logger.debug("Showing broadcast message: header (%s) body (%s)" % (header, body))
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
            playItemRaw = self.send_rpc("Player.GetItem", {"playerid" : player})

            try:
                fLabel = playItemRaw['result']['item']['label']
                fType = playItemRaw['result']['item']['type']
                fId = -1

                if playItemRaw['result']['item']['type'] != 'unknown':
                    fId = playItemRaw['result']['item']['id']

                return { 'label' : fLabel,
                         'type'  : fType,
                         'id'    : fId }
            except TypeError:
                pass

        return False

    def get_active_player_details(self, player=None):
        if not player:
            player = self.get_active_player()

        if player:
            playItemRaw = self.send_rpc("Player.GetProperties", {"playerid" : player, "properties" : [ "speed", "percentage", "time", "totaltime" ] })
            try:
                return { 'speed' : playItemRaw['result']['speed'],
                         'percentage' : playItemRaw['result']['percentage'],
                         'time' : playItemRaw['result']['time'],
                         'totaltime' : playItemRaw['result']['totaltime'] }
            except TypeError:
                pass            

        return False

    def get_episode_details(self, epId):
        episodeDBRaw = self.send_rpc("VideoLibrary.GetEpisodeDetails", {"episodeid" : epId, "properties" : ["episode", "showtitle", "season", "firstaired"]})
        return { 'label' : episodeDBRaw['result']['episodedetails']['label'],
                 'episode' : episodeDBRaw['result']['episodedetails']['episode'],
                 'showtitle' : episodeDBRaw['result']['episodedetails']['showtitle'],
                 'firstaired' : episodeDBRaw['result']['episodedetails']['firstaired'],
                 'season' : episodeDBRaw['result']['episodedetails']['season'] }

    def get_movie_details(self, movieId):
        movieDBRaw = self.send_rpc("VideoLibrary.GetMovieDetails", {"movieid" : movieId, "properties" : ["year", "originaltitle"]})
        return { 'year' : movieDBRaw['result']['moviedetails']['year'],
                 'originaltitle' : movieDBRaw['result']['moviedetails']['originaltitle'] }

    def process_proximity_event(self, newstatus):
        self.logger.debug("XBMC Processing proximity event")
        if not newstatus['status'][self.core.location]:
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
                niceName = "%s S%02dE%02d %s (%s)" % (actDetails['showtitle'], actDetails['season'], actDetails['episode'], actDetails['label'], actDetails['firstaired'])
                niceType = "Series"

            elif actType == 'movie':
                niceType = "Movie"
                actDetails = self.get_movie_details(actFileId)
                if actDetails['year'] > 0:
                    niceName = "%s (%s)" % (actDetails['originaltitle'], actDetails['year'])
                else:
                    niceName = actDetails['originaltitle']

            niceTime = "%s%% (%s:%02d:%02d/%s:%02d:%02d)" % (round(actPercentage, 0),
                                                           actTime['hours'],
                                                           actTime['minutes'],
                                                           actTime['seconds'],
                                                           actTotaltime['hours'],
                                                           actTotaltime['minutes'],
                                                           actTotaltime['seconds'] )
            if actSpeed == 0:
                niceStatus = "Paused (%s)" % niceType
            if actSpeed == 1:
                niceStatus = "Playing (%s)" % niceType
            else:
                niceStatus = "Playing at %sx (%s)" % (actSpeed, niceType)

        ret = {}
        ret['updates'] = self.updates
        ret['niceName'] = niceName
        ret['updateNode'] = self.updateNode
        ret['actFile'] = actFile
        ret['actId'] = actFileId
        ret['actType'] = actType
        ret['actDetails'] = actDetails
        ret['actSpeed'] = actSpeed
        ret['actPercentage'] = actPercentage
        ret['actTime'] = actTime
        ret['actTotaltime'] = actTotaltime
        ret['niceStatus'] = niceStatus
        ret['niceTime'] = niceTime
        return ret

descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin,
    'detailsNames' : { 'updates' : "Database updates initated",
                       'niceName' : "Active nice name",
                       'niceTime' : "Active nice time",
                       'niceStatus' : "Active nice status",
                       'updateNode' : "DB update node",
                       'actSpeed' : "Active speed",
                       'actPercentage' : "Active percentage",
                       'actTime' : "Active time",
                       'actTotaltime' : "Active totaltime",
                       'actFile' : "Active file",
                       'actId' : "Active id",
                       'actType' : "Active type",
                       'actDetails' : "Active details" }
}

