####################################################################################################################
# Source Generated with Decompyle++
# File: RemoteSL.pyc (Python 3.11)
####################################################################################################################

"""Main Remote SL controller script for Ableton Live."""
import Live


#import MidiRemoteScript <-- Unnecessary unused.
from _Generic.util import DeviceAppointer


from ableton.v2.control_surface import ControlSurface, Component, Layer, Skin, MIDI_CC_TYPE, MIDI_NOTE_TYPE
# from ableton.v2.control_surface.components import TransportComponent
#from _Framework.TransportComponent import TransportComponent
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from .consts import *
from .Components.TransportComponent import TransportComponent
from .Components.DisplayComponent import DisplayComponent
from .EffectController import EffectController
from .Components.MixerComponent import MixerController

from .myLogger import *




####################################################################################################################


class RemoteSL(ControlSurface):
	"""Wire the display, effect, and mixer controllers together."""


	################################################################################################################


	def __init__(self, c_instance):
		"""Initialise the Remote SL controller and its child components."""

		log("RemoteSL.__init__() called.")
		#self._device_initialized = False

		super(RemoteSL, self).__init__(c_instance)

		#self._c_instance = c_instance
		self._handle = c_instance.handle() # <--- Remove when fully upgraded

		with self.component_guard():
			
			#self.hardware_controls = {} #dictionary to hold controls.
			# At some point we should mebbe split _components from controllers????
			#self._components : list[Component | EffectController | MixerController | DisplayComponent] = []
			#transport = TransportComponent()

			log("\t|----->Setting up free buttons...")

			self._fx_buttons = [ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, cc) for cc in Constants.Effect.NAVIGATION + Constants.Effect.SELECT_BUTTONS + Constants.Effect.UPPER_BUTTONS]

			# self._ts_buttons = [ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, cc) for cc in Constants.Transport.ALL]

			self._mx_buttons = [ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, cc) for cc in Constants.Mixer.NAVIGATION+ Constants.Mixer.SELECT_BUTTONS + Constants.Mixer.BUTTONS_TOP_ROW + Constants.Mixer.BUTTONS_BOTTOM_ROW]

			log("\t|----->Done setting up free buttons.")


			log("\t|----->Adding listeners...")
			for button in list(self._fx_buttons + self._mx_buttons):
				button.add_value_listener(self.on_button_pressed_cb, identify_sender=True)
			log("\t|----->Done adding listeners.")

			log("\t|----->Building DisplayController...")
			self._display_component = DisplayComponent(self)

			log("\t|----->Building EffectController...")
			self._effect_controller = EffectController(self)

			log("\t|----->Building MixerController...")
			self._mixer_controller = MixerController(self)

			self._transport_component = TransportComponent(self)

			self._transport_component.set_enabled(True)
			self._display_component.set_enabled(True)

			# Listener to detect new track pressed.
			self.song.view.add_selected_track_listener(self.clean_track_switch_hook)
		
			self._components.append(self._effect_controller)
			self._components.append(self._mixer_controller)
			#self._components.append(self._display_component)
		

		#self._register_component(self._tranport_component) # <-- Not needed when in guard.
		self._update_hardware_delay = -1

		self._device_appointer = DeviceAppointer(
			song=(self.song),
			appointed_device_setter = self.set_appointed_device,
		)

		# Only show message after initialization complete as it relies on c_instance...
		self.show_message("RemoteSL_Customised script loaded.") # <- Shows message in bottom bar.

		# generate_stub(Live.Track, "./Track.pyi")
		# generate_stub(ControlSurface, "./ControlSurface.pyi")
		#self.set_enabled(True)
		#self._device_initialized = True


		log(f"num components: {len(self._components)}")
		for comp in self._components:
			log(comp)


		log("<-----Returning from RemoteSL.__init__().")



	################################################################################################################


	# definitely no an override.
	def get_application(self):
		"""Expose the Live application object."""
		
		return Live.Application.get_application()


	################################################################################################################
 
 

	@override
	def build_midi_map(self, midi_map_handle):
		"""Build the MIDI mappings for all controller components."""
		
		log(f"*->RemoteSL.build_midi_map({midi_map_handle}) called.")

		try:
			super(RemoteSL, self).build_midi_map(midi_map_handle)

		except Exception as e:
			log(f"****Error in super().build_midi_map({midi_map_handle}): {e}.")

		#if not self._automap_has_control:

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

		# --- THE ABSOLUTE LOGIC GATE ---
		# Check if our effect controller exists and if a lock is currently active
		if hasattr(self, '_effect_controller') and self._effect_controller is not None:
			
			# IF LOCKED IS TRUE: Exit immediately to protect your active screen text from being wiped!
			if getattr(self._effect_controller, '_assigned_device_is_locked', False) == True:
				log("HOOK ABORT: Controller is locked. Protecting active parameter text rows.")
				return None
		# --------------------------------

		# Fetch what track your mouse just clicked in real-time
		track = self.song.view.selected_track
		
		# If the track lane has absolutely no plugins or devices loaded on it
		if track is None or len(track.devices) == 0:
			log("CLEAN SWAP ENGINE: Blank track caught. Wiping screen names...")
			
			# --- CRITICAL MEMORY RESET FOR THE ASSIGNED DEVICE ---
			if hasattr(self, '_effect_controller') and self._effect_controller is not None:
				# Force the parent container to drop its cached plugin reference
				self._effect_controller._assigned_device = None
				
				# Disconnect the 16 virtual channel strips so they let go of old macros
				if hasattr(self._effect_controller, '_strips'):
					for strip in self._effect_controller._strips:
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

		for button in list(self._fx_buttons + self._mx_buttons): # + self._ts_buttons
			button.remove_value_listener(self.on_button_pressed_cb)

		self.send_midi(Constants.SysEx.ALL_LEDS_OFF)
		self.send_midi(Constants.SysEx.GOODBYE)
		self._device_initialized = False
		
		super(RemoteSL, self).disconnect()


	################################################################################################################

	#def _add_child(self, component):
		#component._set_enabled_recursive(self.is_enabled()) # <- Later could enable here????
		#self._components.append(component)
		#return component


	def add_children(self, *a):
		# With this we can pass this as the parent of all of the child components and gain access to song and parent.
		# is it canonical?  maybe we would be better passing it as controller.
		pass
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
		self._effect_controller.lock_to_device(device)


	################################################################################################################


	# def map_transport_buttons(self):
	# 	"""Maps the transport buttons the modern way."""
		
	# 	log("map_transport_buttons() called.")

	# 	self._transport.layer = Layer(
	# 		play_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.PLAY),
	# 		stop_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.STOP),
	# 		record_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.RECORD),
	# 		loop_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.LOOP),
	# 		seek_backward_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.REWIND),
	# 		seek_forward_button=ButtonElement(True, MIDI_CC_TYPE, Constants.Hardware.MIDI_CHANNEL, Constants.Transport.FORWARD)
	# 	)
		

	# 	self._components.append(self._transport)


	################################################################################################################


	def on_button_pressed_cb(self, value, sender: ButtonElement):
		"""Callback to recieve button presses."""
		
		log(f"*->on_button_pressed_cb({value}, {sender}) called.")

		cc_or_note_no = sender.original_identifier()
		midi_channel = sender.original_channel()
		if midi_channel is None: return
		
		msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)

		# log(f"Button Pressed. {midi_bytes} {value} {sender}")

		status_byte = 0

		if msg_type == MIDI_CC_TYPE:
			status_byte = 176 + int(midi_channel)

		elif msg_type == MIDI_NOTE_TYPE:
			status_byte = 144 + midi_channel
		
		self.receive_midi((status_byte, cc_or_note_no, value))

			
################################################################################################################


# This is now called by registered button listeners.
	@override
	def receive_midi(self, midi_bytes):
		"""Route incoming MIDI messages to the effect or mixer controller."""

		log(f"RemoteSL.receive_midi({str(midi_bytes)}) called.")

		if not midi_bytes:
			log("...returning none.")
			return None

		status = midi_bytes[0] & 240
		log(f"\t----->status={status}")

		if status in (Constants.MIDI.NOTE_ON, Constants.MIDI.NOTE_OFF):
			
			note = midi_bytes[1]
			velocity = midi_bytes[2]
			
			if note in Constants.Effect.DRUM_PADS:
				self._effect_controller.receive_midi_note(note, velocity)
				return None
			
			log("unknown MIDI message %s" % str(midi_bytes))
			return None


		if status == Constants.MIDI.STATUS:
			
			cc_no = midi_bytes[1]
			cc_value = midi_bytes[2]

			log("\t----->status byte received.")

			if cc_no in Constants.Effect.ALL:
				self._effect_controller.receive_midi_cc(cc_no, cc_value)
				return None
			
			if cc_no in Constants.Mixer.ALL:
				self._mixer_controller.receive_midi_cc(cc_no, cc_value)
				return None

			if cc_no in Constants.Transport.ALL:
				self._tranport_component.handle_cc(cc_no, cc_value)
				return None
				
			log("unknown MIDI message %s" % str(midi_bytes))
			return None


		if status == 240:
			
			log("status == 240")

			if len(midi_bytes) == 13 or midi_bytes[1:4] == (0, 32, 41) or midi_bytes[8] == Constants.Hardware.ABLETON_PID or midi_bytes[10] == 1:
				
				#self._automap_has_control = midi_bytes[11] == 0
				#support_mkII = midi_bytes[6] * 100 + midi_bytes[7] >= 1800
				
				#if not self._automap_has_control:
				self.send_midi(Constants.SysEx.ALL_LEDS_OFF)
				
				for component in self._components:
					
					#component.set_support_mkII(support_mkII)
					#if not self._automap_has_control:
					component.refresh_state()
				
					self.request_rebuild_midi_map()
				return None

		print("unknown MIDI message %s" % str(midi_bytes))
		super(RemoteSL, self).receive_midi(midi_bytes)

		return None
	

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
		"""Send MIDI bytes to the Live C instance when automap is not controlling them."""

		found = False
		for i,val in enumerate(midi_event_bytes):
			if i != 0 and i != len(midi_event_bytes) - 1 and val > 0x7f:
				found = True

		if found:
			log(f"Error bad MIDI message sent: {midi_event_bytes}")
		
		self._send_midi(midi_event_bytes)


	################################################################################################################


	def set_appointed_device(self, device):
		"""Native callback fired by DeviceAppointer when track focus shifts."""

		log(f"RemoteSL.set_appointed_device({device}) called.")
		log(f"\t|----->REMOTE SL APPCON: DeviceAppointer passed device -> {str(device)}")
		
		# Ensure this points directly to your active effect controller instance
		if self._effect_controller is not None:
			self._effect_controller.set_appointed_device(device)
		else:
			log("***ERROR***: RemoteSL._effect_controller is None.")

		log(f"<-----Returning from set_appointed_device({device})")



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

		self._effect_controller.unlock_from_device(device)


	################################################################################################################


	@override
	def update_display(self):
		"""Update the display and decrement the hardware refresh timer."""

		#log(f"RemoteSL.update_display() called.") <---- not logged as on a timer.

		if self._update_hardware_delay > 0:
			self._update_hardware_delay -= 1
			if self._update_hardware_delay == 0:
				self.update_hardware()

		for component in self._components:
			if hasattr(component, "update_display"): # <----Transport components don't have update display.
				component.update_display()

		self._transport_component.update()


	################################################################################################################


	def update_hardware(self):
		"""Initialise the hardware and refresh each controller component."""

		log("RemoteSL._update_hardware() called.")

		self.send_midi(Constants.SysEx.WELCOME)
		for component in self._components:
				if hasattr(component, "refresh_state"): # to check as i don't know if all have refresh state.
					component.refresh_state()



####################################################################################################################
####################################################################################################################
