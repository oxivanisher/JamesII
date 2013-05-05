# http://stackoverflow.com/questions/892199/detect-record-audio-in-python
# http://stevenhickson.blogspot.ch/2013/04/voice-control-on-raspberry-pi.html
# https://github.com/StevenHickson/PiAUISuite/blob/master/VoiceCommand/voicecommand.cpp
# http://stackoverflow.com/questions/4160175/detect-tap-with-pyaudio-from-live-mic
# https://code.google.com/p/pygooglevoice/source/browse/#hg%2Fgooglevoice

# sounds:
# http://www.lcarscom.net/sounds.htm

# apt-get install python-poster python-pyaudio

import pyaudio
import sys
import wave
import subprocess
import struct
import time
import json
import tempfile
import os

from james.plugin import *

class VoiceThread(PluginThread):

    def __init__(self, plugin, core, threshold, lang, channels, rate):
        super(VoiceThread, self).__init__(plugin)

        self.core = core
        self.threshold = threshold
        self.lang = lang
        self.channels = channels
        self.rate = rate
        self.fnameWave = '/dev/shm/james-voice-command.wav'
        self.fnameFlac = '/dev/shm/james-voice-command.flac'
        self.lastTextDetected = 0
        self.startupTime = 0
       

    def process_wave_data(self, audioData):
        URL = 'http://www.google.com/speech-api/v1/recognize?lang=' + self.lang

        # FIXME: track total upload size
        
        wav_file = wave.open(self.fnameWave, "w")
        wav_file.setparams((self.channels, 2, self.rate, len(audioData)/2, 'NONE', 'NOT COMPRESSED'))
        wav_file.writeframesraw(audioData)
        wav_file.close()

        subprocess.call(['/usr/bin/flac', '--totally-silent', '--delete-input-file', '-f', '--channels=1' '--best', '--sample-rate=16000', '-o', self.fnameFlac, self.fnameWave])

        proc = subprocess.Popen(['/usr/bin/wget', '-O', '-', '-o', '/dev/null', '--post-file', self.fnameFlac, '--header=Content-Type:audio/x-flac;rate=44100', URL], stdout=subprocess.PIPE)
        return_code = proc.wait()
        os.unlink(self.fnameFlac)
        if return_code == 0:
            jsonResult = proc.stdout.read()
            return json.loads(jsonResult)
        else:
            return False

    def work(self):
        chunk = 1024
        p = pyaudio.PyAudio()

        stream = p.open(format = pyaudio.paInt16,
                        channels = self.channels, 
                        rate = self.rate, 
                        input = True,
                        output = True,
                        frames_per_buffer = chunk)

        loudTs = 0.0
        rms = 0
        run = True
        recording = False
        working = False
        recordStartTs = 0
        returnData = ''
        while (run):
            data = stream.read(chunk)
            if working:
                if len(data) % 2 != 0:
                    self.logger.warning("Recieved invalid data from audio stream")
                for j in range(0, chunk / 2):
                    sample = struct.unpack('h', data[j*2:j*2+2])[0]
                    x = abs(sample / float(2**15-1))
                    ratio = 0.1
                    rms = (1 - ratio) * rms + ratio * x

                    if (rms > self.threshold):
                        loudTs = time.time()
                        if not recording:
                            self.logger.debug("Started listening")
                            recordStartTs = time.time()
                            recording = True

                if recording:
                    returnData += data

                recordDuration = time.time() - recordStartTs
                lastNoise = time.time() - loudTs

                if lastNoise > 2 and recording:
                    recording = False

                    self.logger.debug("Stopped listening")
                    if recordDuration < 2.1:
                        self.logger.debug("Too short to be a command")
                    else:
                        self.logger.debug("Processing audio data")
                        voiceCommand = self.process_wave_data(returnData)
                        if voiceCommand:
                            lastTextDetected = time.time()
                            self.logger.debug("Detection data: %s" % voiceCommand)
                            self.core.add_timeout(0, self.plugin.on_text_detected, voiceCommand)
                        else:
                            self.logger.debug("No text detected")

                    returnData = ''

            self.plugin.workerLock.acquire()
            run = self.plugin.workerRunning
            working = self.plugin.workerWorking
            self.plugin.workerLock.release()

        stream.stop_stream()
        stream.close()
        p.terminate()
        self.logger.debug('Exited')


class VoiceCommandsPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(VoiceCommandsPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('start', ('Starts voice detection'), self.cmd_start_thread)
        self.commands.create_subcommand('stop', ('Stopps voice detection'), self.cmd_stop_thread)
        self.commands.create_subcommand('status', ('Shows if the voice detection is running'), self.cmd_thread_status)

        self.workerLock = threading.Lock()
        self.workerRunning = True
        self.workerWorking = True
        
        self.lirc_thread = VoiceThread(self,
                                       self.core,
                                       self.config['nodes'][self.core.hostname]['threshold'],
                                       self.config['nodes'][self.core.hostname]['lang'],
                                       1,
                                       44100,)
        self.lirc_thread.start()

    def terminate(self):
        self.workerLock.acquire()
        self.workerRunning = False
        self.workerLock.release()

    def cmd_thread_status(self, args):
        self.workerLock.acquire()
        status = self.workerWorking
        self.workerLock.release()
        return [status]

    def cmd_stop_thread(self,args):
        self.workerLock.acquire()
        self.workerWorking = False
        self.workerLock.release()

    def cmd_start_thread(self, args):
        self.workerLock.acquire()
        self.workerWorking = True
        self.workerLock.release()

    def on_text_detected(self, textData):
        self.logger.info("Processing text data")
        niceData = self.utils.convert_from_unicode(textData)
        print "text tetected callback:\n%s" % niceData

descriptor = {
    'name' : 'voice-commands',
    'help' : 'Voice command interface',
    'command' : 'voice',
    'mode' : PluginMode.MANAGED,
    'class' : VoiceCommandsPlugin
}
