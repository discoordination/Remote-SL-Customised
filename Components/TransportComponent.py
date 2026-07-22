####################################################################################################################
# TransportComponent.py
####################################################################################################################


from ableton.v2.control_surface import Component, MIDI_CC_TYPE
from ableton.v2.control_surface.elements import ButtonElement
import time

from ..consts import H, T
from ..myLogger import log

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func


####################################################################################################################


class TransportComponent(Component):

	_play_button: 		ButtonElement
	_stop_button: 		ButtonElement
	_record_button: 	ButtonElement 
	_loop_button: 		ButtonElement
	_rewind_button: 	ButtonElement 
	_fforward_button: 	ButtonElement

	_rewind_button_down : bool = False
	_fforward_button_down : bool = False

	_rewind_hold_start_time = None
	_fforward_hold_start_time = None

	FORW_REW_JUMP_BY_AMOUNT : float = 0.25


	################################################################################################################
	

	def __init__(self, name, parent, *a, **k):

		log(f"TransportComponent.__init__({name},{parent}) called.")

		super().__init__(name=name, *a, **k)

		self._parent = parent
		self._song = parent.song

		self._create_buttons()
		self._add_button_listeners()

		log(f"<-----Returning from TransportController.__init__({name},{parent}).")


	################################################################################################################


	# def on_enabled(self):
		
	# 	log("TransportComponent.on_enabled() called.")
	# 	# Called when component becomes active – do initial setup
		

	# ################################################################################################################


	# def on_disabled(self):
		
	# 	log("TransportComponent.on_disabled() called.")
	# 	# Called when component is disabled – clean up
	# 	# e.g., turn off any LEDs
	

	################################################################################################################


	@override
	def disconnect(self):

		log("TransportComponent.disconnect() called.")

		self._remove_button_listeners()

		super().disconnect()


	################################################################################################################


	def _create_buttons(self):

		log("TransportComponent._create_buttons() called.")

		# Create buttons
		self._play_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.PLAY)
		self._stop_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.STOP)
		self._record_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.RECORD)
		self._loop_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.LOOP)
		self._rewind_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.REWIND)
		self._fforward_button: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, T.FORWARD)	


	################################################################################################################


	def _add_button_listeners(self):

		log("TransportComponent._add_button_listeners() called.")

		# Add button listeners
		self._play_button.add_value_listener(self._on_play_pressed)
		self._stop_button.add_value_listener(self._on_stop_pressed)
		self._record_button.add_value_listener(self._on_rec_pressed)
		self._loop_button.add_value_listener(self._on_loop_pressed)
		self._rewind_button.add_value_listener(self._on_rewind_pressed)
		self._fforward_button.add_value_listener(self._on_fforward_pressed)


	################################################################################################################


	def _remove_button_listeners(self):

		log("TransportComponent._remove_button_listeners() called.")

		# Add button listeners
		self._play_button.remove_value_listener(self._on_play_pressed)
		self._stop_button.remove_value_listener(self._on_stop_pressed)
		self._record_button.remove_value_listener(self._on_rec_pressed)
		self._loop_button.remove_value_listener(self._on_loop_pressed)
		self._rewind_button.remove_value_listener(self._on_rewind_pressed)
		self._fforward_button.remove_value_listener(self._on_fforward_pressed)


	################################################################################################################


	def _on_play_pressed(self, value):
		
		log(f"TransportComponent._on_play_pressed({value}) called.")

		if value == H.BUTTON_PRESSED:
			self._song.start_playing()


	################################################################################################################


	def _on_stop_pressed(self, value):

		log(f"TransportComponent._on_stop_pressed({value}) called.")
		
		if value == H.BUTTON_PRESSED:
			self._song.stop_playing()


	################################################################################################################


	def _on_rewind_pressed(self, value):

		log(f"TransportComponent._on_rewind_pressed({value}) called.")

		if value == H.BUTTON_PRESSED:
			self._rewind_button_down = True
			self._fforward_button_down = False
			self._fforward_hold_start_time = False
			self._rewind_hold_start_time = time.time()   # Start timing
			self._song.jump_by(-self.FORW_REW_JUMP_BY_AMOUNT)
		else:
			self._rewind_button_down = False
			self._rewind_hold_start_time = None          # Reset timer


	################################################################################################################


	def _on_fforward_pressed(self, value):

		log(f"TransportComponent._on_fforward_pressed({value}) called.")

		if value == H.BUTTON_PRESSED:
			self._fforward_button_down = True
			self._rewind_button_down = False
			self._rewind_hold_start_time = False
			self._fforward_hold_start_time = time.time()
			self._song.jump_by(self.FORW_REW_JUMP_BY_AMOUNT)
		else:
			self._fforward_button_down = False
			self._fforward_hold_start_time = None
			


	################################################################################################################


	def _on_rec_pressed(self, value):

		log(f"TransportComponent._on_rec_pressed({value}) called.")

		if value == H.BUTTON_PRESSED:
			self._song.record_mode = not self._song.record_mode


	################################################################################################################


	def _on_loop_pressed(self, value):

		log(f"TransportComponent._on_loop_pressed({value}) called.")
		if value == H.BUTTON_PRESSED:
			self._song.loop = not self._song.loop


	################################################################################################################


	@override
	def update(self):
		"""Called periodically – handles rewind/forward hold behavior."""

		#log("TransportComponent.update() called.")

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
			self._song.jump_by(-jump_amount)

		# Handle forward
		if self._fforward_button_down and self._fforward_hold_start_time is not None:
			elapsed = time.time() - self._fforward_hold_start_time
			multiplier = get_multiplier(elapsed)
			jump_amount = self.FORW_REW_JUMP_BY_AMOUNT * multiplier
			self._song.jump_by(jump_amount)


	################################################################################################################


	# def send_midi(self, midi_bytes):
		
	# 	log("TransportComponent.send_midi() called.")

	# 	if self._parent:
	# 		self._parent._send_midi(midi_bytes)


####################################################################################################################
####################################################################################################################

