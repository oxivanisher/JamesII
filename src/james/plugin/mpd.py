import os
import sys
import urllib2
import subprocess

from james.plugin import *

class MpdPlugin(Plugin):

	def __init__(self, core):
		super(MpdPlugin, self).__init__(core, MpdPlugin.name)

		self.create_command('mpc', self.cmd_mpc, 'interface to mpc')
		self.create_command('radio_on', self.cmd_radio_on, 'play radio')
		self.create_command('radio_off', self.cmd_radio_off, 'stop radio')
		self.create_command('mpd_sleep', self.cmd_mpd_sleep, 'play sleep radio and fade slowly out')
		self.create_command('mpd_wakeup', self.cmd_mpd_wakeup, 'play wakeup radio and fade slowly in')

		self.mpc_bin = '/usr/bin/mpc'

		self.connection_string = self.mpc_bin
		if self.core.config.values['mpd']['host'] != "":
			self.connection_string += " --host=" + self.core.config.values['mpd']['host']
		if self.core.config.values['mpd']['port'] != "":
			self.connection_string += " --port=" + self.core.config.values['mpd']['port']
		if self.core.config.values['mpd']['password'] != "":
			self.connection_string += " --password=" + self.core.config.values['mpd']['password']		

	def terminate(self):
		pass

#if os.path.isfile(self.mpc_bin): FIXME
	def cmd_mpc(self, args):
		self.exec_mpc(args)

	def cmd_radio_off(self, args):
		self.exec_mpc(['clear'])

	# radio (online url) methods
#if self.core.config.values['mpd']['url'] != "":
	def cmd_radio_on(self, args):
		self.load_online_playlist(self.core.config.values['mpd']['radio_url'])
		self.exec_mpc(['play'])		

	def cmd_mpd_sleep(self, args):
		self.load_online_playlist(self.core.config.values['mpd']['sleep_url'])
		self.exec_mpc(['play'])
		minutes = 1
		try:
			minutes = args[0]
		except IndexError:
			pass
		subprocess.Popen(['/usr/bin/mpfade', str(minutes), "0", self.core.config.values['mpd']['host']])

	def cmd_mpd_wakeup(self, args):
		self.exec_mpc(['clear'])
		self.load_online_playlist(self.core.config.values['mpd']['wakeup_url'])
		minutes = 1
		try:
			minutes = args[0]
		except IndexError:
			pass
		subprocess.Popen(['/usr/bin/mpfade', str(minutes), "100", self.core.config.values['mpd']['host']])

	# Helper Methods
	def exec_mpc(self, args):
		print 'cmd mpc ' + self.connection_string + ' ' + ' '.join(args)
		mpc_pipe = os.popen(self.connection_string + ' ' + ' '.join(args),'r')
		mpc = mpc_pipe.read().strip()
		mpc_pipe.close()
		return mpc

	def load_online_playlist(self, url):
		for source in urllib2.urlopen(url):
			if source != "":
				self.exec_mpc(['add', source])



descriptor = {
	'name' : 'mpd',
	'mode' : PluginMode.MANAGED,
	'class' : MpdPlugin
}

