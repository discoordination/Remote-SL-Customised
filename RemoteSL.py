####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
####################################################################################################################
# RemoteSL.py
####################################################################################################################


# TODO: Test if you actually need to monitor appointed device in RemoteSL or whether it is sufficient to monitor it in EffectComponent only.
# !   |-> Pretty much done... it's running without either Appointer or onTracksChanged now.
# FIXME: Switching on while live active doesn't bring up the controller. <--- Have tried to fix but i think it is impossible.

from Live.Application import Application as LiveApplication
from Live.Track import Track
from Live.Device import Device
from Live.Application import get_application
from Live import MidiMap

from _Generic.util import DeviceAppointer

from ableton.v2.control_surface import ControlSurface, Component, Layer, Skin, MIDI_CC_TYPE, MIDI_NOTE_TYPE
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement, SysexElement

#from ableton.v2.base.task import wait, sequence, run

import sys
from typing import Type, cast, Final

# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from .consts import Constants, MIDI, M, SYX
from .Components.TransportComponent import TransportComponent
from .Components.DisplayComponent import DisplayComponent, DISPLAY, ROW
from .Components.EffectComponent import EffectComponent
from .Components.MixerComponent import MixerComponent

from .RemoteSL_Logger import *

from .tracker import CALL_COUNTS, ALL_METHODS

####################################################################################################################


class RemoteSL(ControlSurface):
	"""Wire the display, effect, and mixer controllers together."""


	################################################################################################################

	_device_appointer       : DeviceAppointer
	_drumPad_select_button  : ButtonElement
	_drumPad_buttons        : list[ButtonElement]
	_handle                 : int
	_sysex_receiver         : SysexElement

	#* _display_component 	   : DisplayComponent
	#* _effect_component  	   : EffectComponent
	#* _mixer_component   	   : MixerComponent
	#* _transport_component    : TransportComponent

	################################################################################################################


	def __init__(self, c_instance):
		"""Initialise the Remote SL controller and its child components."""

		log_info("RemoteSL.__init__() called.")

		super(RemoteSL, self).__init__(c_instance)
		self.set_enabled(False)

		self._handle = cast(int, c_instance.handle()) # <--- Remove when fully upgraded

		#self._register_component(self._tranport_component) # <-- Not needed when in guard.
		#self._update_hardware_delay = -1 # -1 is an initalizer??? <---- Not used now.

		# self._device_appointer = DeviceAppointer(
		# 	song=(self.song),
		# 	appointed_device_setter = self._on_appointed_device_changed,
		# )

		with self.component_guard():

			self._sysex_receiver = SysexElement(sysex_identifier=SYX.RECEIVE_SYSEX_HEADER)
			self._sysex_receiver.add_value_listener(self._on_sysex_received)
			# Listener to detect new track pressed.
			#self.song.view.add_selected_track_listener(self.clean_track_switch_hook) #TODO: Move to Effect Component.

			self._create_controls()
			self._add_listeners()

			# self._online_status_listener = ButtonElement(
			# 	True, MIDI_CC_TYPE, 0xBF, 0x67
			# )
			# self._online_status_listener.add_value_listener(self._on_online_status_changed)

			log_verbose("\t|----->Building DisplayComponent...")
			self._display_component = DisplayComponent(self)

			log_verbose("\t|----->Building EffectController...")
			self._effect_component = EffectComponent(self)

			log_verbose("\t|----->Building MixerController...")
			self._mixer_component = MixerComponent(self)
			
			log_verbose("\t|----->Building TransportComponent...")
			self._transport_component = TransportComponent(self)


		self.show_message("RemoteSL_Customised script loaded.") # <- Shows message in bottom bar.
		self.enable()

		# Do some quick checks.
		if self._enabled == False:
			log_error("Error: RemoteSL must be enabled.")
			#raise ValueError(f"Error: Object {self} is not enabled when it should be.")

		if len(self.components) != 4:
			log_error(f"Error: num components is {len(self._components)} when it should be 4.")
			raise ValueError(f"Error: num components is {len(self._components)} when it should be 4.")

		for comp in self.components:
			log_verbose(f"{comp.name}  is_enabled: {comp.is_enabled()}  is_explicit_enabled: {comp.is_enabled(True)}")
	
			#if comp._enabled == False:
			#	raise ValueError(f"Error: Object {comp} is not enabled when it should be.")

		log_verbose("<-----Returning from RemoteSL.__init__().")


	################################################################################################################


	def _add_listeners(self):

		for i in range(8):
			self._drumPad_buttons[i].add_value_listener(self._on_drum_pad_action, identify_sender = True)

		self._drumPad_select_button.add_value_listener(self._on_drum_pad_select_pressed)

		self.song.add_tempo_listener(self._on_tempo_changed)



	################################################################################################################

 

	@override
	def build_midi_map(self, midi_map_handle: int):
		"""Build the MIDI mappings for all controller components."""

		if not self.is_enabled():
			return

		log_info(f"*->RemoteSL.build_midi_map({midi_map_handle}) called.")

		try:
			super().build_midi_map(midi_map_handle)

		except Exception as e:
			log_error(f"Error in super().build_midi_map({midi_map_handle}): {e}.")

		try:
			for component in self._components:
				if hasattr(component, "build_midi_map"): # <-- transport components don't build midi maps.
					component.build_midi_map(midi_map_handle) #(self.handle(), midi_map_handle)
		except Exception as e:
			log_error(f"in component.build_midi_map({midi_map_handle}): {e}")

		
		self.set_pad_translations(Constants.PAD_TRANSLATION)


	################################################################################################################


	@override
	def can_lock_to_devices(self):
		"""Allow the controller to lock to a device."""
		return True


	################################################################################################################


	# def clean_track_switch_hook(self):
	# 	"""	# --- CHANNELS MONITOR: INSTANT BLANK TRACK SCREEN WIPER ---"""

	# 	log_info(f"RemoteSL.clean_track_switch_hook_called() called.")

	# 	# --- THE ABSOLUTE LOGIC GATE ---
	# 	# Check if our effect controller exists and if a lock is currently active
	# 	if hasattr(self, '_effect_controller') and self._effect_component is not None:
			
	# 		# IF LOCKED IS TRUE: Exit immediately to protect your active screen text from being wiped!
	# 		if getattr(self._effect_component, '_assigned_device_is_locked', False) == True:
	# 			log("HOOK ABORT: Controller is locked. Protecting active parameter text rows.")
	# 			return None
	# 	# --------------------------------

	# 	# Fetch what track your mouse just clicked in real-time
	# 	track = self.song.view.selected_track
		
	# 	# If the track lane has absolutely no plugins or devices loaded on it
	# 	if track is None or len(track.devices) == 0:
	# 		log("CLEAN SWAP ENGINE: Blank track caught. Wiping screen names...")
			
	# 		# --- CRITICAL MEMORY RESET FOR THE ASSIGNED DEVICE ---
	# 		if hasattr(self, '_effect_controller') and self._effect_component is not None:
	# 			# Force the parent container to drop its cached plugin reference
	# 			self._effect_component._assigned_device = None
				
	# 			# Disconnect the 16 virtual channel strips so they let go of old macros
	# 			if hasattr(self._effect_component, '_strips'):
	# 				for strip in self._effect_component._strips:
	# 					strip.assigned_parameter = None
	# 		# ----------------------------------------------------
			
	# 		# --- THE MISSING BLUE HAND FLUSH INSTRUCTION ---
	# 		# We MUST explicitly tell Ableton's C++ core to rebuild its hardware mapping tables 
	# 		# when hitting an empty track, otherwise it natively freezes your old VST maps in memory!
	# 		self.request_rebuild_midi_map()
	# 		# -----------------------------------------------


	# 		# Explicitly pass your original prompt text directly to the display engine
	# 		#fallback_names = ["Please select a Device in Live to edit it..."]
	# 		#fallback_params = [None for _ in range(16)]
			
	# 		#self._display_component.setup_display_for_params(DISPLAY.LEFT, fallback_names, fallback_params)
	# 		self._display_component.clear_display_row(ROW.BL)
	# 		self._display_component.write_display_rows("Please select a device in Live to edit it...", ROW.TL)

	# 	log_verbose("|<-----Returning from clean_track_switch_hook()")
			  

	################################################################################################################


	def _create_controls(self):

		self._drumPad_select_button = ButtonElement(True, MIDI_CC_TYPE, M.CHANNEL, Constants.Effect.SELECT_DRUM_PAD)
		self._drumPad_buttons = [ButtonElement(True, MIDI_NOTE_TYPE, M.CHANNEL, Constants.Effect.DRUM_PAD_BASE_NOTE + i) for i in range(8)]


	################################################################################################################


	# def connect_script_instances(self, instanciated_scripts):
	# 	"""
	# 	Natively called by Ableton to connect multiple remote scripts.
	# 	Crucial for setting up the underlying control registries!
	# 	"""
	# 	log("RemoteSL.connect_script_instances() called.")
	# 	super(RemoteSL, self).connect_script_instances(instanciated_scripts)


	################################################################################################################
	
	
	def disable(self):
		"""Disables the device hence also disabling all components."""

		log_info("RemoteSL.disable() called.")

		self.turn_off_all_leds()
		self.send_midi(SYX.GOODBYE)

		# Setting self to false is sufficient to switch off all other components.
		self.set_enabled(False)

		# for component in self.components: #? I don't believe i have to manually call this.
		# 	component.set_enabled(False)



	################################################################################################################


	@override
	def disconnect(self):
		"""Disconnect all components and send the shutdown MIDI messages."""

		log_info("RemoteSL.disconnect() called.")

		self._sysex_receiver.remove_value_listener(self._on_sysex_received)
		#self._device_appointer.disconnect()
		#self.song.view.remove_selected_track_listener(self.clean_track_switch_hook)

		self._remove_listeners()

		if self.is_enabled():
			self.disable()

		super(RemoteSL, self).disconnect()

		self.send_midi(Constants.SysEx.GOODBYE) # After super so it's done after clear screen.

		#-------------------------------------------------------------------------
		## LOGGING FUNCTIONS ##
		
		# Find uncalled methods
		called = set(CALL_COUNTS.keys())
		uncalled = ALL_METHODS - called
		if uncalled:
			log_info("=== Uncalled Methods ===")
			for method in sorted(uncalled):
				log(f"  {method}")
			log_info("=========================")
		else:
			log_info("All tracked methods were called at least once.")

		# Optionally, also log call counts for all methods:
		log_info("=== Call Counts ===")
		for method, count in sorted(CALL_COUNTS.items(), key=lambda x: x[1], reverse=True):
			log_info(f"  {method}: {count}")
		log_info("===================")

		#-------------------------------------------------------------------------
		log_verbose(f"<-----Returning from RemoteSL.disconnect()")


	################################################################################################################


	def enable(self):
		"""Enables the device"""

		log_info("RemoteSL.enable() called.")

		self.set_enabled(True)
		#self.refresh_state() # <---- Do i need to do this?


		for component in self.components:
			component.set_enabled(True)

		
	################################################################################################################


	def get_application(self) -> LiveApplication:
		"""Expose the Live application object."""
		
		return cast(LiveApplication, get_application())


	################################################################################################################
	

	def handle(self):
		"""Get the c_instance handle... Should be refactored out at some point."""
		return self._handle


	################################################################################################################


	def is_enabled(self):
		return self._enabled


	################################################################################################################


	# I believe this is unused.  Also without underscore it shadows an inherited function.
	@override
	def lock_to_device(self, device):
		"""Lock the effect controller to the given device."""
		
		log_info(f"RemoteSL._lock_to_device({device}) called.")

		super(RemoteSL, self).lock_to_device(device)
		self._effect_component._lock_to_device(device)


	################################################################################################################


	def _on_appointed_device_changed(self, device):
		"""Native callback fired by DeviceAppointer when track focus shifts."""
		pass
		log_info(f"RemoteSL._on_appointed_device_changed({device}) called.", LogCategory.LISTENER)
		log_listener_callback(None, device)
		log(f"\t|----->REMOTE SL APPCON: DeviceAppointer passed device -> {str(device)}")
		
		# Ensure this points directly to your active effect controller instance
		#if self._effect_component is not None:
		# self._effect_component._set_appointed_device(device)
		#else:
		#	log("***ERROR***: RemoteSL._effect_controller is None.")

		log_verbose(f"<-----Returning from _on_appointed_device_changed({device})", LogCategory.LISTENER)


	################################################################################################################


	def _on_drum_pad_select_pressed(self, value):
		log(f"_on_btn_sel_dpads_pressed({value}) called.", category=LogCategory.LISTENER)
		if value:

			self.strobe_leds()
			self.send_midi((M.START_BYTE, Constants.Effect.SELECT_DRUM_PAD, 1))
		else:
			self.send_midi((M.START_BYTE, Constants.Effect.SELECT_DRUM_PAD, 0))


	################################################################################################################


	def _on_drum_pad_action(self, value, sender):
		log(f"DrumPad pressed: value: {value}, sender: {sender}", category=LogCategory.LISTENER)


	################################################################################################################


	# def _on_online_status_changed(self, value): #TODIO: Remove
	# 	"""Doesn't really give us anything new"""
	# 	log_info(f"Online status CC received: value={value}", category=LogCategory.LISTENER)
	# 	if value == 1:
	# 		log_verbose("Online status: Device connected.")
	# 		self._device_connected = True
	# 		if not self.is_enabled():
	# 			self.enable()
	# 	else:
	# 		log_verbose("Online status: Device disconnected.")
	# 		self._device_connected = False
	# 		if self.is_enabled():
	# 			self.disable()


	################################################################################################################


	def _on_sysex_received(self, message_data):

		hex_str = ', '.join(f'{b:02X}' for b in message_data)
		log_info(f"RemoteSL._on_sysex_received({hex_str}) called.", category=LogCategory.LISTENER)

		# The length of data is partially decided by the sysex filter string setup in the listener.
		# Everything in the string is disgarded and everything after is kept apart from the final byte.
		# I receive version and beta because these may vary depending on the device.
		if not len(message_data) == 6:
			log_warning("Received strange sysex message so skipping.")
			return

		version = message_data[0]
		beta = message_data[1]
		template = message_data[2]
		_ = message_data[3] # This is the blank.
		cmd = message_data[4] # the command type.
		data = message_data[5] # the value leaving or coming.

		if template == SYX.TEMPL.ABLTN[0]:

			if cmd == SYX.CMD.START_END[0]: # A start/end command.

				if data == 1:
					log_verbose("Returning to ableton template. Enabling.")
					self.enable()
		
				else:
					log_verbose("Template change sysex message detected. Disabling.")
					self.disable()

		else:
			log_verbose(f"SYSEX: Other sysex message received: {hex_str}")

				
	################################################################################################################

	
	# @override
	# def port_settings_changed(self):
	# 	log_info("RemoteSL.port_settings_changed() called.")
	# 	return super().port_settings_changed()


	################################################################################################################


	def _on_tempo_changed(self):

		self._display_component.show_timed_message(f"bpm: {self.song.tempo}", 2.0, True, ROW.TL, ROW.TR) 

		# It's impossible to set the remotesl tempo via midi message... 
	
		# log(f"RemoteSL._tempo_changed() called. New tempo: {self.song.tempo}bpm.")

		# # Convert tempo to 14-bit value (20-320 BPM range)
		# newTempo = int(round(self.song.tempo))

		# # Clamp to valid range
		# newTempo = max(20, min(320, newTempo))

		# lsb = newTempo & 0x7F
		# msb = (newTempo >> 7) & 0x7F

		# # Send on Automap channel (channel 16, status byte 0xBF)
		# # CC 94 = MSB, CC 95 = LSB

		# for ch in range(8):
		# 	self.send_midi((0xb0 + ch, 0x5e, msb))   # MSB
		# 	self.send_midi((0xb0 + ch, 0x5f, lsb))   # LSB


	################################################################################################################


	@override
	def refresh_state(self):
		"""Trigger a refresh of the controller hardware state."""

		if not self.is_enabled():
			return
		
		log_info("*->RemoteSL.refresh_state() called.")
		#self.schedule_message(4, self.update_hardware)
		#self.send_midi(Constants.SysEx.WELCOME) <--- Done in enable
		self._display_component.set_refresh_displays()

		super(RemoteSL, self).refresh_state() # This calls update.

		log_verbose("<-----Returning from RemoteSL.refresh_state().")


	################################################################################################################


	def _remove_listeners(self):
				
		[drumPad.remove_value_listener(self._on_drum_pad_action) for drumPad in self._drumPad_buttons]
		self._drumPad_select_button.remove_value_listener(self._on_drum_pad_select_pressed)

		self.song.remove_tempo_listener(self._on_tempo_changed)


	################################################################################################################


	@override
	def request_rebuild_midi_map(self):
		"""Request that Live rebuild the current MIDI map."""

		if not self.is_enabled():
			return

		log("RemoteSL.request_rebuild_midi_map() called.")
		super(RemoteSL, self).request_rebuild_midi_map()


	################################################################################################################


	# def restore_bank(self, bank):
	# 	"""Restore the effect bank selection."""
	# 	self._effect_controller.restore_bank(bank)


	################################################################################################################


	def send_midi(self, midi_event_bytes : tuple[int, ...]):
		"""Send MIDI bytes."""

		log_midi("OUT", midi_event_bytes)

		# check for bad midi bytes.
		bad = False

		for i, val in enumerate(midi_event_bytes):
			if i != 0 and i != len(midi_event_bytes) - 1 and val > 0x7f:
				bad = True

		if midi_event_bytes[0] in (M.CC, M.NOTE_ON, M.NOTE_OFF):
			if len(midi_event_bytes) > 3:
				bad = True

		if bad:
			log_error(f"Bad MIDI message sent: {midi_event_bytes}")
		
		self._send_midi(midi_event_bytes)


	################################################################################################################


	def suggest_input_port(self):
		"""Return the suggested input port name."""
		
		return "RemoteSL"


	################################################################################################################


	# Overrides base class... currently not used i think.
	@override
	def suggest_map_mode(self, cc_no, channel):
		"""Return the recommended MIDI map mode for a CC number."""
		
		#super(RemoteSL, self).suggest_map_mode(cc_no, channel)

		if cc_no in Constants.Effect.ENCODERS:
			return MidiMap.MapMode.relative_smooth_signed_bit
		return MidiMap.MapMode.absolute
	

	################################################################################################################


	def suggest_output_port(self):
		"""Return the suggested output port name."""

		return "RemoteSL"


	################################################################################################################


	@override
	def supports_pad_translation(self):
		"""Enable pad translation support."""

		return True


	################################################################################################################


	def turn_off_all_leds(self):
		for led in Constants.ALL_LEDS:
			self.send_midi((M.START_BYTE, led, 0))


	################################################################################################################


	def strobe_leds(self):

		def _flash(count):
			if count <= 0:
				self.update()
				return
			for led in Constants.ALL_LEDS:
				self.send_midi((M.START_BYTE, led, 1))
				self.schedule_message(1, lambda led=led: self.send_midi((M.START_BYTE, led, 0)))

			self.schedule_message(2, lambda: _flash(count - 1))
		
		_flash(6)


	################################################################################################################


	@override
	def unlock_from_device(self, device):
		"""Unlock the effect controller from the given device."""

		log_info(f"RemoteSL.unlock_from_device({device}) called.")

		super().unlock_from_device(device)
				
		self._effect_component._unlock_from_device(device)


	################################################################################################################


	@override
	def update(self):

		if not self.is_enabled():
			return
		
		log_info("*->RemoteSL.update() called.")

		super().update() # <--- Calls all other updates.


	################################################################################################################


	@override
	def update_display(self):
		"""Update the display and decrement the hardware refresh timer. Called on a timer by the ableton engine."""

		# No ticks sent when disabled.
		if not self.is_enabled():
			return

		log(f"RemoteSL.update_display() called.")

		# So any component that has an update_tick method registers for regular ticks!
		for component in self.components:
			if hasattr(component, 'update_tick'):
				component.update_tick()

		super().update_display()



####################################################################################################################
####################################################################################################################



	# def on_button_pressed_cb(self, value, sender: ButtonElement):
	# 	"""Callback to recieve button presses."""
		
	# 	log(f"*->on_button_pressed_cb({value}, {sender}) called.")

	# 	cc_or_note_no = sender.original_identifier()
	# 	midi_channel = sender.original_channel()

	# 	if midi_channel is None: return
		
	# 	msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)
	# 	status_byte = 0

	# 	if msg_type == MIDI_CC_TYPE:
	# 		status_byte = 176 + int(midi_channel)

	# 	elif msg_type == MIDI_NOTE_TYPE:
	# 		status_byte = 144 + midi_channel
		
	# 	self.receive_midi((status_byte, cc_or_note_no, value))

			
################################################################################################################


	# # This is now called by registered button listeners.
	@override
	def receive_midi(self, midi_bytes):
		"""Route incoming MIDI messages to the effect or mixer controller."""

		log_warning("=== receive_midi CALLED ===")  # ← THIS WILL TELL YOU IF IT'S BEING CALLED
		log_midi("IN", midi_bytes)

		return

		if not midi_bytes: # Why??? Does this ever happen?  Should i remove this line.
			log_error("Error: ...receive_mid() blank midi message received.")
			return None

		#log_midi("IN", midi_bytes)

		msg_type = midi_bytes[0] & 0xf0
		# 1111 0000 is going to give you the top 4 bytes of mid_bytes 0.

		#log(f"\t----->status = {bin(status)}")

		# if it's a midi note on or midi note off.
		if msg_type in (Constants.MIDI.NOTE_ON, Constants.MIDI.NOTE_OFF):
			
			note = midi_bytes[1]
			velocity = midi_bytes[2]
			
			if note in Constants.Effect.DRUM_PADS:
				# send drum pad note to effect controller.
				self._effect_component.receive_midi_note(note, velocity)
				return None
			
			log_warning("unknown MIDI message %s" % str(midi_bytes))
			return None

		# if it's a midi status update.
		if msg_type == Constants.MIDI.CC:
			
			data1 = midi_bytes[1]
			data2 = midi_bytes[2]

			if data1 == Constants.MIDI.DATA1.TEMPO_MSB:
				self._tempo_msb = data2
				return

			elif data1 == Constants.MIDI.DATA1.TEMPO_LSB:
				tempo_lsb = data2
				self.song.tempo = (self._tempo_msb << 7) | tempo_lsb
				log(f"Sending midi tempo change {(self._tempo_msb << 7) | tempo_lsb}")
				return
			
			log_warning("unknown MIDI message %s" % str(midi_bytes))
			return None


		# It's a sysex message.
		if msg_type == Constants.MIDI.SYSEX:
			
			log(f"\t|----->Received a sysex message.")

			if (    len(midi_bytes) == 13 or 
	   				midi_bytes[1:4] == (0, 32, 41) or
					  midi_bytes[8] == Constants.Hardware.ABLETON_PID or 
					 midi_bytes[10] == 1
				):
				
				log_warning(f"\t|----->message: {midi_bytes} has passed the strange tests and is being processed.")

				self.send_midi(MIDI.ALL_LEDS_OFF)
				
				for component in self.components:
					component.refresh_state()

				self.request_rebuild_midi_map()

				return None

			else:
				log_warning("Unknown SYSEX message received.")
			

		log_warning("unknown MIDI message %s" % str(midi_bytes))
		super(RemoteSL, self).receive_midi(midi_bytes)

		return None
	

	################################################################################################################


	# def toggle_lock(self):
	# 	"""Delegate lock toggling to the Live C instance."""

	# 	log("RemoteSL.toggle_lock() called.")
	# 	self.toggle_lock()

	################################################################################################################


	# def instance_identifier(self):
	# 	"""Return the Live instance identifier."""
	# 	return self._c_instance.instance_identifier()


	################################################################################################################
