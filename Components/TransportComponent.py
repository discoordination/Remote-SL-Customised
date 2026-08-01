####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
####################################################################################################################
# TransportComponent.py
####################################################################################################################

from __future__ import annotations

from ableton.v2.control_surface import Component, MIDI_CC_TYPE
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement

from Live.Song import Song
from Live import MidiMap

from ..consts import H, T, M
from ..RemoteSL_Logger import log, log_info, log_verbose, log_listener_callback, LogLevel, LogCategory

import time
from typing import Final

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from ..RemoteSL import RemoteSL


####################################################################################################################


class TransportComponent(Component):

	################################################################################################################

	FORW_REW_JUMP_BY_AMOUNT : Final[float] = 0.25

	################################################################################################################

	_control_surface          : RemoteSL 
      
	_play_button              : ButtonElement
	_stop_button              : ButtonElement
	_record_button            : ButtonElement
	_loop_button              : ButtonElement
	_rewind_button            : ButtonElement 
	_fforward_button          : ButtonElement
	_tempo_msb                : EncoderElement
	_tempo_lsb                : EncoderElement

	_fforward_button_down     : bool
	_fforward_hold_start_time : float | None
	_rewind_button_down       : bool
	_rewind_hold_start_time   : float | None
	_tempo_msb_value		  : int


	################################################################################################################
	

	def __init__(self, control_surface: RemoteSL, name='TransportComponent', *a, **k):

		log_info(f"TransportComponent.__init__({control_surface},{name}) called.")

		super().__init__(name=name, song=control_surface.song, is_enabled=False, *a, **k)

		self._control_surface = control_surface

		self._rewind_button_down = False
		self._fforward_button_down  = False
		self._rewind_hold_start_time = None
		self._fforward_hold_start_time = None

		self._create_controls()

		log_info(f"<-----Returning from TransportComponent.__init__({name},{control_surface}).")


	################################################################################################################

	@property
	def control_surface(self):
		return self._control_surface


	@property
	@override
	def song(self) -> Song:
		result = super().song
		assert result is not None
		return result


	# ################################################################################################################

	@override
	def on_enabled_changed(self):

		log_info(f"TransportComponent.on_enabled_changed() called.  enabled={self.is_enabled()} explicit={self.is_enabled(True)}.")

		if self.is_enabled():
			# Called when component becomes active – do initial setup
			self._add_listeners()
			
		else:
			self._remove_listeners()

		return super().on_enabled_changed()
	

	################################################################################################################


	@override
	def disconnect(self):

		log_info("TransportComponent.disconnect() called.")

		if self.is_enabled():
			self._remove_listeners()

		super().disconnect()


	################################################################################################################


	def _create_controls(self):

		log_verbose("TransportComponent._create_controls() called.")

		self._play_button     = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.PLAY)
		self._stop_button     = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.STOP)
		self._record_button   = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.RECORD)
		self._loop_button     = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.LOOP)
		self._rewind_button   = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.REWIND)
		self._fforward_button = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.FORWARD)
		self._tempo_msb       = EncoderElement(MIDI_CC_TYPE,H.MIDI_CHANNEL, M.DATA1.TEMPO_MSB, MidiMap.MapMode.absolute)
		self._tempo_lsb       = EncoderElement(MIDI_CC_TYPE,H.MIDI_CHANNEL, M.DATA1.TEMPO_LSB, MidiMap.MapMode.absolute)


	################################################################################################################


	def _add_listeners(self):

		log_verbose("TransportComponent._add_control_listeners() called.")

		self._play_button.add_value_listener(self._on_play_pressed)
		self._stop_button.add_value_listener(self._on_stop_pressed)
		self._record_button.add_value_listener(self._on_rec_pressed)
		self._loop_button.add_value_listener(self._on_loop_pressed)
		self._rewind_button.add_value_listener(self._on_rewind_pressed)
		self._fforward_button.add_value_listener(self._on_fforward_pressed)
		self._tempo_lsb.add_value_listener(self._on_tempo_lsb)
		self._tempo_msb.add_value_listener(self._on_tempo_msb)

		self.song.add_record_mode_listener(self._on_record_mode_changed)


	################################################################################################################


	def _remove_listeners(self):

		log_verbose("TransportComponent._remove_control_listeners() called.")

		self._play_button.remove_value_listener(self._on_play_pressed)
		self._stop_button.remove_value_listener(self._on_stop_pressed)
		self._record_button.remove_value_listener(self._on_rec_pressed)
		self._loop_button.remove_value_listener(self._on_loop_pressed)
		self._rewind_button.remove_value_listener(self._on_rewind_pressed)
		self._fforward_button.remove_value_listener(self._on_fforward_pressed)
		self._tempo_msb.remove_value_listener(self._on_tempo_msb)
		self._tempo_lsb.remove_value_listener(self._on_tempo_lsb)

		self.song.remove_record_mode_listener(self._on_record_mode_changed)


	################################################################################################################


	def _on_play_pressed(self, value):
		
		log(f"*->TransportComponent._on_play_pressed({value}) called.", category=LogCategory.LISTENER)

		if value == H.BUTTON_PRESSED:
			self.song.start_playing()


	################################################################################################################


	def _on_stop_pressed(self, value):

		log(f"*->TransportComponent._on_stop_pressed({value}) called.", category=LogCategory.LISTENER)
		
		if value == H.BUTTON_PRESSED and self.song:
			self.song.stop_playing()


	################################################################################################################


	def _on_fforward_pressed(self, value):

		log(f"*->TransportComponent._on_fforward_pressed({value}) called.", category=LogCategory.LISTENER)

		if value == H.BUTTON_PRESSED:
			self._fforward_button_down = True
			self._rewind_button_down = False
			self._rewind_hold_start_time = False
			self._fforward_hold_start_time = time.time()
			self.song.jump_by(self.FORW_REW_JUMP_BY_AMOUNT)
		else:
			self._fforward_button_down = False
			self._fforward_hold_start_time = None
			

	################################################################################################################


	def _on_loop_pressed(self, value):

		log(f"*->TransportComponent._on_loop_pressed({value}) called.", category=LogCategory.LISTENER)

		if value == H.BUTTON_PRESSED:
			self.song.loop = not self.song.loop


	################################################################################################################


	def _on_record_mode_changed(self):

		log(f"*->TransportComponent._on_record_mode_changed() called.", category=LogCategory.LISTENER)

		# update the record button light. T.RECORD is the same for the button in one way and the light in the other.
		self.control_surface.send_midi((M.STATUS + H.MIDI_CHANNEL, T.RECORD, self.song.record_mode))
							 

	################################################################################################################


	def _on_rec_pressed(self, value):

		log(f"*->TransportComponent._on_rec_pressed({value}) called.", category=LogCategory.LISTENER)

		# here we could contextually either record the song or record a clip if a clip is selected and in clip view.

		if value == H.BUTTON_PRESSED:
			self.song.record_mode = not self.song.record_mode

		
	################################################################################################################


	def _on_rewind_pressed(self, value):

		log(f"*->TransportComponent._on_rewind_pressed({value}) called.", category=LogCategory.LISTENER)

		if value == H.BUTTON_PRESSED:
			
			self._rewind_button_down = True
			self._fforward_button_down = False
			self._fforward_hold_start_time = False
			self._rewind_hold_start_time = time.time()   # Start timing
			self.song.jump_by(-self.FORW_REW_JUMP_BY_AMOUNT)

		else:
			self._rewind_button_down = False
			self._rewind_hold_start_time = None          # Reset timer


	################################################################################################################


	def _on_tempo_msb(self, value):
		log_listener_callback(value)
		self._tempo_msb_value = value


	################################################################################################################



	def _on_tempo_lsb(self, value):
		log_listener_callback(value)
		if hasattr(self, '_tempo_msb_value'):
			tempo = (self._tempo_msb_value << 7) | value
			self.song.tempo = tempo


	################################################################################################################


	@override
	def update(self):
		"""Called periodically - handles rewind/forward hold behavior."""

		if not self.is_enabled():
			return

		log_info("TransportComponent.update() called.")

		# Make sure record mode button is set right.
		self.control_surface.send_midi((M.STATUS + H.MIDI_CHANNEL, T.RECORD, self.song.record_mode))

		super().update()


	################################################################################################################


	def update_tick(self):
		"""This is what we will call from update_display as we require regular updates for ff and rw."""

		if not self.is_enabled():
			return

		log("DisplayComponent.update_tick() called.")

		# Helper to get jump multiplier based on elapsed time
		def get_multiplier(elapsed):
			if elapsed < 0.25:
				return 0.0
			elif elapsed < 1.0:
				return 1
			elif elapsed < 1.5:
				return 2
			elif elapsed < 2.0:
				return 3
			elif elapsed < 3.0:
				return 4
			elif elapsed < 4.0:
				return 8
			elif elapsed < 6.0:
				return 12
			elif elapsed < 8.0:
				return 20
			else:
				return 30

		# Handle rewind
		if self._rewind_button_down and self._rewind_hold_start_time is not None:
			elapsed = time.time() - self._rewind_hold_start_time
			multiplier = get_multiplier(elapsed)
			jump_amount = self.FORW_REW_JUMP_BY_AMOUNT * multiplier
			self.song.jump_by(-jump_amount)
			
		# Handle forward
		elif self._fforward_button_down and self._fforward_hold_start_time is not None:
			elapsed = time.time() - self._fforward_hold_start_time
			multiplier = get_multiplier(elapsed)
			jump_amount = self.FORW_REW_JUMP_BY_AMOUNT * multiplier
			self.song.jump_by(jump_amount)
			


	################################################################################################################


####################################################################################################################
####################################################################################################################

