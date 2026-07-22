####################################################################################################################
# Source Generated with Decompyle++
# File: EffectController.pyc (Python 3.11)
####################################################################################################################


"""Effect-section controller logic for the Remote SL script."""
from __future__ import annotations

#from past.utils import old_div // <--- old python division not needed.

import Live as Live


#from .consts import *
from .consts import Constants
from .RemoteSLComponent import RemoteSLComponent
from .myLogger import *

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
    from typing import override
else:
    def override(func):
        return func

import time # To debounce the double button press.


####################################################################################################################

class EffectController(RemoteSLComponent):
	"""Handle effect-device selection, bank navigation, and parameter mapping."""


	def __init__(self, remote_sl_parent, display_controller):
		"""Initialise the controller state for the effect section."""

		RemoteSLComponent.__init__(self, remote_sl_parent)
		
		log("EffectController.__init__() called.")

		self._parent = remote_sl_parent # ref. to the owning RemoteSL object.
		self._display_controller = display_controller # ref. to the display.
		
		self._last_selected_track = None
		self._blank_prompt_is_drawn = False

		# --- DYNAMIC DISPLAY STATE TRACKING ---
		self._current_display_row = "pots" # Defaults to pots on startup
		# --------------------------------------

		self._assigned_device_is_locked : bool = False
		self._assigned_device = None
		self._bank : int = 0
		self._display_page_index : int = 0
		self._show_bank : bool = False

		self._lock_popup_ticks : int = 0

		# 1. Create the 16 strips in memory FIRST
		self._strips : list[EffectChannelStrip] = [EffectChannelStrip(self) for _ in range(16)]
		
		# 2. Trigger the dynamic functions LAST once all data structures exist
		self.change_assigned_device(self._parent.song.appointed_device)
		#self.reassign_strips() is called in change_assigned_device

		log("<-----Returning from EffectController.__init__().")



	################################################################################################################


	@override
	def disconnect(self):
		"""Disconnect the effect controller from the currently assigned device."""

		log("EffectController.disconnect() called")
			
		self.change_assigned_device(None)


	################################################################################################################


	@override
	def update_display(self):
		"""Fires continuously on Ableton's background frame clock to monitor device state."""
		
		# --- FIX: THE ABSOLUTE UPDATE DISPLAY LOCK ENVELOPE ---
		# If the controller is locked, we completely freeze the parameter tracking view!
		if getattr(self, '_assigned_device_is_locked', False) == True:
			
			# Monitor if the locked device was physically deleted from the session set
			try:
				if self._assigned_device is None or not self._assigned_device.canonical_parent:
					raise Exception("Device deleted")
			except Exception:
				log("LOCK BREAK: Locked device was physically deleted! Releasing control maps...")
				self._assigned_device_is_locked = False
				self.unlock_from_device(self._assigned_device)
				self._assigned_device = self._parent.song.appointed_device
				self.change_assigned_device(self._assigned_device)
				
			# If the device is alive and locked, EXIT IMMEDIATELY.
			# This blocks the empty track lane check below from ever executing!
			return None
		
		# ------------------------------------------------------

		# Fetch exactly what device Ableton's viewport highlights right now
		current_track_device = self.song.view.selected_track.view.selected_device
		
		# --- CHANNELS MONITOR BALANCED RE-SYNC GUARD (Runs ONLY when unlocked) ---
		if current_track_device is None and self._assigned_device is not None:
			log("POLLING ENGINE: Empty track lane detected. Resetting references...")
			self._assigned_device = None
			for strip in self._strips:
				strip.assigned_parameter = None
			self.reassign_strips(force_rebuild=True)
			return None
			
		if current_track_device is None and self._assigned_device is None:
			return None
		# ------------------------------------------------------------------------
		
		
		moved_strip_index = None

		for strip_index, strip in enumerate(self._strips):
			param = strip.assigned_parameter
			if param is not None:
				current_val = param.value
				
				# Check if the value shifted since the last frame scan
				if hasattr(strip, '_last_value') and strip._last_value is not None and current_val != strip._last_value:
					strip._last_value = current_val
					moved_strip_index = strip_index
					break
				
				strip._last_value = current_val


		# Update the screen text ONLY if a physical hand movement row shift actually happened
		if moved_strip_index is not None:
			new_row = "pots" if moved_strip_index < 8 else "encoders"
			
			if not hasattr(self, '_current_display_row'):
				self._current_display_row = "pots"
				
			if self._current_display_row != new_row:
				self._current_display_row = new_row
				
				# --- SYNC THE VIRTUAL PAGE INDEX BASED ON ACTIVE ROW FLIP ---
				if not hasattr(self, '_display_page_index'):
					self._display_page_index = 0
				
				# If we are on the first 16-parameter block, align the page number
				if self._bank == 0:
					self._display_page_index = 0 if new_row == "pots" else 1
				# -------------------------------------------------------------
				
				# Update text only, skip the MIDI map layout reconstruction!
				self.reassign_strips(force_rebuild=False)


	################################################################################################################


	def receive_midi_cc(self, cc_no, cc_value):
		"""Route incoming CC events to the correct effect-control handler."""

		log(f"EffectController.receive_midi_cc({cc_no}, {cc_value}) called.")

		# --- THE ABSOLUTE GHOST MOVEMENT KILL SWITCH ---
		# If no device is currently assigned to the controller (empty track state), 
		# completely discard all incoming knob and encoder turns at the gate!
		# This stops broken channel strip memory references from manually tweaking your old plugins.
		if self._assigned_device is None:
			log("GHOST GUARD: Discarded knob movement because track is empty.")
			return None
		# -----------------------------------------------

		if cc_no in Constants.Effect.NAVIGATION:
			self.__handle_page_up_down_ccs(cc_no, cc_value)
			return None
		
		if cc_no in Constants.Effect.SELECT_BUTTONS:
			self.__handle_select_button_ccs(cc_no, cc_value)
			return None
		
		if cc_no in Constants.Effect.UPPER_BUTTONS:
			strip = self._strips[cc_no - Constants.Effect.UPPER_BUTTON_BASE]
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				strip.on_button_pressed()
			return None
		
		if cc_no in Constants.Effect.POTS:
			# Let Live take ownership of the pot row for device-parameter mapping.
			return None
		
		if cc_no in Constants.Effect.ENCODERS:
			return None
		
		if cc_no in Constants.Effect.LOWER_BUTTONS:
			return None


	################################################################################################################


	def receive_midi_note(self, note, velocity):
		"""Handle note events from the drum-pad row for the effect section."""

		log("receive_midi_note() called.")
		if note in Constants.Effect.DRUM_PADS:
			return None

		return None


	################################################################################################################


	def _on_selected_track_changed(self):
		"""Fires instantly whenever you select a different track channel lane in Live."""

		try:
			track = self.song.view.selected_track
			
			# --- ABSOLUTE EMPTY TRACK VALIDATION CHECK ---
			# Look directly inside the track's physical device list array
			if track is None or len(track.devices) == 0:
				log("TRACK CHANGED LOGIC: Track has 0 physical devices. Forcing clear...")
				self.change_assigned_device(None)
				return None
			# ---------------------------------------------

			# If the track actually has devices, safely extract the highlighted target
			current_device = track.view.selected_device
			log(f"TRACK CHANGED LOGIC: Active device is now -> {str(current_device)}")
			
			self.change_assigned_device(current_device)
			
		except Exception as e:
			log(f"TRACK CHANGED ERROR: {str(e)}")



	################################################################################################################


	@override
	def build_midi_map(self, midi_map_handle):
		"""Create Live MIDI mappings for the effect controller strips."""
		
		log(f"EffectController.build_midi_map({midi_map_handle}) called.")

		# needs_takeover = True # never changed easier just to send false. 

		# COMBINE BOTH ROWS INTO ONE LIST OF 16 ITEMS TO FIX INDEX ERROR
		# This gives us indices 0-7 for pots, and 8-15 for encoders
		combined_ccs = list(Constants.Effect.POTS + Constants.Effect.ENCODERS)

		for strip_index, strip in enumerate(self._strips):
			
			# Pull CC numbers from the 16-item list safely
			primary_cc_no = combined_ccs[strip_index]

			#log(f"STRIP LOGGER: Strip Index {strip_index} -> assigned to CC {primary_cc_no}")
			
			parameter = strip.assigned_parameter

			if parameter is not None:

				log(f"\t|----->MAPPING: Strip {strip_index} (CC {primary_cc_no}) to parameter: {parameter.name}")
				
				# ASSIGN MAP MODE DYNAMICALLY BASED ON THE ROW
				if strip_index < 8:
					map_mode = Live.MidiMap.MapMode.absolute # Pots (0-7) are absolute
				else:
					map_mode = Live.MidiMap.MapMode.relative_smooth_signed_bit # Encoders (8-15) are relative
				
				Live.MidiMap.map_midi_cc(
					midi_map_handle,
					parameter,
					Constants.Hardware.MIDI_CHANNEL,
					primary_cc_no,
					map_mode,
					False, # needs_takeover
				)

				# if self.support_mkII():
					
				# 	feedback_rule = Live.MidiMap.CCFeedbackRule()
					
				# 	# Feedback indices (0-7) must map cleanly back to hardware feedback ccs
				# 	feedback_index = strip_index if strip_index < 8 else (strip_index - 8)
				# 	feedback_rule.cc_no = fx_encoder_feedback_ccs[feedback_index]
				# 	feedback_rule.channel = SL_MIDI_CHANNEL
				# 	feedback_rule.delay_in_ms = 0

				# 	feedback_rule.cc_value_map = tuple(
				# 		int(1.5 + (float(index) / 127.0) * 10.0) for index in range(128)
				# 	)
				# 	ring_mode_value = FX_RING_VOL_VALUE

				# 	if parameter is not None:
			
				# 		try:
				# 			# If the parameter center zero balance matches a bipolar layout (like Pan)
				# 			if getattr(parameter, 'min', 0.0) == -1.0 * getattr(parameter, 'max', 0.0):
				# 				ring_mode_value = FX_RING_PAN_VALUE
				# 			# If the parameter snaps to discrete steps (like On/Off or Choice lists)
				# 			elif getattr(parameter, 'is_quantized', False):
				# 				ring_mode_value = FX_RING_SIN_VALUE
				# 		except Exception as e:
				# 			log(f"STRIP ENGINE: Safe parameter check exception -> {str(e)}")
					
			
				# 	# Only send LED rings if dealing with encoder row feedback positions
				# 	if strip_index >= 8:
				# 		self.send_midi((self.cc_status_byte(), fx_encoder_led_mode_ccs[feedback_index], ring_mode_value))
						
				# 	Live.MidiMap.map_midi_cc_with_feedback_map(
				# 		midi_map_handle,
				# 		parameter,
				# 		SL_MIDI_CHANNEL,
				# 		primary_cc_no,
				# 		map_mode,
				# 		feedback_rule,
				# 		False, # needs_takeover
				# 	)
				# 	Live.MidiMap.send_feedback_for_parameter(midi_map_handle, parameter)
				# 	continue

				continue
			
			else:
				log(f"\t|----->MAPPING FAILED: Strip {strip_index} (CC {primary_cc_no}) has NO assigned parameter (None)!")

			# if self.support_mkII():
			# 	feedback_index = strip_index if strip_index < 8 else (strip_index - 8)
			# 	self.send_midi((self.cc_status_byte(), fx_encoder_led_mode_ccs[feedback_index], 0))
			# 	self.send_midi((self.cc_status_byte(), fx_encoder_feedback_ccs[feedback_index], 0))

			#Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, SL_MIDI_CHANNEL, primary_cc_no)
			pass
			
		# --- FIX: THE ABSOLUTE REBUILD TEXT SYNC GATE ---
		# Ableton just ran its mapping sweeps! Force our layout text processor to re-slice 
		# the fresh parameter names and push them straight into the display variables!
		# We set force_rebuild=False so it only refreshes the text names behind the scene 
		# without triggering a recursive C++ mapping loop.
		log("\t|----->MAPPING REBUILD: Now calling reassign strips...")
		self.reassign_strips(force_rebuild=False)
		# ------------------------------------------------

		# for cc_no in fx_forwarded_ccs:
		# 	Live.MidiMap.forward_midi_cc(self._parent.handle(), midi_map_handle, SL_MIDI_CHANNEL, cc_no)

		# for note in Constants.Effect.DRUM_PAD_ROW:
		# 	Live.MidiMap.forward_midi_note(self._parent.handle() , midi_map_handle, MIDI.SL_CHANNEL, note)

		log(f"<-----Returning from EffectController.build_midi_map({midi_map_handle}).")



	################################################################################################################


	@override
	def refresh_state(self):
		
		log("EffectController.refresh_state() called.")
		
		self.__update_select_row_leds()
		self.reassign_strips()


	################################################################################################################


	def reassign_strips(self, force_rebuild=True):
		
		log(f"EffectController.__reassign_strips(force_rebuild={force_rebuild}) called.")
		
		page_up_value = Constants.Hardware.BUTTON_RELEASED
		page_down_value = Constants.Hardware.BUTTON_RELEASED
		device = self._assigned_device


		if device is not None:
			
			log("Device valid...")
			self._blank_prompt_is_drawn = False

			param_index = 0
			param_names = []
			parameters = []

			for strip in self._strips:
				
				param = None
				name = ""
				new_index = param_index + self._bank * 16

				device_parameters = device.parameters[1:]

				if new_index < len(device_parameters):
					param = device_parameters[new_index]
				
				if param:
					name = param.name

				strip.assigned_parameter = param
				parameters.append(param)
				param_names.append(name)
				param_index += 1

			if self._bank > 0:
				page_down_value = Constants.Hardware.BUTTON_PRESSED

			if self._bank + 1 < self.__number_of_parameter_banks():
				page_up_value = Constants.Hardware.BUTTON_PRESSED

			self.report_bank()

			# --- FIX: DYNAMIC RE-SLICING BASED ON ACTIVE DISPLAY ROW ---
			# Check if the tracking variable exists (or initialize it on the fly)
			if not hasattr(self, '_current_display_row'):
				self._current_display_row = "pots"

			if self._current_display_row == "pots":
				# Left Screen gets items 0-7 (Pots)
				active_names = param_names[:8]
				active_params = parameters[:8]
			else:
				# Left Screen gets items 8-15 (Encoders)
				active_names = param_names[8:]
				active_params = parameters[8:]


			self._display_controller.setup_left_display(active_names, active_params)


		else:
			# This is for if no device is selected.

			for strip in self._strips:
				strip.assigned_parameter = None

			log("CLEARING SCREEN: Caching original single-string text prompt...")
			
			# Save a pure 1-item text string array inside the display controller variables
			param_names = ["Please select a Device in Live to edit it..."]
			parameters = [None for _ in range(8)]
			
			self._display_controller.setup_left_display(param_names, parameters)


		# Wrap this line so it only fires when explicitly requested
		if force_rebuild:
			self.request_rebuild_midi_map() # <--- suspicious as rebuild_midi_map calls this some of the time.


		# if self.support_mkII():
		# 	log("*** ERROR *** I should not be seeing mkii code...")
		# 	self.send_midi((self.cc_status_byte(), FX_DISPLAY_PAGE_DOWN, page_down_value))
		# 	self.send_midi((self.cc_status_byte(), FX_DISPLAY_PAGE_UP, page_up_value))

		# 	for cc_no in fx_upper_button_row_ccs:
		# 		self.send_midi((self.cc_status_byte(), cc_no, CC_VAL_BUTTON_RELEASED))


		log(f"<-----Returning from EffectController.__reassign_strips(force_rebuild={force_rebuild}).")


	################################################################################################################



	def __handle_row_display_switch(self, moving_strip):
		"""Calculate which row was moved and dynamically sync the virtual display page index."""

		log(f"EffectController.__handle_row_display_switch() called.")

		try:
			# Find where this moving strip sits inside our array list of 16 targets
			strip_index = self._strips.index(moving_strip)
			
			# Decide what view option to flip to
			new_row = "pots" if strip_index < 8 else "encoders"
			
			if self._current_display_row != new_row:
				self._current_display_row = new_row
				
				# --- CRITICAL TRACKING SYNC FOR PHYSICAL TOUCHES ---
				# Ensure variables exist
				if not hasattr(self, '_bank'):
					self._bank = 0
				
				# Convert the current bank position and row focus into the absolute page index.
				# Every bank controls 16 items (2 pages). Pots are even pages, Encoders are odd pages.
				if new_row == "pots":
					self._display_page_index = self._bank * 2
				else:
					self._display_page_index = (self._bank * 2) + 1
					
				log(f"TOUCH SENSOR: Flipped to {new_row}. Virtual Page Index synced to -> {self._display_page_index}")
				# ----------------------------------------------------
				
				# Call text reassign with force_rebuild=False!
				# Touching a knob should NEVER cause a violent C++ MIDI mapping teardown lag dropout.
				self.reassign_strips(force_rebuild=False)
				

		except Exception as e:
			log(f"TOUCH ENGINE ERROR: {str(e)}")


	################################################################################################################


	def __handle_page_up_down_ccs(self, cc_no, cc_value):
		"""Handle physical banking buttons to toggle display rows before swapping MIDI maps."""
	
		# Only process the command when the user physically presses the button down
		if cc_value != Constants.Hardware.BUTTON_PRESSED:
			return None

		if self._assigned_device is None:
			return None

		device_parameters = self._assigned_device.parameters[1:]

		# Calculate the total number of 8-parameter display pages available
		total_pages = len(device_parameters) + 7 // 8

		# Make sure our tracking page variable exists in memory
		if not hasattr(self, '_display_page_index'):
			self._display_page_index = 0

		# --- CASE A: PAGE UP PRESSED ---
		if cc_no == Constants.Effect.PAGE_UP:
			if self._display_page_index + 1 < total_pages:
				self._display_page_index += 1
				log(f"PAGE BUTTON: Pressed Up. Virtual Display Page is now -> {self._display_page_index}")
				
				# Math Rule: A hard MIDI map layout rewrite is required only when entering an EVEN page index!
				# Page 0->1 (Same MIDI maps, view shifts to encoders)
				# Page 1->2 (New MIDI maps!, view resets to pots)
				if self._display_page_index % 2 == 0:
					self._bank += 1
					self._current_display_row = "pots"
					self.reassign_strips(force_rebuild=True) # Full C++ MIDI map rebuild
				else:
					self._current_display_row = "encoders"
					self.reassign_strips(force_rebuild=False) # TEXT SWAP ONLY, lightning fast

		# --- CASE B: PAGE DOWN PRESSED ---
		elif cc_no == Constants.Effect.PAGE_DOWN:
			if self._display_page_index > 0:
				self._display_page_index -= 1
				log(f"PAGE BUTTON: Pressed Down. Virtual Display Page is now -> {self._display_page_index}")
				
				# Math Rule: Moving backward, a hard MIDI map layout rewrite is required only when dropping out of an EVEN page index
				# Page 2->1 (New MIDI maps!, view shifts to encoders)
				# Page 1->0 (Same MIDI maps, view resets to pots)
				if (self._display_page_index + 1) % 2 == 0:
					self._bank -= 1
					self._current_display_row = "encoders"
					self.reassign_strips(force_rebuild=True) # Full C++ MIDI map rebuild
				else:
					self._current_display_row = "pots"
					self.reassign_strips(force_rebuild=False) # TEXT SWAP ONLY, lightning fast



	################################################################################################################


	def __handle_select_button_ccs(self, cc_no, cc_value):
		
		log(f"__handle_select_button_ccs({cc_no}, {cc_value}) called.")
		
		if cc_no == Constants.Effect.SELECT_TOP_BUTTON_ROW:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
											
								# Debounce double-broadcast hardware port packets
				current_time = time.time()
				if hasattr(self, '_last_lock_press_time') and (current_time - self._last_lock_press_time) < 0.1:
					log("DEBOUNCE BLOCK: Successfully dropped physical hardware double-broadcast packet.")
					return None
				self._last_lock_press_time = current_time
				
				# 1. READ the status BEFORE changing anything
				was_already_locked = getattr(self, '_assigned_device_is_locked', False)
				
				log("LOCK BUTTON PRESSED: Handing toggle request to root script...")
			
				# 2. Fire the native toggle command in Live via the master script
				self._parent.toggle_lock()
				
				# 3. Engage the 2-second visual hold timer (10 frame ticks)
				self._lock_popup_ticks = 10
				
				# 4. Route state updates purely through your balanced helpers
				if not was_already_locked:
					log("LOCK ROUTE: Engaging lock_to_device...")
					# This now sets the flag to True and updates select LEDs natively
					self.lock_to_device(self.song.appointed_device)
					
					self._display_controller.show_timed_message("Device Locked!", duration_seconds=2.0)	

				else:
					log("LOCK ROUTE: Engaging unlock_from_device...")
					current_device = self._assigned_device
					
					# 1. Turn off the hardware button LEDs natively
					self.unlock_from_device(current_device)
					
					# 2. Hard reset variables cleanly on a manual unlock
					self._assigned_device_is_locked = False 
					self._display_page_index = 0
					self._current_display_row = "pots"
					
					# 3. Pull whatever device Ableton is focusing on right now
					live_appointed_device = self.song.appointed_device
					
					# --- FIX: UPDATE THE MEMORY POINTER DIRECTLY WITHOUT CORRUPTING CACHES ---
					# Set the internal pointer to the new instrument
					self._assigned_device = live_appointed_device
					
					# Run text reassignment with force_rebuild=False so it updates the text names 
					# array behind the scenes without triggering a destructive C++ MIDI rebuild!
					self.reassign_strips(force_rebuild=False)
					# ------------------------------------------------------------------------
					
					# 4. Flash your centralized timed message popup for exactly 2 seconds
					self._display_controller.show_timed_message("Device Unlocked", duration_seconds=2.0)


				return None


		if cc_no == Constants.Effect.SELECT_ENCODER:
			
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				
				new_index = min(
					len(self.song.scenes) - 1,
					max(0, list(self.song.scenes).index(self.song.view.selected_scene) - 1),
				)
				self.song.view.selected_scene = self.song.scenes[new_index]
			return None

		if cc_no == Constants.Effect.SELECT_BOTTOM_BUTTON_ROW:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				new_index = min(
					len(self.song.scenes) - 1,
					max(0, list(self.song.scenes).index(self.song.view.selected_scene) + 1),
				)
				self.song.view.selected_scene = self.song.scenes[new_index]
			return None

		if cc_no == Constants.Effect.POTS:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self.song.view.selected_scene.fire_as_selected()
			return None

		if cc_no == Constants.Effect.SELECT_DRUM_PAD:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self.song.stop_all_clips()
			return None


	################################################################################################################


	def __update_select_row_leds(self):
		
		if self._assigned_device_is_locked:
			self.send_midi((self.cc_status_byte(), Constants.Effect.SELECT_TOP_BUTTON_ROW, Constants.Hardware.BUTTON_PRESSED))
		else:
			self.send_midi((self.cc_status_byte(), Constants.Effect.SELECT_BOTTOM_BUTTON_ROW, Constants.Hardware.BUTTON_RELEASED))


	################################################################################################################


	def lock_to_device(self, device):
		"""Natively handle the hardware feedback loop when locking."""

		if device:
			# --- FIX: ASSIGN THE LOCAL FLAG STATUS NATIVELY HERE ---
			self._assigned_device_is_locked = True
			# --------------------------------------------------------
			self.__update_select_row_leds()


	################################################################################################################


	def unlock_from_device(self, device):
		"""Natively handle the hardware feedback loop when unlocking."""

		if device and device == self._assigned_device:
			
			self._assigned_device_is_locked = False
			self.__update_select_row_leds()
			if self.song.appointed_device != self._assigned_device:
				self.reassign_strips()


	################################################################################################################


	def report_bank(self):
		
		log("EffectController.__report_bank() called.")
		
		if self._show_bank:
			self._show_bank = False
			self.show_bank_select("Bank" + str(self._bank + 1))


	################################################################################################################


	def show_bank_select(self, bank_name):
		
		log(f"EffectController.__show_bank_select({bank_name}) called.")

		if self._assigned_device:
			self._parent.show_message(
				str(self._assigned_device.name + " Bank: " + bank_name)
			)


	###############################################################################################################


	def restore_bank(self, bank):
		
		log("EffectController.restore_bank() called.")

		if self._assigned_device_is_locked:
			self._bank = bank
			self.reassign_strips()


	###############################################################################################################


	def set_appointed_device(self, device):
		"""Public receiver function called by RemoteSL.py."""

		log(f"EffectController.set_appointed_device(): Received device pointer -> {str(device)}")

		# This isn't called if the device is locked and you drop a new device on the locked channel.

		# If the user has locked the controller, ignore any dynamic focus shifts from Ableton.
		if getattr(self, '_assigned_device_is_locked', False):
			log("LOCK ENGINE GUARD: Blocked appointed_device focus shift to maintain hardware lock.")
			return None

		self.change_assigned_device(device)


	################################################################################################################


	def change_assigned_device(self, device):
		
		"""Safely update active device references across track focus shifts."""
		log(f"EffectController.__change_assigned_device({str(device)}) called.")
		
		# Set the master reference pointer to the device object handed down by Live
		self._assigned_device = device
		
		# Reset view layout page markers ONLY if we are browsing tracks dynamically
		if not getattr(self, '_assigned_device_is_locked', False):
			self._bank = 0
			self._display_page_index = 0
			self._current_display_row = "pots"
		
		# Force a single rebuild of the layouts safely (force_rebuild=True maps MIDI)
		self.reassign_strips(force_rebuild=True)

		log("<-----Returning from change_assigned_device().")


	################################################################################################################


	def __parameter_list_of_device_changed(self):
		
		log("EffectController.__parameter_list_of_device_changed() called.")
		self.reassign_strips()


	################################################################################################################


	def __number_of_parameter_banks(self):
		
		log("EffectController.__number_of_parameter_banks() called.")

		result = 0

		if self._assigned_device is not None:
			param_count = len(self._assigned_device.parameters)
			
			# Use double-slash '//' for clean integer floor division
			result = (param_count // 8) + int(param_count % 8 != 0)
		
		return result


	################################################################################################################





####################################################################################################################
####################################################################################################################




class EffectChannelStrip(object):
	"""Represent a single strip in the effect controller layout."""


	################################################################################################################

	def __init__(self, mixer_controller_parent):
		
		self._mixer_controller : EffectController = mixer_controller_parent
		self._assigned_parameter: Live.DeviceParameter.DeviceParameter | None = None
		self._last_value : float = 0.0

	################################################################################################################


	@property
	def last_value(self) -> float:
		return self._last_value
	
	@last_value.setter
	def last_value(self, last_value: float):
		self._last_value = last_value


	################################################################################################################


	@property
	def assigned_parameter(self) -> Live.DeviceParameter.DeviceParameter | None:
		"""Getter: Safely returns the currently bound device parameter or None."""
		return self._assigned_parameter
	
	@assigned_parameter.setter
	def assigned_parameter(self, parameter: Live.DeviceParameter.DeviceParameter | None):
		"""Setter: Safely updates the internal parameter reference reference."""
		self._assigned_parameter = parameter

		# # --- Step 1: REMOVE CLEANUP ---
		# # If this strip is already watching a parameter, kill the listener before letting go
		# if self._assigned_parameter is not None:
		# 	if self._assigned_parameter.value_has_listener(self._on_any_knob_moved):
		# 		self._assigned_parameter.remove_value_listener(self._on_any_knob_moved)

		# Assign the new parameter target (can be a real parameter or None)

		# # --- Step 2: ATTACH NEW LISTENER ---
		# # If the new parameter is valid, attach our localized listener hook
		# if self._assigned_parameter is not None:
		# 	if not self._assigned_parameter.value_has_listener(self._on_any_knob_moved):
		# 		self._assigned_parameter.add_value_listener(self._on_any_knob_moved)


	################################################################################################################


	def on_button_pressed(self):
		
		log("EffectChannelStrip.on_button_pressed() called.")

		if self._assigned_parameter and self._assigned_parameter.is_enabled:
			
			if self._assigned_parameter.is_quantized:
				
				if self._assigned_parameter.value + 1 > self._assigned_parameter.max:
					
					self._assigned_parameter.value = self._assigned_parameter.min

				else:
					self._assigned_parameter.value += 1
			else:
				self._assigned_parameter.value = self._assigned_parameter.default_value



	################################################################################################################



	def on_encoder_moved(self, cc_value : int):
		
		log(f"EffectChannelStrip.on_encoder_moved({cc_value}) called.")
		
		parameter = self._assigned_parameter
		
		if parameter is None:
			return None

		if not hasattr(parameter, "min") or not hasattr(parameter, "max"):
			return None

		if parameter.max == parameter.min:
			return None

		value_range = float(parameter.max - parameter.min)
		if value_range <= 0:
			return None

		normalized = float(cc_value) / 127.0
		parameter.value = parameter.min + (value_range * normalized)

		if hasattr(parameter, "is_quantized") and parameter.is_quantized:
			parameter.value = round(parameter.value)



####################################################################################################################
####################################################################################################################

