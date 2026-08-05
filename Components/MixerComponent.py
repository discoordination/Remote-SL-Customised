####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
####################################################################################################################

#TODO: pressing a select button could select the track only if you longer press?  Or is this needed?
#TODO: pressing a mute button could also solo if on and a long press or un solo if long or better idea long press on 
# the row select button changes it to solo mode... like shift solo mode

####################################################################################################################


"""Mixer-section controller logic for the Remote SL script."""

from __future__ import annotations	# to avoid the circular reference on RemoteSL and not use quotes...

from Live import MidiMap

from Live.Track import Track
from Live.Song import Song
from Live.DeviceParameter import DeviceParameter

from ableton.v2.control_surface import Component, MIDI_CC_TYPE
from ableton.v2.control_surface.elements import ButtonElement, SliderElement


from enum import Enum
from typing import TYPE_CHECKING, Optional

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func


if TYPE_CHECKING:
	from ..RemoteSL import RemoteSL


from .DisplayComponent import DisplayComponent, ROW, DISPLAY
from ..consts import SLM, MXR, Constants, H, M
from ..RemoteSL_Logger import log, log_assignment, log_verbose, log_error, log_warning, log_info


####################################################################################################################


class LayoutMode(Enum):
	STANDARD = (0, "All")
	TRACKS = (1, "Tracks & Main")
	RETURNS = (2, "Returns & Main")


####################################################################################################################




class MixerComponent(Component):
	"""Handle tracks, transport controls, and slider modes for the mixer section."""


	################################################################################################################

	_control_surface     : RemoteSL
	_display_component   : DisplayComponent

	# ------------- Controls ----------------

	_btn_page_up         : ButtonElement
	_btn_page_down       : ButtonElement
	_btn_sel_faders      : ButtonElement
	_btn_sel_tbs         : ButtonElement
	_btn_sel_bbs         : ButtonElement
	_btns_top_row        : list[ButtonElement]
	_btns_btm_row        : list[ButtonElement]
	#._faders:		list[SliderElement]

	# ---------------------------------------

	_assigned_tracks     : list[Track] 
	_last_send_index     : int
	_layout_mode         : LayoutMode
	_strips              : list[MixerChannelStrip]
	_slider_mode		 : int
	_strip_offset        : int


	################################################################################################################


	def __init__(self, control_surface: RemoteSL, name: str = 'MixerComponent', *a, **k):
		"""Initialise the mixer controller state and display references."""

		log_info(f"MixerComponent.__init__({control_surface}, {name}) called.")
		
		super().__init__(name=name, song=control_surface.song, is_enabled=False, *a, **k)

		self._control_surface = control_surface
		self._display_component = control_surface._display_component

		self._strip_offset = 0
		self._slider_mode = SLM.VOLUME
		self._last_send_index = 0
		
		self._strips = [MixerChannelStrip(self, index) for index in range(Constants.Hardware.NUM_CONTROLS_PER_ROW)]
		self._assigned_tracks = []
		self._layout_mode = LayoutMode.STANDARD

		self._create_controls()

		log_info(f"<-----Returning from MixerComponent.__init__({control_surface}, {name}).")


	################################################################################################################


	@property
	def control_surface(self) -> RemoteSL:
		return self._control_surface


	################################################################################################################


	@property
	@override
	def song(self) -> Song:
		result = super().song
		assert result is not None
		return result


	################################################################################################################


	@property
	def slider_mode(self) -> int:
		return self._slider_mode

	
	@slider_mode.setter
	def slider_mode(self, newMode: int) -> None:
		self._slider_mode = newMode


	################################################################################################################

	
	@property
	def bank_size(self) -> int:
		
		if self._layout_mode == LayoutMode.STANDARD:  # All Tracks
			return Constants.Hardware.NUM_CONTROLS_PER_ROW  # 8
		else:  # Tracks Only or Returns Only
			return Constants.Hardware.NUM_CONTROLS_PER_ROW - 1  # 7


	################################################################################################################


	def _add_listeners(self) -> None:

		log_verbose(f"MixerComponent._add_listeners() called. Buttons: {self._btn_sel_faders}, {self._btn_sel_tbs}, {self._btn_sel_bbs}")
		
		self._btn_page_up.add_value_listener(self._on_btn_page_up_pressed)
		self._btn_page_down.add_value_listener(self._on_btn_page_down_pressed)
		self._btn_sel_faders.add_value_listener(self._on_btn_sel_faders_pressed)
		self._btn_sel_tbs.add_value_listener(self._on_btn_sel_tbs_pressed)
		self._btn_sel_bbs.add_value_listener(self._on_btn_sel_bbs_pressed)

		#[fader.add_value_listener(self._on_fader_moved, identify_sender=True) for fader in self._faders]
		[btn.add_value_listener(self._on_btn_in_top_row_pressed, identify_sender=True) for btn in self._btns_top_row]
		[btn.add_value_listener(self._on_btn_in_btm_row_pressed, identify_sender=True) for btn in self._btns_btm_row]

		self.song.add_visible_tracks_listener(self._on_tracks_added_or_deleted)


	################################################################################################################


	@override
	def build_midi_map(self, midi_map_handle) -> None:
		"""Create Live MIDI mappings for the mixer strips."""
		
		log_info(f"MixerComponent->build_midi_map({midi_map_handle}) called.")

		for strip_index, strip in enumerate(self._strips):
			
			cc_no = Constants.Mixer.SLIDER_BASE + strip_index
			
			if strip.assigned_track() and strip.slider_parameter():
			
				map_mode = MidiMap.MapMode.absolute # They are sliders not encoders.
				parameter = strip.slider_parameter()

				log_assignment(strip_index, cc_no, str(parameter) if parameter is not None else "")

				MidiMap.map_midi_cc(midi_map_handle, parameter, Constants.Hardware.MIDI_CHANNEL, cc_no, map_mode, False) # from Live.Midimap
				
			
		log_info(f"<-----Returning from MixerComponent.build_midi_map({midi_map_handle}).")


	################################################################################################################


	def _create_controls(self) -> None:
		
		self._btn_page_up 	 = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.PAGE_UP)
		self._btn_page_down  = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.PAGE_DOWN)

		self._btn_sel_faders = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_SLIDERS)
		self._btn_sel_tbs	 = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_BUTTONS_TOP)
		self._btn_sel_bbs	 = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_BUTTONS_BOTTOM)

		self._btns_top_row   = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc)  for cc in MXR.BUTTONS_TOP_ROW]
		self._btns_btm_row   = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc)  for cc in MXR.BUTTONS_BOTTOM_ROW]


	################################################################################################################


	@override
	def disconnect(self) -> None:
		"""Remove listeners and release the assigned tracks when the script disconnects."""

		log_info("MixerComponent.disconnect() called.")

		if self.is_enabled():
			self._remove_listeners()
		
			for strip in self._strips:
				strip.set_assigned_track(None) 

			for track in self._assigned_tracks:
				if track and track.name_has_listener(self._on_track_name_changed):
					track.remove_name_listener(self._on_track_name_changed)


	################################################################################################################


	def _get_filtered_tracks(self) -> tuple[Track, ...]:
		"""Utility function to get the selection of tracks required by the mode setting."""

		# Don't call if not enabled.
		# TODO: Remove when you are sure it's not called.
		if not self.is_enabled():
			log_error("Try to avoid calling if not enabled.  U haven't written the code for that.")
			raise RuntimeError("Error: We should try to avoid calling if not enabled.")

		if self.is_enabled() == False:
			return ()
		if self._layout_mode == LayoutMode.STANDARD: # All Tracks (standard) 
			return tuple(self.song.visible_tracks) + tuple(self.song.return_tracks) + (self.song.master_track,)
		if self._layout_mode == LayoutMode.RETURNS:  # Returns Only
			return tuple(self.song.return_tracks)

		# Tracks and master.
		return tuple(self.song.visible_tracks)
		

	################################################################################################################

	
	def _on_btn_in_top_row_pressed(self, value, sender: ButtonElement) -> None:

		log_info(f"MixerComponent._on_btn_in_top_row_pressed({value}, {sender}) called.")

		cc: int = sender.original_identifier()
		# midi_channel = sender.original_channel()	
		# msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)

		channel_strip = self._strips[cc - Constants.Mixer.BUTTONS_TOP_BASE]

		if value == Constants.Hardware.BUTTON_PRESSED:
			channel_strip.top_row_button_pressed()
		

	################################################################################################################
	
	
	def _on_btn_in_btm_row_pressed(self, value, sender: ButtonElement) -> None:

		log_info(f"MixerComponent._on_btn_in_btm_row_pressed({value}, {sender}) called.")
		
		cc = sender.original_identifier()
		# midi_channel = sender.original_channel()	
		# msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)

		channel_strip = self._strips[cc - Constants.Mixer.BUTTON_BOTTOM_BASE]

		if value == H.BUTTON_PRESSED:
			channel_strip.bottom_row_button_pressed()


	################################################################################################################

	
	def _on_btn_page_down_pressed(self, value) -> None:

		log_info(f"MixerComponent._on_btn_page_down_pressed({value}) called.")
		
		all_tracks = tuple(self.control_surface.song.visible_tracks) + tuple(self.control_surface.song.return_tracks) + (self.control_surface.song.master_track,)

		if value and len(all_tracks) > self.bank_size:
			
			self._strip_offset += self.bank_size
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()


	################################################################################################################
	
	
	def _on_btn_page_up_pressed(self, value) -> None:
		
		log_info(f"MixerComponent._on_btn_page_up_pressed({value}) called.")

		if value and self._strip_offset > 0:
			
			self._strip_offset -= self.bank_size
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()


	################################################################################################################

	
	def _on_btn_sel_bbs_pressed(self, value) -> None:

		log_info(f"MixerComponent._on_btn_sel_bbs_pressed({value}) called.")

		if value:
			# should revolve around sends
			if self._slider_mode >= SLM.SEND: # If send mode is already sends increment them.
				log(f"\t|----->Doing A.")
				newSendMode = SLM.SEND + ((self._slider_mode + 1) % len(self.song.return_tracks))
				self._set_slider_mode(newSendMode)
			else:  # Else simply go to the first send mode.
				log(f"\t|----->Doing B.")
				self._set_slider_mode(SLM.SEND + self._last_send_index)
				

	################################################################################################################

	
	def _on_btn_sel_faders_pressed(self, value) -> None:
		log_info(f"MixerComponent._on_btn_sel_faders_pressed({value}) called.")

		if value:
			if self._slider_mode != SLM.VOLUME:
				self._set_slider_mode(SLM.VOLUME)

			else:
				self._layout_mode = list(LayoutMode)[((self._layout_mode.value[0] + 1) % len(LayoutMode))]
				self._display_component.show_timed_message(f"{self._layout_mode.value[1]}", 2.0, True, ROW.TR)
				self._strip_offset = 0 # Reset the offset.
				self.reassign_strips()
				self.control_surface.request_rebuild_midi_map()


	################################################################################################################
	
	
	def _on_btn_sel_tbs_pressed(self, value) -> None:

		log_info(f"MixerComponent._on_btn_sel_tbs_pressed({value}) called.")

		if value:
			self._set_slider_mode(SLM.PAN)


	################################################################################################################

	@override
	def on_enabled_changed(self):

		log_info(f"MixerComponent.on_enabled_changed() called.  enabled={self.is_enabled()} explicit={self.is_enabled(True)}.")

		if self.is_enabled():
			log_verbose("\t|----->Enabling MixerComponent.")
			# Called when component becomes active – do initial setup
			self._add_listeners()
			
		else:
			log_verbose("\t|----->Disabling MixerComponent.")
			self._remove_listeners()
			for strip in self._strips:
				strip.set_assigned_track(None) 

		self.reassign_strips() # This deals with removing track listeners.
		self.control_surface.request_rebuild_midi_map()

		return super().on_enabled_changed()


	################################################################################################################


	def _on_strip_parameter_changed(self, strip_index: int):
		"""Called when a parameter on a strip changes."""

		# Update the display for this strip only
		strip = self._strips[strip_index]
		param = strip.slider_parameter()

		if param is not None:
			self._display_component.update_parameter(strip_index, param, ROW.BR)


	################################################################################################################


	def _on_tracks_added_or_deleted(self) -> None:
		
		log_info("MixerComponent.on_tracks_added_or_deleted called().")
		
		#self._validate_strip_offset()
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map()


	################################################################################################################


	def _on_track_name_changed(self) -> None:
		self.reassign_strips()


	################################################################################################################


	def reassign_strips(self) -> None:
		
		log_info("MixerComponent.reassign_strips() called.")

		# Remove existing listeners.
		for track in self._assigned_tracks:
			if track and track.name_has_listener(self._on_track_name_changed):
				track.remove_name_listener(self._on_track_name_changed)

		# Reset assigned tracks list.
		self._assigned_tracks = []

		if not self.is_enabled():	# Return here so we've cleared the tracks and the listeners.
			return
		
		# Get tracks based on display mode
		tracks = self._get_filtered_tracks()

		track_names: list[str] = []
		parameters: list[Optional[DeviceParameter]] = []

		self._validate_strip_offset()
		track_index = self._strip_offset


		for strip_index, strip in enumerate(self._strips):

			if self._layout_mode != LayoutMode.STANDARD and strip_index == len(self._strips) - 1:
				track = self.song.master_track

			else:
				# We haven't run out of tracks
				if track_index < len(tracks):

					track = tracks[track_index]
					track_index += 1
				else:
					track = None

			if track:
				strip.set_assigned_track(track)
				track_names.append(track.name)
				parameters.append(strip.slider_parameter())
				track.add_name_listener(self._on_track_name_changed)
				self._assigned_tracks.append(track)
			
			else:
				strip.set_assigned_track(None)
				track_names.append("")
				parameters.append(None)
			
	
		self._display_component.setup_display_for_params(DISPLAY.RIGHT, track_names, parameters)

		#self.control_surface.request_rebuild_midi_map() # We don't do it here because maybe mapping hasn't changed,
		#			ie. perhaps only the name has changed.
		
		log_info("<-----Returning from MixerComponent.reassign_strips()")
		

	################################################################################################################


	# def receive_midi_cc(self, cc_no, cc_value) -> None:
	# 	"""Route incoming CC events for mixer navigation and transport control."""
		
	# 	log_info(f"MixerComponent.receive_midi_cc({cc_no}, {cc_value}) called.")
			
	# 	if cc_no in Constants.Mixer.SLIDERS:
	# 		channel_strip = self._strips[cc_no - Constants.Mixer.SLIDER_BASE]
	# 		channel_strip.slider_moved(cc_value)

	# 	else:
	# 		log("\t|----->Midi cc not handled by MixerComponent.")

	# 	log_info(f"<-----Returning from MixerComponent.receive_midi_cc({cc_no}, {cc_value}).")
	# 	return None


	################################################################################################################


	@override
	def refresh_state(self) -> None:
		
		log_info("MixerComponent.refresh_state() called.")
		
		self._update_selected_row_leds()
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map() # <---- Not sure if required here.
		
		log_verbose("<-----Returning from MixerComponent.refresh_state().")


	################################################################################################################


	def _remove_listeners(self) -> None:

		self._btn_page_up.remove_value_listener(self._on_btn_page_up_pressed)
		self._btn_page_down.remove_value_listener(self._on_btn_page_down_pressed)
		self._btn_sel_faders.remove_value_listener(self._on_btn_sel_faders_pressed)
		self._btn_sel_tbs.remove_value_listener(self._on_btn_sel_tbs_pressed)
		self._btn_sel_bbs.remove_value_listener(self._on_btn_sel_bbs_pressed)

		[btn.remove_value_listener(self._on_btn_in_top_row_pressed) for btn in self._btns_top_row]
		[btn.remove_value_listener(self._on_btn_in_btm_row_pressed) for btn in self._btns_btm_row]

		self.song.remove_visible_tracks_listener(self._on_tracks_added_or_deleted)
		

	################################################################################################################


	def _send_midi(self, midi_bytes: tuple[int, int, int]):
		return self._control_surface.send_midi(midi_bytes)


	################################################################################################################


	def _set_selected_track(self, track) -> None:
		if track:
			self.control_surface.song.view.selected_track = track


	################################################################################################################


	def _set_slider_mode(self, new_mode: int) -> None:

		log_info(f"DisplayComponent.set_slider_mode({new_mode}) called.")

		if self._slider_mode != new_mode:
			
			if self._slider_mode >= SLM.SEND and new_mode >= SLM.SEND:
				
				if self._slider_mode - SLM.SEND + 1 < len(self.control_surface.song.return_tracks):
					self._slider_mode += 1
					self._last_send_index = self._slider_mode - SLM.SEND
				else:
					self._slider_mode = SLM.SEND
					self._last_send_index = 0
				
			self._slider_mode = new_mode

			newModeStr = "Volume" if new_mode == SLM.VOLUME else "Pan" if new_mode == SLM.PAN else f"Send {1 + new_mode - SLM.SEND}"

			self._display_component.show_timed_message(f"{newModeStr} Mode Selected", 2.0, True, ROW.TR)

			self._update_selected_row_leds()
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()



	################################################################################################################


	# def track_about_to_arm(self, track):
		
	# 	if track and self.control_surface.song.exclusive_arm:
	# 		for candidate in self.control_surface.song.tracks:
				
	# 			if candidate.can_be_armed and candidate.arm and candidate != track:
	# 				candidate.arm = False


	################################################################################################################


	@override
	def update(self) -> None:

		if not self.is_enabled():
			return
		
		log_verbose("MixerComponent.update() called.")
		self._update_selected_row_leds() # For light at start.

		#self.refresh_state()
		super().update()


	################################################################################################################


	# def update_display(self) -> None:
	# 	super().update_display()
	# 	log_info("MixerComponent.update_display() called.")


	################################################################################################################


	def _update_selected_row_leds(self) -> None:
		
		if self._slider_mode == SLM.VOLUME:
			
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, 1))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, 0))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, 0))

		elif self._slider_mode == SLM.PAN:
			
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, 0))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, 1))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, 0))
		
		elif self._slider_mode >= SLM.SEND:
			
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, 0))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, 0))
			self._send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, 1))


	################################################################################################################


	# def validate_slider_mode(self):
	# 	if self._slider_mode - SLM.SEND >= len(self.song.return_tracks):
	# 		self._slider_mode = SLM.VOLUME


	################################################################################################################


	def _validate_strip_offset(self) -> None:

		# Get filtered tracks (same as reassign_strips)
		tracks = self._get_filtered_tracks()

		# Calculate the largest multiple of bank_size that is <= len(tracks) - 1
		# This gives us: 0, bank_size, 2*bank_size, ... up to the last full/partial bank
		max_offset = max(0, ((len(tracks) - 1) // self.bank_size) * self.bank_size)
		
		# Clamp to valid range
		self._strip_offset = min(self._strip_offset, max_offset)
		self._strip_offset = max(0, self._strip_offset)
		
		# Align to bank_size (ensures offset is always 0, bank_size, 2*bank_size, ...)
		self._strip_offset = (self._strip_offset // self.bank_size) * self.bank_size


	################################################################################################################


####################################################################################################################




class MixerChannelStrip(object):
	"""Represent one mixer strip with mute, arm, and slider behaviour."""

	################################################################################################################


	def __init__(self, mixer_controller_parent: MixerComponent, index: int):

		self._mixer_controller : MixerComponent = mixer_controller_parent
		self._index : int = index
		self._assigned_track : Optional[Track] = None


	################################################################################################################


	@property
	def song(self) -> Song:
		return self._mixer_controller.song


	################################################################################################################


	def assigned_track(self) -> Optional[Track]:
		return self._assigned_track


	################################################################################################################


	def _is_track_alive(self) -> bool:
		"""You need to check the track hasn't been deleted."""
		if self._assigned_track is None:
			return False
		try:
			# Accessing a property on a dead track raises Boost.Python.ArgumentError
			_ = self._assigned_track.name
			return True
		except Exception:
			return False

	################################################################################################################

	def _on_parameter_value_changed(self, value = None):
		self._mixer_controller._on_strip_parameter_changed(self._index)


	################################################################################################################


	def set_assigned_track(self, track: Track | None):

		# If track is being set to none or track is changing. Then if there is a parameter and it has a listener remove.
        # Remove listener from old parameter if any
		if self._assigned_track is not None:
			old_param = self.slider_parameter()
			if old_param and old_param.value_has_listener(self._on_parameter_value_changed):
				old_param.remove_value_listener(self._on_parameter_value_changed)

		self._assigned_track = track

		# Add listener to new parameter if available
		if track is not None:
			new_param = self.slider_parameter()
			if new_param and not new_param.value_has_listener(self._on_parameter_value_changed):
				new_param.add_value_listener(self._on_parameter_value_changed)


	################################################################################################################


	def slider_parameter(self) -> DeviceParameter | None:
		"""Gets the actual Live.DeviceParameter currently controlled by the slider."""
		
		if self._assigned_track is None or not self._is_track_alive(): # is track alive checks for deleted tracks.
			return None

		slider_mode = self._mixer_controller.slider_mode # What is the currently selected use for the slider.

		if slider_mode == SLM.VOLUME:
			return self._assigned_track.mixer_device.volume
		
		if slider_mode == SLM.PAN:
			return self._assigned_track.mixer_device.panning
		
		if slider_mode >= SLM.SEND:
			
			send_index = slider_mode - SLM.SEND # What is the index of send currently controlled.

			if send_index < len(self._assigned_track.mixer_device.sends):
				return self._assigned_track.mixer_device.sends[send_index]

		return None


	################################################################################################################


	# def slider_moved(self, cc_value: int) -> None:

	# 	log(f"MixerComponent.slider_moved({cc_value}) called.")
	# 	parameter = self.slider_parameter() # get the parameter.

	# 	if parameter and hasattr(parameter, "min") and hasattr(parameter, "max") and parameter.max != parameter.min:
	# 		parameter.value = parameter.min + (parameter.max - parameter.min) * (float(cc_value) / 127.0)


	################################################################################################################


	# def take_control_of_second_button(self, take_control : bool) -> None:
	# 	pass


	################################################################################################################


	def top_row_button_pressed(self) -> None:
		
		if self._assigned_track and self._assigned_track in tuple(self.song.visible_tracks) + tuple(self.song.return_tracks):
			log("\t----->Muting track.")
			self._assigned_track.mute = not self._assigned_track.mute


	################################################################################################################


	def bottom_row_button_pressed(self) -> None:

		if self._assigned_track and self._assigned_track in self.song.visible_tracks:
			
			#self._mixer_controller.track_about_to_arm(self._assigned_track)
			self._assigned_track.arm = not self._assigned_track.arm
			log("\t----->Arming track.")

			if self._assigned_track.arm and self._assigned_track.view.select_instrument():
				self._mixer_controller._set_selected_track(self._assigned_track)
				log("\t----->Setting track selected.")


	################################################################################################################


	# def _on_mute_changed(self) -> None:
	# 	pass


	################################################################################################################


	# def _on_arm_changed(self) -> None:
	# 	pass


####################################################################################################################



####################################################################################################################
####################################################################################################################
