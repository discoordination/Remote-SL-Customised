# Source Generated with Decompyle++
# File: RemoteSLComponent.pyc (Python 3.11)

"""Base helper class shared by the Remote SL controller components."""

from .consts import *
import Live


class RemoteSLComponent(object):
	"""Provide common accessors and MIDI helpers for controller components."""


	def __init__(self, remote_sl_parent):
		self._parent = remote_sl_parent
		self._support_mkII = False


	def application(self):
		"""Expose the Live application object."""
		return self._parent.application()


	def build_midi_map(self, midi_map_handle):
		"""Build MIDI mappings for the component."""
		pass


	def cc_status_byte(self):
		"""Return the CC status byte for the script's MIDI channel."""
		return Constants.MIDI.STATUS + Constants.Hardware.MIDI_CHANNEL


	def disconnect(self):
		"""Clean up component state when the script is disconnected."""
		pass


	@property
	def song(self) -> Live.Song.Song:
		"""Expose the Live song object."""
		return self._parent.song


	def refresh_state(self):
		"""Refresh the component state after a change."""
		pass


	def request_rebuild_midi_map(self):
		"""Request that Live rebuild the MIDI mapping table."""
		self._parent.request_rebuild_midi_map()


	def send_midi(self, midi_event_bytes):
		"""Send MIDI data through the parent Remote SL script."""
		self._parent._send_midi(midi_event_bytes)


	def set_support_mkII(self, support_mkII):
		"""Set the MkII support flag."""
		self._support_mkII = support_mkII


	def support_mkII(self):
		"""Return whether the controller is running in MkII mode."""
		return self._support_mkII
	

	def update_display(self):
		"""Update any controller display content."""
		pass

	@property
	def is_private(self):
		return False
