####################################################################################################################
# Source Generated with Decompyle++
# File: RemoteSL.pyc (Python 3.11)
####################################################################################################################

"""Main Remote SL controller script for Ableton Live."""
import Live

from _Generic.util import DeviceAppointer

from ableton.v2.control_surface import ControlSurface, Component, Layer, Skin, MIDI_CC_TYPE, MIDI_NOTE_TYPE
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement

#from ableton.v2.base.task import wait, sequence, run

import sys

# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from .consts import Constants, MIDI, M
from .Components.TransportComponent import TransportComponent
from .Components.DisplayComponent import DisplayComponent, ROW
from .Components.EffectComponent import EffectComponent
from .Components.MixerComponent import MixerComponent

from .myLogger import *

from .tracker import CALL_COUNTS, ALL_METHODS

####################################################################################################################


class RemoteSL(ControlSurface):
	"""Wire the display, effect, and mixer controllers together."""


	################################################################################################################


	def __init__(self, c_instance):
		"""Initialise the Remote SL controller and its child components."""

		log_info("RemoteSL.__init__() called.")

		super(RemoteSL, self).__init__(c_instance)

		self._handle = c_instance.handle() # <--- Remove when fully upgraded

		with self.component_guard():
			
			log("\t|----->Building DisplayComponent...")
			self._display_component = DisplayComponent(self)

			log("\t|----->Building EffectController...")
			self._effect_component = EffectComponent(self)

			log("\t|----->Building MixerController...")
			self._mixer_component = MixerComponent(self)

			log("\t|----->Building TransportComponent...")
			self._transport_component = TransportComponent(self)

			# Listener to detect new track pressed.
			self.song.view.add_selected_track_listener(self.clean_track_switch_hook)
			self.song.add_tempo_listener(self._tempo_changed)
		
		
		for component in self.components:
			component.set_enabled(True)
			#self._register_component

		#self._register_component(self._tranport_component) # <-- Not needed when in guard.
		self._update_hardware_delay = -1 # -1 is an initalizer???

		self._device_appointer = DeviceAppointer(
			song=(self.song),
			appointed_device_setter = self.set_appointed_device,
		)

		# Only show message after initialization complete as it relies on c_instance...
		self.show_message("RemoteSL_Customised script loaded.") # <- Shows message in bottom bar.

		# Do some quick checks.
		if self._enabled == False:
			log_error("Error: RemoteSL must be enabled.")
			raise ValueError(f"Error: Object {self} is not enabled when it should be.")

		if len(self.components) != 4:
			log_error(f"Error: num components is {len(self._components)} when it should be 4.")
			raise ValueError(f"Error: num components is {len(self._components)} when it should be 4.")

		for comp in self.components:
			log(comp)
			#if comp._enabled == False:
			#	raise ValueError(f"Error: Object {comp} is not enabled when it should be.")

		# generate_stub(Live.Track, "./Track.pyi")
		# generate_stub(ControlSurface, "./ControlSurface.pyi")
		#self.set_enabled(True)

		log_info("<-----Returning from RemoteSL.__init__().")


	################################################################################################################


	def _tempo_changed(self):

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


	# definitely not an override.
	def get_application(self):
		"""Expose the Live application object."""
		
		return Live.Application.get_application()


	################################################################################################################
 

	@override
	def build_midi_map(self, midi_map_handle: int):
		"""Build the MIDI mappings for all controller components."""
		
		log(f"*->RemoteSL.build_midi_map({midi_map_handle}) called.")

		try:
			super(RemoteSL, self).build_midi_map(midi_map_handle)

		except Exception as e:
			log_error(f"Error in super().build_midi_map({midi_map_handle}): {e}.")

		try:
			for component in self._components:
				if hasattr(component, "build_midi_map"): # <-- transport components don't build midi maps.
					component.build_midi_map(midi_map_handle) #(self.handle(), midi_map_handle)
		except Exception as e:
			log(f"****Error in component.build_midi_map({midi_map_handle}): {e}")


		self.set_pad_translations(Constants.PAD_TRANSLATION)


	################################################################################################################


	@override
	def can_lock_to_devices(self):
		"""Allow the controller to lock to a device."""
		return True


	################################################################################################################


	def clean_track_switch_hook(self):
		"""	# --- CHANNELS MONITOR: INSTANT BLANK TRACK SCREEN WIPER ---"""

		log(f"RemoteSL.clean_track_switch_hook_called() called.")

		# --- THE ABSOLUTE LOGIC GATE ---
		# Check if our effect controller exists and if a lock is currently active
		if hasattr(self, '_effect_controller') and self._effect_component is not None:
			
			# IF LOCKED IS TRUE: Exit immediately to protect your active screen text from being wiped!
			if getattr(self._effect_component, '_assigned_device_is_locked', False) == True:
				log("HOOK ABORT: Controller is locked. Protecting active parameter text rows.")
				return None
		# --------------------------------

		# Fetch what track your mouse just clicked in real-time
		track = self.song.view.selected_track
		
		# If the track lane has absolutely no plugins or devices loaded on it
		if track is None or len(track.devices) == 0:
			log("CLEAN SWAP ENGINE: Blank track caught. Wiping screen names...")
			
			# --- CRITICAL MEMORY RESET FOR THE ASSIGNED DEVICE ---
			if hasattr(self, '_effect_controller') and self._effect_component is not None:
				# Force the parent container to drop its cached plugin reference
				self._effect_component._assigned_device = None
				
				# Disconnect the 16 virtual channel strips so they let go of old macros
				if hasattr(self._effect_component, '_strips'):
					for strip in self._effect_component._strips:
						strip.assigned_parameter = None
			# ----------------------------------------------------
			
			# --- THE MISSING BLUE HAND FLUSH INSTRUCTION ---
			# We MUST explicitly tell Ableton's C++ core to rebuild its hardware mapping tables 
			# when hitting an empty track, otherwise it natively freezes your old VST maps in memory!
			self.request_rebuild_midi_map()
			# -----------------------------------------------


			# Explicitly pass your original prompt text directly to the display engine
			fallback_names = ["Please select a Device in Live to edit it..."]
			fallback_params = [None for _ in range(16)]
			
			self._display_component.setup_left_display(fallback_names, fallback_params)


	################################################################################################################


	# def connect_script_instances(self, instanciated_scripts):
	# 	"""
	# 	Natively called by Ableton to connect multiple remote scripts.
	# 	Crucial for setting up the underlying control registries!
	# 	"""
	# 	log("RemoteSL.connect_script_instances() called.")
	# 	super(RemoteSL, self).connect_script_instances(instanciated_scripts)


	################################################################################################################


	@override
	def disconnect(self):
		"""Disconnect all components and send the shutdown MIDI messages."""

		log("RemoteSL.disconnect() called.")

		# for component in self._components:
		# 	component.disconnect()

		self._device_appointer.disconnect()

		for component in self.components:
			component.set_enabled(False)

		# for button in list(self._fx_buttons): # + self._mx_buttons): # + self._ts_buttons
		# 	button.remove_value_listener(self.on_button_pressed_cb)

		self.send_midi(MIDI.ALL_LEDS_OFF)
		super(RemoteSL, self).disconnect()
		self.send_midi(Constants.SysEx.GOODBYE) # After super so it's done after clear screen.

		# Find uncalled methods
		called = set(CALL_COUNTS.keys())
		uncalled = ALL_METHODS - called
		if uncalled:
			log("=== Uncalled Methods ===")
			for method in sorted(uncalled):
				log(f"  {method}")
			log("=========================")
		else:
			log("All tracked methods were called at least once.")

		# Optionally, also log call counts for all methods:
		log("=== Call Counts ===")
		for method, count in sorted(CALL_COUNTS.items(), key=lambda x: x[1], reverse=True):
			log(f"  {method}: {count}")
		log("===================")




	################################################################################################################

	#def _add_child(self, component):
		#component._set_enabled_recursive(self.is_enabled()) # <- Later could enable here????
		#self._components.append(component)
		#return component


	#def add_children(self, *a):
		# With this we can pass this as the parent of all of the child components and gain access to song and parent.
		# is it canonical?  maybe we would be better passing it as controller.
		#pass
		##components = list(map(self._add_child, a))
		#if len(components) == 1:
		#	return components[0]
		#return components


	################################################################################################################

	
	def handle(self):
		"""Get the c_instance handle... Should be refactored out at some point."""
		return self._handle


	################################################################################################################


	# def instance_identifier(self):
	# 	"""Return the Live instance identifier."""
	# 	return self._c_instance.instance_identifier()



	################################################################################################################


	# I believe this is unused.  Also without underscore it shadows an inherited function.
	@override
	def lock_to_device(self, device):
		
		log(f"RemoteSL._lock_to_device({device}) called.")

		"""Lock the effect controller to the given device."""
		super(RemoteSL, self).lock_to_device(device)
		self._effect_component._lock_to_device(device)


	################################################################################################################


	def on_button_pressed_cb(self, value, sender: ButtonElement):
		"""Callback to recieve button presses."""
		
		log(f"*->on_button_pressed_cb({value}, {sender}) called.")

		cc_or_note_no = sender.original_identifier()
		midi_channel = sender.original_channel()

		if midi_channel is None: return
		
		msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)
		status_byte = 0

		if msg_type == MIDI_CC_TYPE:
			status_byte = 176 + int(midi_channel)

		elif msg_type == MIDI_NOTE_TYPE:
			status_byte = 144 + midi_channel
		
		self.receive_midi((status_byte, cc_or_note_no, value))

			
################################################################################################################


	# # This is now called by registered button listeners.
	# @override
	# def receive_midi(self, midi_bytes):
	# 	"""Route incoming MIDI messages to the effect or mixer controller."""

	# 	log_info("=== receive_midi CALLED ===")  # ← THIS WILL TELL YOU IF IT'S BEING CALLED
	# 	log_midi("IN", midi_bytes, "RemoteSL")

	# 	if not midi_bytes: # Why??? Does this ever happen?  Should i remove this line.
	# 		log_error("Error: ...receive_mid() blank midi message received.")
	# 		return None

	# 	#log_midi("IN", midi_bytes)

	# 	msg_type = midi_bytes[0] & 0xf0
	# 	# 1111 0000 is going to give you the top 4 bytes of mid_bytes 0.

	# 	#log(f"\t----->status = {bin(status)}")

	# 	# if it's a midi note on or midi note off.
	# 	if msg_type in (Constants.MIDI.NOTE_ON, Constants.MIDI.NOTE_OFF):
			
	# 		note = midi_bytes[1]
	# 		velocity = midi_bytes[2]
			
	# 		if note in Constants.Effect.DRUM_PADS:
	# 			# send drum pad note to effect controller.
	# 			self._effect_component.receive_midi_note(note, velocity)
	# 			return None
			
	# 		log_warning("unknown MIDI message %s" % str(midi_bytes), "RemoteSL")
	# 		return None

	# 	# if it's a midi status update.
	# 	if msg_type == Constants.MIDI.CC:
			
	# 		data1 = midi_bytes[1]
	# 		data2 = midi_bytes[2]

	# 		if data1 == Constants.MIDI.DATA1.TEMPO_MSB:
	# 			self._tempo_msb = data2
	# 			return

	# 		elif data1 == Constants.MIDI.DATA1.TEMPO_LSB:
	# 			tempo_lsb = data2
	# 			self.song.tempo = (self._tempo_msb << 7) | tempo_lsb
	# 			log(f"Sending midi tempo change {(self._tempo_msb << 7) | tempo_lsb}")
	# 			return
			
	# 		log_warning("unknown MIDI message %s" % str(midi_bytes), "RemoteSL")
	# 		return None


	# 	# It's a sysex message.
	# 	if msg_type == Constants.MIDI.SYSEX:
			
	# 		log(f"\t|----->Received a sysex message.")

	# 		if (    len(midi_bytes) == 13 or 
	#    				midi_bytes[1:4] == (0, 32, 41) or
	# 				  midi_bytes[8] == Constants.Hardware.ABLETON_PID or 
	# 				 midi_bytes[10] == 1
	# 			):
				
	# 			log_warning(f"\t|----->message: {midi_bytes} has passed the strange tests and is being processed.")

	# 			self.send_midi(MIDI.ALL_LEDS_OFF)
				
	# 			for component in self.components:
	# 				component.refresh_state()

	# 			self.request_rebuild_midi_map()

	# 			return None

	# 		else:
	# 			log_warning("Unknown SYSEX message received.")
			

	# 	log_warning("unknown MIDI message %s" % str(midi_bytes))
	# 	super(RemoteSL, self).receive_midi(midi_bytes)

	# 	return None
	

	################################################################################################################

	@override
	def refresh_state(self):
		"""Trigger a refresh of the controller hardware state."""

		log("*->RemoteSL.refresh_state() called.")

		self._update_hardware_delay = 5

		log("<-----Returning from RemoteSL.refresh_state().")
		#super(RemoteSL, self).refresh_state() # don't call this now as it requires update().


	################################################################################################################


	@override
	def request_rebuild_midi_map(self):
		"""Request that Live rebuild the current MIDI map."""

		log("RemoteSL.request_rebuild_midi_map() called.")
		super(RemoteSL, self).request_rebuild_midi_map()


	################################################################################################################


	# def restore_bank(self, bank):
	# 	"""Restore the effect bank selection."""
	# 	self._effect_controller.restore_bank(bank)


	################################################################################################################


	def send_midi(self, midi_event_bytes : tuple[int, ...]):
		"""Send MIDI bytes."""

		log_midi("OUT", midi_event_bytes, "RemoteSL")

		# check for bad midi bytes.
		bad = False

		for i, val in enumerate(midi_event_bytes):
			if i != 0 and i != len(midi_event_bytes) - 1 and val > 0x7f:
				bad = True

		if midi_event_bytes[0] in (M.CC, M.NOTE_ON, M.NOTE_OFF):
			if len(midi_event_bytes) > 3:
				bad = True

		if bad:
			log_error(f"Error: bad MIDI message sent: {midi_event_bytes}", "RemoteSL")
		
		self._send_midi(midi_event_bytes)


	################################################################################################################


	def set_appointed_device(self, device):
		"""Native callback fired by DeviceAppointer when track focus shifts."""

		log_info(f"RemoteSL.set_appointed_device({device}) called.")
		log_listener_callback(None, device)
		log(f"\t|----->REMOTE SL APPCON: DeviceAppointer passed device -> {str(device)}")
		
		# Ensure this points directly to your active effect controller instance
		#if self._effect_component is not None:
		# self._effect_component._set_appointed_device(device)
		#else:
		#	log("***ERROR***: RemoteSL._effect_controller is None.")

		log_info(f"<-----Returning from set_appointed_device({device})")



	################################################################################################################


	# def show_message(self, message):
	# 	"""Display a message in Live's UI."""
	# 	self._c_instance.show_message(message)


	################################################################################################################


	# def song(self):
	# 	"""Expose the Live song object."""
	# 	return self._c_instance.song()


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
			return Live.MidiMap.MapMode.relative_smooth_signed_bit
		return Live.MidiMap.MapMode.absolute
	


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


	# def toggle_lock(self):
	# 	"""Delegate lock toggling to the Live C instance."""

	# 	log("RemoteSL.toggle_lock() called.")
	# 	self.toggle_lock()


	################################################################################################################


	@override
	def unlock_from_device(self, device):
		"""Unlock the effect controller from the given device."""

		log(f"RemoteSL.unlock_from_device({device}) called.")

		self._effect_component._unlock_from_device(device)


	################################################################################################################


	@override
	def update_display(self):
		"""Update the display and decrement the hardware refresh timer."""

		#log(f"RemoteSL.update_display() called.") <---- not logged as on a timer.
		super().update_display()

		if self._update_hardware_delay > 0:		# <---- somehwere there is a timer tick for this
			self._update_hardware_delay -= 1
			if self._update_hardware_delay == 0:
				self.update_hardware()


		for component in self.components:
			component.update()


	@override
	def update(self):
		log("*->RemoteSL.update() called.")
		super().update()

	################################################################################################################


	def update_hardware(self):
		"""Initialise the hardware and refresh each controller component."""

		log("RemoteSL.update_hardware() called.")

		self.send_midi(Constants.SysEx.WELCOME)
		
		for component in self.components:
			#TODO: Review if refresh state is necessary or a good idea.	
			if hasattr(component, "refresh_state"): # to check as i don't know if all have refresh state.
				pass
				#component.refresh_state()

		# If you were regularly to call this function then you would need to reset the timer here.
		# Correction the update hardware timer is called in refresh_state() and is set to 5.




	# def send_midi_logged(self, name: str, midi_bytes):
	# 	log(f"MIDI MESSAGE: {name}: {midi_bytes}")
	# 	self.send_midi(midi_bytes)


####################################################################################################################
####################################################################################################################
