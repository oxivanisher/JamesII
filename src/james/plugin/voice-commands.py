# http://stackoverflow.com/questions/892199/detect-record-audio-in-python
# http://stevenhickson.blogspot.ch/2013/04/voice-control-on-raspberry-pi.html
# https://github.com/StevenHickson/PiAUISuite/blob/master/VoiceCommand/voicecommand.cpp
# http://stackoverflow.com/questions/4160175/detect-tap-with-pyaudio-from-live-mic
# https://code.google.com/p/pygooglevoice/source/browse/#hg%2Fgooglevoice

# sounds:
# http://www.lcarscom.net/sounds.htm

# arecord -f cd -t wav -d 3 -r 16000 | flac - -f --best --sample-rate 16000 -o /dev/shm/out.flac 1>/dev/null 2>/dev/null; wget -O - -o /dev/null --post-file /dev/shm/out.flac --header="Content-Type: audio/x-flac; rate=16000" http://www.google.com/speech-api/v1/recognize?lang=en

# /x-flac; rate=16000" http://www.google.com/speech-api/v1/recognize?lang=en
# {"status":0,"id":"62744b72320e6f9116a5eb4c12c909cb-1","hypotheses":[{"utterance":"this is a test","confidence":0.9501244}]}


# sed -e 's/[{}]/''/g' \| 
# awk -v k="text" '{n=split($0,a,",");

# for (i=1; i<=n; i++) print a[i]; exit }' \| 
# awk -F: 'NR==3 { print $3; exit }'

# apt-get install python-poster python-pyaudio

import pyaudio
import sys
import wave
import subprocess
import struct
import time
import json
# import tempfile

def process_wave_data_aksdhj(audioData, channels, rate):
    URL = 'http://www.google.com/speech-api/v1/recognize?lang=en'

    # print "\tprocessing wave (%s)" % len(audioData)

    fname_wave = '/dev/shm/test.wav'
    fname_flac = '/dev/shm/test.flac'

    wav_file = wave.open(fname_wave, "w")
    wav_file.setparams((channels, 2, rate, len(audioData)/2, 'NONE', 'NOT COMPRESSED'))
    wav_file.writeframesraw(audioData)
    wav_file.close()

    subprocess.call(['/usr/bin/flac', '--totally-silent', '--delete-input-file', '-f', '--channels=1' '--best', '--sample-rate=16000', '-o', fname_flac, fname_wave]) #--delete-input-file

    # --header="Content-Type: audio/x-flac; rate=16000" http://www.google.com/speech-api/v1/recognize?lang=en
    # wget -O - -o /dev/null --post-file /dev/shm/out.flac --header="Content-Type: audio/x-flac; rate=16000" http://www.google.com/speech-api/v1/recognize?lang=en
    # print ' '.join(['/usr/bin/wget', '-O', '-', '--post-file', fname_flac, '--header="Content-Type: audio/x-flac; rate=16000"', URL])
    proc = subprocess.Popen(['/usr/bin/wget', '-O', '-', '-o', '/dev/null', '--post-file', fname_flac, '--header=Content-Type:audio/x-flac;rate=44100', URL], stdout=subprocess.PIPE)
    return_code = proc.wait()
    if return_code == 0:
        jsonResult = proc.stdout.read()
        return json.loads(jsonResult)
    else:
        print "\terror on wget or no output"
        return False

def voice_worker(recordVolume):
    CHANNELS = 1
    RATE = 44100
    # RATE = 16000

    chunk = 1024
    p = pyaudio.PyAudio()

    stream = p.open(format = pyaudio.paInt16,
                    channels = CHANNELS, 
                    rate = RATE, 
                    input = True,
                    output = True,
                    frames_per_buffer = chunk)

    loudTs = 0.0
    rms = 0
    working = True
    recording = False
    recordStartTs = 0
    returnData = ''
    print "* starting"
    while (working):
        data = stream.read(chunk)
        # if len(data) % 2 != 0:
        #     print "alert"
        for j in range(0, chunk / 2):
            sample = struct.unpack('h', data[j*2:j*2+2])[0]
            x = abs(sample / float(2**15-1))
            ratio = 0.1
            rms = (1 - ratio) * rms + ratio * x

            if (rms > recordVolume):
                loudTs = time.time()
                if not recording:
                    print "listening"
                    recordStartTs = time.time()
                    recording = True

        if recording:
            returnData += data

        recordDuration = time.time() - recordStartTs
        lastNoise = time.time() - loudTs

        if lastNoise > 2 and recording:
            print recordDuration
            recording = False

            print "stop listening"
            if recordDuration < 2.2:
                print "too short sound found"
            else:
                print "processing wave data"
                voiceCommand = process_wave_data_aksdhj(returnData, CHANNELS, RATE)
                if voiceCommand:
                    print "got command: %s" % voiceCommand
                else:
                    print "no voice command found"

            returnData = ''

    print "* done"
    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == '__main__':
    recordVolume = 0.25
    voice_worker(recordVolume)

# from poster.encode import multipart_encode
# from poster.streaminghttp import register_openers
# import urllib2

# datagen, headers = multipart_encode({"name": open('/tmp/test.flac', "rb")})
# # Create the Request object
# request = urllib2.Request(URL, datagen, headers)
# # Actually do the request, and get the response
# print urllib2.urlopen(request).read()