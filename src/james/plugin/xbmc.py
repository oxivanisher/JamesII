
import json
import uuid
import httplib2

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

        self.updateNode = False
        if self.core.hostname in self.config['updatenodes']:
            self.updateNode = True
        self.load_state('updates', 0)

        self.commands.create_subcommand('test', 'test message', self.get_active_player_details)

    def send_rpc(self, method, params=None):
        if params is None:
            params = {}

        id = str(uuid.uuid1())
        h = httplib2.Http()
        h.add_credentials(self.config['nodes'][self.core.hostname]['username'],
                          self.config['nodes'][self.core.hostname]['password'])

        server_string = "http://%s:%s/jsonrpc" % (self.config['nodes'][self.core.hostname]['host'],
                                                  self.config['nodes'][self.core.hostname]['port'])

        raw_data = [{"jsonrpc": "2.0", 'id': id, 'method': method, 'params': params}]

        data = json.dumps(raw_data)
        try:
            resp, content = h.request(server_string, "POST", body=data, headers={'Content-Type': 'application/json'})
            if resp.status != 200:
                self.logger.debug('Unable to process RPC request %s: (%s) (%s)' % (resp.status, raw_data, resp))
                return False
            else:
                try:
                    return json.loads(resp)[0]
                except Exception:
                    return True

        except Exception as e:
            self.logger.warning('Unable to connect to XBMC: %s' % e)
            return False

    def send_rpc_message(self, title, message):
        return self.send_rpc("GUI.ShowNotification", {"title": title, "message": message})

    def cmd_pause(self, args):
        player_id = self.get_active_player()
        pause = False
        if player_id:
            if self.get_active_player_details(player_id)['speed'] == 1:
                pause = True
        if pause:
            self.send_rpc("Player.PlayPause", {"playerid": player_id})
            return ["Paused"]
        return ["Not paused"]

    def cmd_toggle(self, args):
        player_id = self.get_active_player()
        pause = False
        if player_id:
            self.send_rpc("Player.PlayPause", {"playtogglederid": player_id})
            return ["Toggled"]
        return ["Not toggled"]

    def cmd_stop(self, args):
        player_id = self.get_active_player()
        if player_id:
            self.send_rpc("Player.STOP", {"playerid": player_id})
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
        nice_status = "Stopped"
        if status['actId']:
            nice_status = "%s: %s %s" % (status['nice_status'], status['niceName'], status['niceTime'])
        return nice_status

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
        active_player_raw = self.utils.convert_from_unicode(self.send_rpc("Player.GetActivePlayers"))
        try:
            for activePlayer in active_player_raw['result']:
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
            play_item_raw = self.send_rpc("Player.GetItem", {"playerid": player})

            try:
                f_label = play_item_raw['result']['item']['label']
                f_type = play_item_raw['result']['item']['type']
                f_id = -1

                if play_item_raw['result']['item']['type'] != 'unknown':
                    f_id = play_item_raw['result']['item']['id']

                return {'label': f_label,
                        'type': f_type,
                        'id': f_id}
            except TypeError:
                pass

        return False

    def get_active_player_details(self, player=None):
        if not player:
            player = self.get_active_player()

        if player:
            play_item_raw = self.send_rpc("Player.GetProperties",
                                          {"playerid": player,
                                           "properties": ["speed", "percentage", "time", "totaltime"]})
            try:
                return {'speed': play_item_raw['result']['speed'],
                        'percentage': play_item_raw['result']['percentage'],
                        'time': play_item_raw['result']['time'],
                        'totaltime': play_item_raw['result']['totaltime']}
            except TypeError:
                pass            

        return False

    def get_episode_details(self, ep_id):
        episode_dbraw = self.send_rpc("VideoLibrary.GetEpisodeDetails",
                                      {"episodeid": ep_id,
                                       "properties": ["episode", "showtitle", "season", "firstaired"]})
        return {'label': episode_dbraw['result']['episodedetails']['label'],
                'episode': episode_dbraw['result']['episodedetails']['episode'],
                'showtitle': episode_dbraw['result']['episodedetails']['showtitle'],
                'firstaired': episode_dbraw['result']['episodedetails']['firstaired'],
                'season': episode_dbraw['result']['episodedetails']['season'] }

    def get_movie_details(self, movie_id):
        movie_dbraw = self.send_rpc("VideoLibrary.GetMovieDetails",
                                    {"movieid": movie_id, "properties": ["year", "originaltitle"]})
        return {'year': movie_dbraw['result']['moviedetails']['year'],
                'originaltitle': movie_dbraw['result']['moviedetails']['originaltitle']}

    def process_proximity_event(self, newstatus):
        self.logger.debug("XBMC Processing proximity event")
        if not newstatus['status'][self.core.location]:
            self.core.add_timeout(0, self.cmd_stop, None)

    def return_status(self, verbose=False):
        player = self.get_active_player()
        act_speed = ""
        act_percentage = 0.0
        act_time = {}
        act_totaltime = {}
        act_file = "unknown"
        act_file_id = "unknown"
        act_type = "unknown"
        nice_name = ""
        nice_status = "Stopped"
        nice_time = ""
        act_details = {}
        if player:
            act_player_data = self.get_active_player_details(player)

            try:
                act_speed = act_player_data['speed']
            except TypeError:
                pass

            act_percentage = act_player_data['percentage']
            act_time = act_player_data['time']
            act_totaltime = act_player_data['totaltime']

            try:
                act_file = self.get_active_file(player)['label']
            except TypeError:
                pass

            try:
                act_type = self.get_active_file(player)['type']
            except TypeError:
                pass

            try:
                act_file_id = self.get_active_file(player)['id']
            except TypeError:
                pass

            if act_type == 'unknown':
                nice_name = act_file
                nice_type = "Youtube"

            elif act_type == 'episode':
                act_details = self.get_episode_details(act_file_id)
                nice_name = "%s S%02dE%02d %s (%s)" % (act_details['showtitle'], act_details['season'],
                                                       act_details['episode'], act_details['label'],
                                                       act_details['firstaired'])
                nice_type = "Series"

            elif act_type == 'movie':
                nice_type = "Movie"
                act_details = self.get_movie_details(act_file_id)
                if act_details['year'] > 0:
                    nice_name = "%s (%s)" % (act_details['originaltitle'], act_details['year'])
                else:
                    nice_name = act_details['originaltitle']

            nice_time = "%s%% (%s:%02d:%02d/%s:%02d:%02d)" % (round(act_percentage, 0),
                                                              act_time['hours'],
                                                              act_time['minutes'],
                                                              act_time['seconds'],
                                                              act_totaltime['hours'],
                                                              act_totaltime['minutes'],
                                                              act_totaltime['seconds'] )
            if act_speed == 0:
                nice_status = "Paused (%s)" % nice_type
            if act_speed == 1:
                nice_status = "Playing (%s)" % nice_type
            else:
                nice_status = "Playing at %sx (%s)" % (act_speed, nice_type)

        ret = {'updates': self.updates, 'nice_name': nice_name, 'updateNode': self.updateNode, 'act_file': act_file,
               'actId': act_file_id, 'act_type': act_type, 'act_details': act_details, 'act_speed': act_speed,
               'act_percentage': act_percentage, 'act_time': act_time, 'act_totaltime': act_totaltime,
               'nice_status': nice_status, 'nice_time': nice_time}
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

