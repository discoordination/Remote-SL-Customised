####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
#
# EffectComponent.py
#
####################################################################################################################
####################################################################################################################


# Disabled Functions
# ------------------

# EffectComponent._handle_row_display_switch // Never called.
# EffectComponent._restore_bank // Never called
# EffectComponent._show_bank_select // Never called
# EffectComponent.receive_midi_cc // All done with listeners.
# EffectComponent.receive_midi_note // No midi notes sent.
# EffectComponent.refresh_state // Theoretically called in the midi_cc loop


####################################################################################################################

"""Effect-section controller logic for the Remote SL script."""
from __future__ import annotations

from Live import MidiMap
from Live.Track import Track
from Live.Song import Song
from Live.DeviceParameter import DeviceParameter
from Live.Device import Device

from ableton.v2.control_surface import Component, MIDI_CC_TYPE
from ableton.v2.control_surface.elements import ButtonElement

import time # To debounce the double button press.

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
    from typing import override
else:
    def override(func):
        return func

from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
	from ..RemoteSL import RemoteSL


from ..consts import Constants, H, FX, M
from ..RemoteSL_Logger import log, log_info, log_warning, log_error, log_assignment, log_listener_callback, log_verbose
from .DisplayComponent import DisplayComponent, DISPLAY, ROW


from ..tracker import TrackedMixin


####################################################################################################################


class EffectComponent(Component, TrackedMixin):
	"""Handle effect-device selection, bank navigation, and parameter mapping."""


	################################################################################################################

	#_control_surface           : RemoteSL
	#_display_component         : DisplayComponent

	# ------------- Controls ----------------
	_btn_page_up               : ButtonElement
	_btn_page_down             : ButtonElement
	_btn_sel_encoders          : ButtonElement
	_btn_sel_top_btns          : ButtonElement
	_btn_sel_pots 	           : ButtonElement
	_btn_sel_btm_btns          : ButtonElement
	#._btn_sel_dpads	   : ButtonElement
	
	_buttons_upper_row         : list[ButtonElement]
	_buttons_bottom_row        : list[ButtonElement]

	# --------------------------------------

	_assigned_device           : Device | None
	_locked_device			   : Device | None
	_assigned_device_is_locked : bool
	_bank					   : int
	_current_display_row       : str
	_display_page_index        : int
	_last_lock_press_time      : float
	_last_selected_track       : Track | None
	#_lock_popup_ticks          : int
	_show_bank                 : bool
	_strips                    : list[EffectChannelStrip]


	################################################################################################################


	def __init__(self, control_surface: RemoteSL, name: str = 'EffectComponent', *a, **k) -> None:
		"""Initialise the controller state for the effect section."""

		log_info(f"EffectComponent.__init__({control_surface}, {name}) called.")

		super().__init__(name = name, song = control_surface.song, is_enabled=False, *a, **k)

		self._control_surface : RemoteSL = control_surface # ref. to the owning RemoteSL object.
		self._display_component : DisplayComponent = control_surface._display_component

		self._create_controls()
		
		self._last_selected_track = None

		# --- DYNAMIC DISPLAY STATE TRACKING ---
		self._current_display_row = "pots" # Defaults to pots on startup

		self._assigned_device_is_locked = False
		self._assigned_device = None
		self._locked_device = None
		self._bank = 0
		self._display_page_index = 0
		self._show_bank = False

		#self._lock_popup_ticks = 0

		# 1. Create the 16 strips in memory FIRST
		self._strips = [EffectChannelStrip(self) for _ in range(16)]
		
		#self.reassign_strips() is called in change_assigned_device

		log("<-----Returning from EffectComponent.__init__().")


	################################################################################################################

	@property
	@override
	def song(self) -> Song:
		s = super().song
		assert s is not None
		return s


	################################################################################################################

	@property
	def control_surface(self) -> RemoteSL:
		return self._control_surface

	################################################################################################################


	def _add_listeners(self) -> None:

		self._btn_page_up.add_value_listener(self._on_btn_page_up_pressed)     
		self._btn_page_down.add_value_listener(self._on_btn_page_down_pressed)
		self._btn_sel_encoders.add_value_listener(self._on_btn_sel_encoders_pressed)
		self._btn_sel_top_btns.add_value_listener(self._on_btn_sel_top_btns_pressed)
		self._btn_sel_pots.add_value_listener(self._on_btn_sel_pots_pressed)
		self._btn_sel_btm_btns.add_value_listener(self._on_btn_sel_btm_btns_pressed)

		[button.add_value_listener(self._on_top_row_button_pressed, identify_sender = True) for button in self._buttons_upper_row]
		[button.add_value_listener(self._on_btm_row_button_pressed, identify_sender = True) for button in self._buttons_bottom_row]

		self.song.add_appointed_device_listener(self._on_appointed_device_changed)
		self.song.add_tracks_listener(self._on_tracks_changed)  #FIXME #!: Remove if not needed.
		self.song.add_visible_tracks_listener(self._on_visible_tracks_changed) #FIXME #!: Remove if not needed.


	################################################################################################################


	@override
	def build_midi_map(self, midi_map_handle : int) -> None:
		"""Create Live MIDI mappings for the effect controller strips."""
		
		log_info(f"EffectComponent.build_midi_map({midi_map_handle}) called.")

		#* COMBINE BOTH ROWS INTO ONE LIST OF 16 ITEMS TO FIX INDEX ERROR
		#* This gives us indices 0-7 for pots, and 8-15 for encoders
		combined_ccs = list(Constants.Effect.POTS + Constants.Effect.ENCODERS)

		for strip_index, strip in enumerate(self._strips):
			
			# Pull CC numbers from the 16-item list safely
			primary_cc_no = combined_ccs[strip_index]

			#log(f"STRIP LOGGER: Strip Index {strip_index} -> assigned to CC {primary_cc_no}")
			
			parameter = strip.assigned_parameter

			if parameter is not None:

				log_assignment(strip_index, primary_cc_no, parameter.name)

				# ASSIGN MAP MODE DYNAMICALLY BASED ON THE ROW
				if strip_index < 8:
					map_mode = MidiMap.MapMode.absolute # Pots (0-7) are absolute
				else:
					map_mode = MidiMap.MapMode.relative_smooth_signed_bit # Encoders (8-15) are relative
				
				MidiMap.map_midi_cc(
					midi_map_handle,
					parameter,
					Constants.Hardware.MIDI_CHANNEL,
					primary_cc_no,
					map_mode,
					False, # needs_takeover
				)
			
			else:
				log_assignment(strip_index, primary_cc_no, "None")

		log_info(f"<-----Returning from EffectComponent.build_midi_map({midi_map_handle}).")


	################################################################################################################


	def _change_assigned_device(self, device: Optional[Device]) -> None:
		"""Safely update active device references across track focus shifts."""

		log_info(f"EffectComponent._change_assigned_device({str(device)}) called.")

		if self._assigned_device_is_locked:
			log_verbose("LOCK ENGINE GUARD: Blocked appointed_device focus shift to maintain hardware lock.")
			return None
		
		# Set the master reference pointer to the device object handed down by Live
		self._assigned_device = device
		
		# Reset view layout page markers ONLY if we are browsing tracks dynamically
		self._bank = 0
		self._display_page_index = 0
		self._current_display_row = "pots"
		
		# Force a single rebuild of the layouts safely (force_rebuild=True maps MIDI)
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map()

		log_info("<-----Returning from EffectComponent.change_assigned_device().")


	################################################################################################################


	def _create_controls(self) -> None:
		
		self._btn_page_up      = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.PAGE_UP)
		self._btn_page_down    = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.PAGE_DOWN)
		self._btn_sel_encoders = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.SELECT_ENCODER)
		self._btn_sel_top_btns = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.SELECT_TOP_BUTTON_ROW)
		self._btn_sel_pots 	   = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.SELECT_POTS)
		self._btn_sel_btm_btns = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.SELECT_BOTTOM_BUTTON_ROW)
		#self._btn_sel_dpads	   = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, FX.SELECT_DRUM_PAD)

		self._buttons_upper_row  = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc) for cc in FX.UPPER_BUTTONS]
		self._buttons_bottom_row = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc) for cc in FX.UPPER_BUTTONS]


	################################################################################################################


	@override
	def disconnect(self) -> None:
		"""Disconnect the effect controller from the currently assigned device."""

		log_info("EffectComponent.disconnect() called")

		if self.is_enabled():
			self._change_assigned_device(None)
			self._remove_listeners()



	################################################################################################################


	def _get_num_parameter_banks(self) -> int:
		"""Get the number of banks required to display all the parameters in banks."""
		
		log_info("EffectComponent._get_num_parameter_banks() called.")

		if self._assigned_device is not None:
			param_count = len(self._assigned_device.parameters)
			
			# Use double-slash '//' for clean integer floor division
			return (param_count // 8) + int(param_count % 8 != 0)
		
		return 0 # No device no banks.


	################################################################################################################


	# def _handle_row_display_switch(self, moving_strip) -> None:
	# 	"""Calculate which row was moved and dynamically sync the virtual display page index."""

	# 	log(f"EffectComponent.__handle_row_display_switch() called.")

	# 	try:
	# 		# Find where this moving strip sits inside our array list of 16 targets
	# 		strip_index = self._strips.index(moving_strip)
			
	# 		# Decide what view option to flip to
	# 		new_row = "pots" if strip_index < 8 else "encoders"
			
	# 		if self._current_display_row != new_row:
	# 			self._current_display_row = new_row
				
	# 			# --- CRITICAL TRACKING SYNC FOR PHYSICAL TOUCHES ---
	# 			# Ensure variables exist
	# 			if not hasattr(self, '_bank'):
	# 				self._bank = 0
				
	# 			# Convert the current bank position and row focus into the absolute page index.
	# 			# Every bank controls 16 items (2 pages). Pots are even pages, Encoders are odd pages.
	# 			if new_row == "pots":
	# 				self._display_page_index = self._bank * 2
	# 			else:
	# 				self._display_page_index = (self._bank * 2) + 1
					
	# 			log(f"TOUCH SENSOR: Flipped to {new_row}. Virtual Page Index synced to -> {self._display_page_index}")
	# 			# ----------------------------------------------------
				
	# 			# Call text reassign with force_rebuild=False!
	# 			# Touching a knob should NEVER cause a violent C++ MIDI mapping teardown lag dropout.
	# 			self.reassign_strips(force_rebuild=False)
				

	# 	except Exception as e:
	# 		log_error(f"TOUCH ENGINE ERROR: {str(e)}")


	################################################################################################################


	def _lock_to_device(self, device: Device | None) -> None:
		"""Natively handle the hardware feedback loop when locking."""
		#* So we don't call this from our listener.  Instead we call toggle lock and it calls
		#*  RemoteSL.lock_to_device which then calls this.
		log_info(f"EffectComponent._lock_to_device({device}) called.")

		if device:
			self._assigned_device_is_locked = True
			self._locked_device = device # according to live.
			self._display_component.show_timed_message("Device Locked!", duration_seconds=2.0)	
			self._update_select_row_leds()



	################################################################################################################


	def _on_appointed_device_changed(self) -> None:
		"""Callback for changing the appointed device."""

		#* Handily this is also called when parameter names change.

		log_info("EffectComponent._on_appointed_device_change() called.")
		log_listener_callback()

		self._change_assigned_device(self.song.appointed_device)  #_set_appointed_device(device)


	################################################################################################################


	def _on_btn_page_up_pressed(self, value) -> None:

		log_listener_callback(value)

		if value and self._assigned_device is not None:
			
			device_parameters = self._assigned_device.parameters[1:]

			# Calculate the total number of 8-parameter display pages available
			total_pages = len(device_parameters) + 7 // 8

			if self._display_page_index + 1 < total_pages:

				self._display_page_index += 1

				log(f"PAGE BUTTON: Pressed Up. Virtual Display Page is now -> {self._display_page_index}")
				
				# Math Rule: A hard MIDI map layout rewrite is required only when entering an EVEN page index!
				# Page 0->1 (Same MIDI maps, view shifts to encoders)
				# Page 1->2 (New MIDI maps!, view resets to pots)
				if self._display_page_index % 2 == 0:
					self._bank += 1
					self._current_display_row = "pots"
					self.reassign_strips() # Full C++ MIDI map rebuild
					self.control_surface.request_rebuild_midi_map()
				else:
					self._current_display_row = "encoders"
					self.reassign_strips() # TEXT SWAP ONLY, lightning fast


	################################################################################################################
	
	
	def _on_btn_page_down_pressed(self, value) -> None:
		
		log_listener_callback(value)

		if value and self._assigned_device is not None:

			if self._display_page_index > 0:
				
				self._display_page_index -= 1
				log(f"PAGE BUTTON: Pressed Down. Virtual Display Page is now -> {self._display_page_index}")
				
				# Math Rule: Moving backward, a hard MIDI map layout rewrite is required only when dropping out of an EVEN page index
				# Page 2->1 (New MIDI maps!, view shifts to encoders)
				# Page 1->0 (Same MIDI maps, view resets to pots)
				if (self._display_page_index + 1) % 2 == 0:
					self._bank -= 1
					self._current_display_row = "encoders"
					self.reassign_strips() # Full C++ MIDI map rebuild
					self.control_surface.request_rebuild_midi_map()
				else:
					self._current_display_row = "pots"
					self.reassign_strips() # TEXT SWAP ONLY, lightning fast


		
	################################################################################################################
	

	# def _on_btn_sel_dpads_pressed(self, value) -> None:

	# 	log_listener_callback(value)

	# 	if value:
	# 		self.song.stop_all_clips()



	################################################################################################################
	

	def _on_btn_sel_encoders_pressed(self, value) -> None:

		log_listener_callback(value)

		if value:
			new_index = min(
				len(self.song.scenes) - 1,
				max(0, list(self.song.scenes).index(self.song.view.selected_scene) - 1),
			)
			self.song.view.selected_scene = self.song.scenes[new_index]


	################################################################################################################
	
	
	def _on_btn_sel_top_btns_pressed(self, value) -> None:

		log_listener_callback(value)

		if value:

			log_verbose(f"{len(self.song.view.selected_track.devices)=}")
			log_verbose(f"{self.song.view.selected_track.view.selected_device=})")

			if self.song.view.selected_track.view.selected_device is not None: # Root script does nothing with None selected.
				log_verbose("LOCK BUTTON PRESSED: Handing toggle request to root script.")
				self.control_surface.toggle_lock()
			else:
				if self._assigned_device_is_locked and self._locked_device is not None: # Only try this if the device is locked.

					log_verbose("LOCK BUTTON PRESSED: On empty track so attempting to unlock.")

					original_track = self.song.view.selected_track
					locked_track : Track = self._locked_device.canonical_parent
					self.song.view.selected_track = locked_track
					self.song.view.select_device(self._locked_device)
					self.control_surface.toggle_lock()
					self.song.view.selected_track = original_track
						
					self.control_surface.unlock_from_device(self._locked_device)
				


	################################################################################################################
	
	
	def _on_btn_sel_pots_pressed(self, value) -> None:

		log_listener_callback(value)
	
		if value:
			self.song.view.selected_scene.fire_as_selected()
	


	################################################################################################################
	
	
	def _on_btn_sel_btm_btns_pressed(self, value) -> None:

		log_listener_callback(value)

		if value:
			new_index = min(
				len(self.song.scenes) - 1,
				max(0, list(self.song.scenes).index(self.song.view.selected_scene) + 1),
			)
			self.song.view.selected_scene = self.song.scenes[new_index]


	################################################################################################################
	
	@override
	def on_enabled_changed(self):

		log_info(f"EffectComponent.on_enabled_changed() called.  enabled={self.is_enabled()} explicit={self.is_enabled(True)}.")

		if self.is_enabled():
			# Called when component becomes active – do initial setup
			self._add_listeners()
			self._change_assigned_device(self.song.appointed_device)

		else:
			self._remove_listeners()

		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map()

		return super().on_enabled_changed()


	################################################################################################################
	

	def _on_top_row_button_pressed(self, value, sender) -> None:

		log_listener_callback(value, sender)


	################################################################################################################
	
	
	def _on_btm_row_button_pressed(self, value, sender) -> None:

		log_listener_callback(value, sender)


	################################################################################################################


	def _on_selected_track_changed(self) -> None:
		"""Fires instantly whenever you select a different track channel lane in Live."""

		log_info(f"EffectComponent._on_selected_track_changed() called.")
		log_listener_callback()

		try:
			track: Track = self.song.view.selected_track
			
			if track is None or len(track.devices) == 0:
				log("TRACK CHANGED LOGIC: Track has 0 physical devices. Forcing clear...")
				self._change_assigned_device(None)
				return None

			# If the track actually has devices, safely extract the highlighted target
	
			log(f"TRACK CHANGED LOGIC: Active device is now -> {str(track.view.selected_device)}")
		
			self._change_assigned_device(track.view.selected_device)
			
		except Exception as e:
			log_error(f"TRACK CHANGED ERROR: {str(e)}")


	################################################################################################################


	def _on_strip_parameter_changed(self, strip_index: int):
		"""Called when a parameter on a strip changes."""

		strip = self._strips[strip_index]
		param = strip.assigned_parameter
		
		if param is not None:
			self._display_component.update_parameter(strip_index, param, ROW.BL)


	################################################################################################################


	def	_on_tracks_changed(self):
		log_listener_callback()


	################################################################################################################


	def _on_visible_tracks_changed(self):
		log_listener_callback()


	################################################################################################################


	def reassign_strips(self) -> None: # , force_rebuild: bool = True)
		
		log_info(f"EffectComponent.reassign_strips() called.") #force_rebuild={force_rebuild}
		
		device = self._assigned_device

		if device is not None:
			
			log_verbose("Device valid...")

			param_index: int = 0
			param_names: list[str] = []
			parameters: list[DeviceParameter | None] = []


			for strip in self._strips:
				
				param: DeviceParameter | None = None
				name: str = ""
				new_index = param_index + self._bank * 16

				device_parameters: list[DeviceParameter | None] = list(device.parameters[1:])

				if new_index < len(device_parameters):
					param = device_parameters[new_index]
				
				if param:
					name : str = param.name

				strip.assigned_parameter = param
				parameters.append(param)
				param_names.append(name)
				param_index += 1

			self._report_bank()

			if self._current_display_row == "pots":
				# Left Screen gets items 0-7 (Pots)
				active_names = param_names[:8]
				active_params = parameters[:8]
			else:
				# Left Screen gets items 8-15 (Encoders)
				active_names = param_names[8:]
				active_params = parameters[8:]

			log_verbose("!!! Setting setup_display_for_params()...")
			self._display_component.setup_display_for_params(DISPLAY.LEFT, active_names, active_params)
			#self._display_component.

		else:
			# This is for if no device is selected.
			for strip in self._strips:
				strip.assigned_parameter = None

			log("CLEARING SCREEN: Caching original single-string text prompt...")
			
			no_device_msg = "Please select a Device in Live to edit it..."
			#parameters = [None for _ in range(8)]

			self._display_component.clear_display_row(ROW.BL)
			self._display_component.write_display_rows(no_device_msg, ROW.TL)

			
		log_info(f"<-----Returning from EffectComponent.__reassign_strips().")


	################################################################################################################


	# #@override
	# def refresh_state(self) -> None:
		
	# 	log_info("EffectComponent.refresh_state() called.")
		
	# 	self._update_select_row_leds()
	# 	self.reassign_strips()

	# 	log_info("<-----Returning from EffectComponent.refresh_state() called.")


	################################################################################################################


	def _remove_listeners(self):
	
		self._btn_page_up.remove_value_listener(self._on_btn_page_up_pressed)     
		self._btn_page_down.remove_value_listener(self._on_btn_page_down_pressed)
		self._btn_sel_encoders.remove_value_listener(self._on_btn_sel_encoders_pressed)
		self._btn_sel_top_btns.remove_value_listener(self._on_btn_sel_top_btns_pressed)
		self._btn_sel_pots.remove_value_listener(self._on_btn_sel_pots_pressed)
		self._btn_sel_btm_btns.remove_value_listener(self._on_btn_sel_btm_btns_pressed)
		#self._btn_sel_dpads.remove_value_listener(self._on_btn_sel_dpads_pressed)

		[button.remove_value_listener(self._on_top_row_button_pressed) for button in self._buttons_upper_row]
		[button.remove_value_listener(self._on_btm_row_button_pressed) for button in self._buttons_bottom_row]

		for strip in self._strips:
			if strip.assigned_parameter is not None:
				strip.assigned_parameter.remove_value_listener(strip._on_parameter_value_changed)

		self.song.remove_appointed_device_listener(self._on_appointed_device_changed)
		self.song.remove_tracks_listener(self._on_tracks_changed)
		self.song.remove_visible_tracks_listener(self._on_visible_tracks_changed)


	################################################################################################################


	def _report_bank(self) -> None:
		
		log_info("EffectComponent._report_bank() called.")
		
		if self._show_bank:
			self._show_bank = False
			self._show_bank_select("Bank" + str(self._bank + 1))


	################################################################################################################


	def restore_bank(self, bank: int) -> None:
		
		log_info("EffectComponent.restore_bank() called.")

		if self._assigned_device_is_locked:
			self._bank = bank
			self.reassign_strips()


	###############################################################################################################


	# def _show_bank_select(self, bank_name: str) -> None:
		
	# 	log_info(f"EffectComponent._show_bank_select({bank_name}) called.")

	# 	if self._assigned_device:
	# 		self._control_surface.show_message(
	# 			str(self._assigned_device.name + " Bank: " + bank_name)
	# 		)


	###############################################################################################################


	# def _set_appointed_device(self, device: Device) -> None:
	# 	"""Public receiver function called by RemoteSL.py."""

	# 	log_info(f"EffectComponent._set_appointed_device(): Received device pointer -> {str(device)}")

		# This isn't called if the device is locked and you drop a new device on the locked channel.

		# If the user has locked the controller, ignore any dynamic focus shifts from Ableton.
		# if getattr(self, '_assigned_device_is_locked', False):
		# 	log("LOCK ENGINE GUARD: Blocked appointed_device focus shift to maintain hardware lock.")
		# 	return None

		#self._change_assigned_device(device)


	################################################################################################################


	# def __parameter_list_of_device_changed(self):
		
	# 	log("EffectComponent.__parameter_list_of_device_changed() called.")
	# 	self.reassign_strips()


	################################################################################################################


	def _unlock_from_device(self, device: Device | None) -> None:
		"""Natively handle the hardware feedback loop when unlocking."""

		log_info(f"EffectComponent._unlock_from_device({device}) called.")

		if device and device == self._locked_device:
			
			self._assigned_device_is_locked = False
			self._locked_device = None
			self._display_component.show_timed_message("Device Unlocked!", duration_seconds=2.0)

			if self.song.appointed_device != self._assigned_device:

				#? I'm guessing reset display and row only if the device actually changes.
				self._current_display_row = "pots"
				self._display_page_index = 0
				self._assigned_device = self.song.appointed_device
				self.reassign_strips()
				self.control_surface.request_rebuild_midi_map()

			self._update_select_row_leds()

		else:
			log_warning("Attempted to unlock with no device.  This could happen....")
			#raise RuntimeError("Attempted to unlock with no device. Impossible.")


	################################################################################################################


	@override
	def update(self) -> None:
		"""Called sometimes... """
		#! FIXME: We need to actually work out what we need to do here.

		if not self.is_enabled():
			return

		log_verbose("EffectComponent.update() called.")
		#self._update_select_row_leds()
		super().update()
		
		#* If the controller is locked, we completely freeze the parameter tracking view!
		#* What to do if device is locked.
		#! This isn't called on a regular tick so will it work is it the best method... Try to test.
		# if self._assigned_device_is_locked == True:
			
		# 	# Monitor if the locked device was physically deleted from the session set

		# 	if self._assigned_device is None or not self._assigned_device.canonical_parent:

		# 		log_verbose("LOCK BREAK: Locked device was physically deleted! Releasing control maps...")
		# 		self._assigned_device = self._control_surface.song.appointed_device
		# 		#self._assigned_device_is_locked = False
		# 		self._unlock_from_device(self._assigned_device)

		# 		if self._assigned_device is not None:
		# 			self._change_assigned_device(self._assigned_device)
				
		# 	# If the device is alive and locked, EXIT IMMEDIATELY.
		# 	# This blocks the empty track lane check below from ever executing!
		# 	return None
		#*------------------------------------------------------------------------------
		
		#! FIXME: This stuff after here is it necessary? Does it work?
		#* Fetch exactly what device Ableton's viewport highlights right now
		# current_track_device = self.song.view.selected_track.view.selected_device
		
		# # --- CHANNELS MONITOR BALANCED RE-SYNC GUARD (Runs ONLY when unlocked) ---
		# if current_track_device is None and self._assigned_device is not None:
		# 	log("POLLING ENGINE: Empty track lane detected. Resetting references...")
		# 	self._assigned_device = None
		# 	for strip in self._strips:
		# 		strip.assigned_parameter = None
		# 	self.reassign_strips()
		# 	self.control_surface.request_rebuild_midi_map()
		# 	return None
			
		# if current_track_device is None and self._assigned_device is None:
		# 	return None
		#* ------------------------------------------------------------------------
		
		#? Not sure what this does.
		# moved_strip_index = None

		# for strip_index, strip in enumerate(self._strips):
		# 	param = strip.assigned_parameter
		# 	if param is not None:
		# 		current_val = param.value
				
		# 		# Check if the value shifted since the last frame scan
		# 		if hasattr(strip, '_last_value') and strip._last_value is not None and current_val != strip._last_value:
		# 			strip._last_value = current_val
		# 			moved_strip_index = strip_index
		# 			break
				
		# 		strip._last_value = current_val


		## Update the screen text ONLY if a physical hand movement row shift actually happened
		# if moved_strip_index is not None:
		# 	new_row = "pots" if moved_strip_index < 8 else "encoders"
			
		# 	if not hasattr(self, '_current_display_row'):
		# 		self._current_display_row = "pots"
				
		# 	if self._current_display_row != new_row:
		# 		self._current_display_row = new_row
				
		# 		# --- SYNC THE VIRTUAL PAGE INDEX BASED ON ACTIVE ROW FLIP ---
		# 		if not hasattr(self, '_display_page_index'):
		# 			self._display_page_index = 0
				
		# 		# If we are on the first 16-parameter block, align the page number
		# 		if self._bank == 0:
		# 			self._display_page_index = 0 if new_row == "pots" else 1
		# 		# -------------------------------------------------------------
				
		# 		# Update text only, skip the MIDI map layout reconstruction!
		# 		self.reassign_strips()

		#?-------------------------------------------------------------------------


	################################################################################################################


	def _update_select_row_leds(self) -> None:
		
		if self._assigned_device_is_locked:
			log_verbose("Turning ON LED for device locked.")
			self._control_surface.send_midi((M.START_BYTE, Constants.Effect.SELECT_TOP_BUTTON_ROW, 1))
		else:
			log_verbose("Turning OFF device locked LED.")
			self._control_surface.send_midi((M.START_BYTE, Constants.Effect.SELECT_TOP_BUTTON_ROW, 0))


	################################################################################################################


####################################################################################################################



class EffectChannelStrip(object):
	"""Represent a single strip in the effect controller layout."""


	################################################################################################################


	_effect_component 	 : EffectComponent
	_assigned_parameter  : DeviceParameter | None
	_last_value 		 : float | None


	################################################################################################################


	def __init__(self, effect_component: EffectComponent):

		self._effect_component = effect_component
		self._assigned_parameter = None
		self._last_value = None


	################################################################################################################


	@property
	def last_value(self) -> Optional[float]:
		return self._last_value
	
	@last_value.setter
	def last_value(self, last_value: float):
		self._last_value = last_value


	################################################################################################################


	@property
	def assigned_parameter(self) -> DeviceParameter | None:
		"""Getter: Safely returns the currently bound device parameter or None."""

		return self._assigned_parameter

	#-------------------------------------------------------------------------------------------
	
	@assigned_parameter.setter
	def assigned_parameter(self, parameter: DeviceParameter | None):
		"""Setter: Safely updates the internal parameter reference reference."""

		if self._assigned_parameter is not None:
			try:
				if self._assigned_parameter.value_has_listener(self._on_parameter_value_changed):
					self._assigned_parameter.remove_value_listener(self._on_parameter_value_changed)
			except:
				pass # This pass is to deal with deleted tracks as assigned parameter is now stale.
				
		self._assigned_parameter = parameter

		if parameter is not None:
			if not parameter.value_has_listener(self._on_parameter_value_changed):
				parameter.add_value_listener(self._on_parameter_value_changed)


	################################################################################################################


	def on_button_pressed(self) -> None:
		
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


	def on_encoder_moved(self, cc_value : int) -> None:
		
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


	################################################################################################################


	def _on_parameter_value_changed(self):

		strip_index = self._effect_component._strips.index(self)
		self._effect_component._on_strip_parameter_changed(strip_index)


	################################################################################################################


####################################################################################################################
####################################################################################################################

