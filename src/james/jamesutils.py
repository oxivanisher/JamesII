
import time

class JamesUtils(object):
	def get_short_age(self, timestamp):
		return str(timestamp)
# public static function getAge($timestamp) {
#         $ageOfMsg = time() - $timestamp;
#         if ($timestamp == 0) {
#             $ageOfMsgReturn = "";
#         } elseif ($ageOfMsg < '60') {
#             $ageOfMsgReturn = $ageOfMsg . " sec(s)";
#         } elseif ($ageOfMsg > '59' && $ageOfMsg < '3600') {
#             $ageOfMsg = round(($ageOfMsg / 60), 1);
#             $ageOfMsgReturn = $ageOfMsg . " min(s)";
#         } elseif ($ageOfMsg >= '3600' && $ageOfMsg < '86400') {
#             $ageOfMsg = round(($ageOfMsg / 3600), 1);
#             $ageOfMsgReturn = $ageOfMsg . " hr(s)";
#         } elseif ($ageOfMsg >= '86400' && $ageOfMsg < '604800') {
#             $ageOfMsg = round(($ageOfMsg / 86400), 1);
#             $ageOfMsgReturn = $ageOfMsg . " day(s)";
#         } elseif ($ageOfMsg >= '604800' && $ageOfMsg < '31449600') {
#             $ageOfMsg = round(($ageOfMsg / 604800), 1);
#             $ageOfMsgReturn = $ageOfMsg . " week(s)";
#         } else {
#             $ageOfMsg = round(($ageOfMsg / 31449600), 1);
#             $ageOfMsgReturn = $ageOfMsg . " year(s)";
#         }
#         return $ageOfMsgReturn;
#     }

	def get_nice_age(self, timestamp):
		return timestamp
#  public static function getNiceAge($timestamp) {
#         $ageOfMsg = time() - $timestamp;
#         if ($timestamp == 0) {
#             $ageOfMsgReturn = "Noch nie";
#         } elseif ($ageOfMsg < '60') {
#             $ageOfMsgReturn = "Vor " . $ageOfMsg . " Sekunden";
#         } elseif ($ageOfMsg < '3600') {
#             $ageOfMsg = round(($ageOfMsg / 60), 1);
#             $ageOfMsgReturn = "Vor " . $ageOfMsg . " Minuten";
#         } elseif ($timestamp > strtotime(date('n') . '/' . date('j') . '/' . date('Y'))) {
#             $ageOfMsgReturn = strftime("Heute um %H:%M Uhr", $timestamp);
#         } elseif ($timestamp > strtotime(date('m/d/y', mktime(0, 0, 0, date("m"), date("d") - 1, date("Y"))))) {
#             $ageOfMsgReturn = strftime("Gestern um %H:%M Uhr", $timestamp);
#         } elseif ($ageOfMsg <= '604800') {
#             $ageOfMsgReturn = strftime("Letzten %A", $timestamp);
#         } elseif ($timestamp > strtotime('1/1/' . date('Y'))) {
#             $ageOfMsgReturn = strftime("Am %d. %B", $timestamp);
#         } else {
#             $ageOfMsgReturn = strftime("Am %d. %b. %Y", $timestamp);
#         }
#         return $ageOfMsgReturn;
#     }