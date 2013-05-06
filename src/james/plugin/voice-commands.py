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
import math

from james.plugin import *

class VoiceThread(PluginThread):

    def __init__(self, plugin, core, threshold, lang, timeout, channels, rate):
        super(VoiceThread, self).__init__(plugin)

        self.core = core
        self.threshold = threshold
        self.timeout = timeout
        self.lang = lang
        self.channels = channels
        self.rate = rate
        self.fnameWave = '/dev/shm/james-voice-command.wav'
        self.fnameFlac = '/dev/shm/james-voice-command.flac'
        self.lastTextDetected = 0
        self.startupTime = 0
        self.streamIn = None
        self.streamOut = None

    def process_wave_data(self, audioData):
        URL = 'http://www.google.com/speech-api/v1/recognize?lang=' + self.lang

        wav_file = wave.open(self.fnameWave, "w")
        wav_file.setparams((self.channels, 2, self.rate, len(audioData)/2, 'NONE', 'NOT COMPRESSED'))
        wav_file.writeframesraw(audioData)
        wav_file.close()

        subprocess.call(['/usr/bin/flac', '--totally-silent', '--delete-input-file', '-f', '--channels=1' '--best', '--sample-rate=16000', '-o', self.fnameFlac, self.fnameWave])


        self.plugin.workerLock.acquire()
        self.plugin.bytesSubmitted += os.path.getsize(self.fnameFlac)
        self.plugin.workerLock.release()

        proc = subprocess.Popen(['/usr/bin/wget', '-O', '-', '-o', '/dev/null', '--post-file', self.fnameFlac, '--header=Content-Type:audio/x-flac;rate=44100', URL], stdout=subprocess.PIPE)
        return_code = proc.wait()
        os.unlink(self.fnameFlac)
        if return_code == 0:
            jsonResult = proc.stdout.read()
            return json.loads(jsonResult)
        else:
            return False

    def play_beep(self, herz, amount, duration):
        steps = ( int(amount) * 2 ) -1
        stepTime = float(duration) / steps
        nullSound = struct.pack('h', 0)
        for step in range(steps):
            if (step % 2) == 0:
                self.play_herz_for(herz, stepTime)
            else:
                self.play_stream(nullSound * int(44100 * stepTime))

    def play_herz_for(self, herz, duration):
        herz = float(herz) 
        samples = int(44100 * float(duration))
        rawSound = ''
        for sample in range(samples):
            time = sample / 44100.0
            out = math.sin(time * herz * math.pi * 2)
            intOut = int(out * 32767)
            rawSound += struct.pack('h', intOut)

        self.play_stream(rawSound)

    def play_stream(self, rawSound):
        diff = (len(rawSound) / 2) % 1024
        nullSound = struct.pack('h', 0)
        newSound = rawSound + (nullSound * (1024 - diff))
        self.streamOut.write(newSound)

    def work(self):
        chunk = 1024
        p = pyaudio.PyAudio()

        self.streamIn = p.open(format = pyaudio.paInt16,
                        channels = self.channels, 
                        rate = self.rate, 
                        input = True,
                        output = False,
                        frames_per_buffer = chunk)

        self.streamOut = p.open(format = pyaudio.paInt16,
                        channels = self.channels, 
                        rate = self.rate, 
                        input = False,
                        output = True,
                        frames_per_buffer = chunk)

        loudTs = 0.0
        rms = 0
        run = True
        recording = False
        working = False
        recordStartTs = 0
        recordStoppedTs = 0
        returnData = ''
        while (run):
            data = self.streamIn.read(chunk)
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
                    recordStoppedTs = time.time()
                    recording = False

                    self.logger.debug("Stopped listening")
                    if recordDuration < 2.1:
                        self.logger.debug("Too short to be a command")
                    else:
                        self.logger.debug("Processing audio data")
                        voiceCommand = self.process_wave_data(returnData)
                        if voiceCommand:
                            lastTextDetected = time.time()
                            # self.play_beep(600, 2, 0.15)
                            self.logger.debug("Detection data: %s" % voiceCommand)
                            self.core.add_timeout(0, self.plugin.on_text_detected, voiceCommand)
                        else:
                            self.logger.info("No text detected")
                            self.play_herz_for(880, 0.1)
                            self.play_herz_for(660, 0.1)

                    returnData = ''

                elif (time.time() - recordStoppedTs) > self.timeout and recordStoppedTs != 0:
                    recordStoppedTs = 0
                    self.play_herz_for(880, 0.1)
                    self.play_herz_for(660, 0.1)
                    self.logger.info("Timeout reached. Disabling voice commands.")
                    self.plugin.workerLock.acquire()
                    self.plugin.workerWorking = False
                    self.plugin.workerLock.release()
                    returnData = ''

            self.plugin.workerLock.acquire()
            run = self.plugin.workerRunning
            newWorking = self.plugin.workerWorking
            playSounds = self.plugin.playSounds
            self.plugin.playSounds = []
            playBeeps = self.plugin.playBeeps
            self.plugin.playBeeps = []
            self.plugin.workerLock.release()

            if working == False and newWorking == True:
                self.play_herz_for(660, 0.1)
                self.play_herz_for(880, 0.1)
            working = newWorking

            for (herz, duration) in playSounds:
                self.play_herz_for(herz, duration)

            for (herz, amount, duration) in playBeeps:
                self.play_beep(herz, amount, duration)

        self.streamIn.stop_stream()
        self.streamIn.close()
        self.streamOut.stop_stream()
        self.streamOut.close()
        p.terminate()
        self.logger.debug('Exited')


class VoiceCommandsPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(VoiceCommandsPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('start', ('Starts voice detection'), self.cmd_start_thread)
        self.commands.create_subcommand('stop', ('Stopps voice detection'), self.cmd_stop_thread)
        self.commands.create_subcommand('playTone', 'Plays a tone (herz) (time)', self.cmd_play_herz_for)
        self.commands.create_subcommand('playBeep', 'Plays beeps (herz) (amount) (time)', self.cmd_play_beep)

        self.workerLock = threading.Lock()
        self.workerRunning = True
        self.workerWorking = False
        self.bytesSubmitted = 0
        self.playSounds = []
        self.playBeeps = []
        
        self.voiceThread = VoiceThread(self,
                                       self.core,
                                       self.config['nodes'][self.core.hostname]['threshold'],
                                       self.config['nodes'][self.core.hostname]['lang'],
                                       self.config['nodes'][self.core.hostname]['timeout'],
                                       1,
                                       44100,)
        self.voiceThread.start()

    def terminate(self):
        self.workerLock.acquire()
        self.workerRunning = False
        self.workerLock.release()

    def return_status(self):
        ret = {}
        self.workerLock.acquire()
        ret['nowRecording'] = self.workerWorking
        ret['bytesSubmitted'] = self.bytesSubmitted
        self.workerLock.release()
        return ret

    def cmd_stop_thread(self,args):
        self.workerLock.acquire()
        self.workerWorking = False
        self.workerLock.release()

    def cmd_start_thread(self, args):
        self.workerLock.acquire()
        self.workerWorking = True
        self.workerLock.release()

    def on_text_detected(self, textData):
        # self.logger.info("Processing text data")
        niceData = self.utils.convert_from_unicode(textData)
        for decodedTextData in niceData['hypotheses']:
            confidence = decodedTextData['confidence']
            rawText = decodedTextData['utterance'].lower().split()
            keyword = self.config['nodes'][self.core.hostname]['keyword'].lower()
            text = []
            try:
                if rawText[0] == keyword:
                    text = rawText[1:]
            except IndexError:
                pass

            try:
                if rawText[1] == keyword:
                    text = rawText[2:]
            except IndexError:
                pass

            if len(text) == 0:
                self.logger.info("No keyword and command detected in: %s" % ' '.join(rawText))
                self.playBeeps.append((440, 3, 0.15))
            else:
                print self.config['commands'] # [{u'it is time for tea': u'tea'}, {u'sleep well': u'gn8'}]
                if ' '.join(text) in self.config['commands']:
                    self.logger.info("Found command: %s" % ' '.join(text))
                    self.playBeeps.append((880, 2, 0.1))
                else:
                    self.logger.info("Unknown command: %s" % ' '.join(text))
                    self.playBeeps.append((440, 2, 0.1))

        # print "text tetected callback:\n%s" % niceData

    def cmd_play_herz_for(self, args):
        if len(args) >= 2:
            self.playSounds.append((args[0], args[1]))
        else:
            return ["Syntax error. Use (herz) (duration)"]

    def cmd_play_beep(self, args):
        if len(args) >= 3:
            self.playBeeps.append((args[0], args[1], args[2]))
        else:
            return ["Syntax error. Use (herz) (amount) (duration)"]


descriptor = {
    'name' : 'voice-commands',
    'help' : 'Voice command interface',
    'command' : 'voice',
    'mode' : PluginMode.MANAGED,
    'class' : VoiceCommandsPlugin,
    'detailsNames' : { 'nowRecording' : "Currently recording",
                       'bytesSubmitted' : "Bytes submitted to google" }
}
