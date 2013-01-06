
import sys
import requests
import json

from james.plugin import *


# http://forum.xbmc.org/showthread.php?tid=111772




# http://isbullsh.it/2012/06/Rest-api-in-python/
# => http://docs.python-requests.org/en/latest/index.html

# github_url = "https://api.github.com/user/repos"
# data = json.dumps({'name':'test', 'description':'some test repo'}) 
# r = requests.post(github_url, data, auth=('user', '*****'))
# print r.json

# james1 script dump (php)
# # Settings for PHP scripts
# require_once("/opt/james/settings/settings.php");
# # helper functions
# function returnStatus ($status) {
#     switch ($status) {
#         case 0:
#             return "Stopped";
#         break;
#         case 4:
#             return "Downloading";
#         break;
#         default:
#             return "Unknown";
#     }
# }
# # system functions
# function query ($host, $command, $agruments = null) {
#     if ($arguments) {
#         $data_string = json_encode(array("josnrpc" => "2.0", "id" => 1, "method" => $command, "params" => $arguments));
#     } else {
#         $data_string = json_encode(array("jsonrpc" => "2.0", "id" => 1, "method" => $command));
#     }
#     $payload = array('Content-Length: ' . strlen($data_string));
#     if ($fp = @fsockopen($host, $GLOBALS['xbport'])) {
#         $rawRequest = 'POST ' . $GLOBALS['xburl'] . ' HTTP/1.0' . PHP_EOL
#                       . 'Content-type: text/json;charset=utf-8' . PHP_EOL
#                       . 'Authorization: Basic ' . base64_encode($GLOBALS['xbuser'] . ':' . $GLOBALS['xbpass']) . PHP_EOL
#                       . 'Content-Length: ' . strlen($data_string) . PHP_EOL . PHP_EOL
#                       . $data_string;
#         fwrite($fp, $rawRequest);
#         $response = stream_get_contents($fp);
#         fclose($fp);
#         $data = json_decode($response);
#         if (! empty($data->error)) {
#             echo "An error occured. Request was:\n";
#             echo $rawRequest;
#             echo "\nServer says:\n";
#             die ((string) $data->error->message . " (" . (string) $data->error->code . ")\n");
#         } else {
#             return $data;
#         }
#     } else {
#         die ("socket could not be opened\n");
#     }
# }
# function query_multi_hosts($query, $args = array()) {
#     foreach ($GLOBALS['xbhost'] as $host) {
#         echo $host . ": ";
#         $data = query ($host, $query, $args);
#         echo (string) $data->result;
#         echo "\n";
#     }
# }
# #Here we go!
# if (empty($argv[1])) $argv[1] = null;
# switch ($argv[1]) {
#     case "update":
#         $data = query_multi_hosts ("VideoLibrary.Scan");
#     break;
#     case "notify":
#         $data = query_multi_hosts ("JSONRPC.NotifyAll", array("sender" => "xbmc.php", "message" => "test"));
#     break;
#     default:
#         echo "Commands are: update\n";
#     break;
# }

class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('test', 'Test command', self.cmd_test)

    def terminate(self):
        pass

    def cmd_xbmc(self, args):
        return 'args: ' + ' '.join(args)

    def cmd_test(self, args):
        # github_url = self.core."https://api.github.com/user/repos"
        # data = json.dumps({'name':'test', 'description':'some test repo'}) 
        # r = requests.post(github_url, data, auth=('user', '*****'))
        # print r.json
        pass



descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin
}

