####################################################################################################################
# Source Generated with Decompyle++
# File: MixerController.pyc (Python 3.11)
####################################################################################################################
####################################################################################################################

#TODO: pressing a select button could select the track only if you longer press?  Or is this needed?
#TODO: pressing a mute button could also solo if on and a long press or un solo if long or better idea long press on 
# the row select button changes it to solo mode... like shift solo mode

####################################################################################################################


"""Mixer-section controller logic for the Remote SL script."""

from __future__ import annotations	# to avoid the circular reference on RemoteSL and not use quotes...

import Live
from Live.Track import Track
from ableton.v2.control_surface import Component, MIDI_CC_TYPE
from ableton.v2.control_surface.elements import ButtonElement, SliderElement

from enum import Enum
from typing import TYPE_CHECKING

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


from .DisplayComponent import DisplayComponent, ROW
from ..consts import SLM, MXR, Constants, H, M
from ..myLogger import log


####################################################################################################################


class LayoutMode(Enum):
	STANDARD = (0, "All")
	TRACKS = (1, "Tracks & Main")
	RETURNS = (2, "Returns & Main")


####################################################################################################################



class MixerComponent(Component):
	"""Handle tracks, transport controls, and slider modes for the mixer section."""


	################################################################################################################


	def __init__(self, control_surface: RemoteSL, name: str = 'MixerComponent', *a, **k):
		"""Initialise the mixer controller state and display references."""
		
		super().__init__(name=name, song=control_surface.song, *a, **k)

		self._control_surface: RemoteSL = control_surface
		self._display_component: DisplayComponent = control_surface._display_component
	
		self._btn_page_up: 	  ButtonElement
		self._btn_page_down:  ButtonElement

		self._btn_sel_faders: ButtonElement
		self._btn_sel_tbs:	  ButtonElement
		self._btn_sel_bbs:	  ButtonElement

		self._btns_top_row:	list[ButtonElement]
		self._btns_btm_row:	list[ButtonElement]

		self._strip_offset: int = 0
		self._slider_mode: int = SLM.VOLUME
		self._last_send_index: int = 0
		
		self._strips = [MixerChannelStrip(self, index) for index in range(Constants.Hardware.NUM_CONTROLS_PER_ROW)]
		self._assigned_tracks: list[Track] = []
		self._layout_mode: LayoutMode = LayoutMode.STANDARD

		self._create_buttons()
		self._add_button_listeners()

		self.song.add_visible_tracks_listener(self.on_tracks_added_or_deleted)
		#self.song.add_loop_listener(self._on_loop_changed)

		self.update_selected_row_leds() # For light at start.
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map()


	################################################################################################################

	@property
	def control_surface(self) -> RemoteSL:
		return self._control_surface

	################################################################################################################

	@property
	@override
	def song(self) -> Live.Song.Song:
		result = super().song
		assert result is not None
		return result


	################################################################################################################


	@property
	def slider_mode(self) -> int:
		return self._slider_mode

	
	################################################################################################################

	@slider_mode.setter
	def slider_mode(self, newMode: int) -> None:
		self._slider_mode = newMode


	################################################################################################################


	@property
	def send_midi(self):
		return self._control_surface.send_midi


	################################################################################################################
	
	
	@property
	def bank_size(self) -> int:
		if self._layout_mode == LayoutMode.STANDARD:  # All Tracks
			return Constants.Hardware.NUM_CONTROLS_PER_ROW  # 8
		else:  # Tracks Only or Returns Only
			return Constants.Hardware.NUM_CONTROLS_PER_ROW - 1  # 7


	################################################################################################################


	def _add_button_listeners(self) -> None:
		
		self._btn_page_up.add_value_listener(self._on_btn_page_up_pressed)
		self._btn_page_down.add_value_listener(self._on_btn_page_down_pressed)
		self._btn_sel_faders.add_value_listener(self._on_btn_sel_faders_pressed)
		self._btn_sel_tbs.add_value_listener(self._on_btn_sel_tbs_pressed)
		self._btn_sel_bbs.add_value_listener(self._on_btn_sel_bbs_pressed)

		[btn.add_value_listener(self._on_btn_in_top_row_pressed, identify_sender=True) for btn in self._btns_top_row]
		[btn.add_value_listener(self._on_btn_in_btm_row_pressed, identify_sender=True) for btn in self._btns_btm_row]


	################################################################################################################


	@override
	def build_midi_map(self, midi_map_handle) -> None:
		"""Create Live MIDI mappings for the mixer strips and transport buttons."""
		
		log(f"MixerController->build_midi_map({midi_map_handle}) called.")
		#needs_takeover = True

		for strip_index, strip in enumerate(self._strips):
			
			cc_no = Constants.Mixer.SLIDER_BASE + strip_index
			
			if strip.assigned_track() and strip.slider_parameter():
			
				map_mode = Live.MidiMap.MapMode.absolute
				parameter = strip.slider_parameter()
				Live.MidiMap.map_midi_cc(midi_map_handle, parameter, Constants.Hardware.MIDI_CHANNEL, cc_no, map_mode, False)
				continue
			
			Live.MidiMap.forward_midi_cc(self.control_surface.handle(), midi_map_handle, Constants.Hardware.MIDI_CHANNEL, cc_no)

		log(f"<-----Returning from MixerController.build_midi_map({midi_map_handle}).")


	################################################################################################################


	def _create_buttons(self) -> None:
		
		self._btn_page_up: 	  ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.PAGE_UP)
		self._btn_page_down:  ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.PAGE_DOWN)

		self._btn_sel_faders: ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_SLIDERS)
		self._btn_sel_tbs:	  ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_BUTTONS_TOP)
		self._btn_sel_bbs:	  ButtonElement = ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, MXR.SELECT_BUTTONS_BOTTOM)

		self._btns_top_row:	list[ButtonElement] = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc)  for cc in MXR.BUTTONS_TOP_ROW]
		self._btns_btm_row:	list[ButtonElement] = [ButtonElement(True, MIDI_CC_TYPE, H.MIDI_CHANNEL, cc)  for cc in MXR.BUTTONS_BOTTOM_ROW]


	################################################################################################################


	@override
	def disconnect(self) -> None:
		"""Remove listeners and release the assigned tracks when the script disconnects."""

		log("MixerController.disconnect() called.")
		
		self.song.remove_visible_tracks_listener(self.on_tracks_added_or_deleted)
		#self.song.remove_is_playing_listener(self.on_is_playing_changed)
		#self.song.remove_loop_listener(self._on_loop_changed)
		
		for strip in self._strips:
			strip.set_assigned_track(None)

		for track in self._assigned_tracks:
			if track and track.name_has_listener(self.on_track_name_changed):
				track.remove_name_listener(self.on_track_name_changed)


	################################################################################################################


	def _get_filtered_tracks(self) -> tuple[Live.Track.Track, ...]:
		
		if self._layout_mode == LayoutMode.STANDARD: # All Tracks (standard) 
			return tuple(self.song.visible_tracks) + tuple(self.song.return_tracks) + (self.song.master_track,)
		elif self._layout_mode == LayoutMode.RETURNS:  # Returns Only
			return tuple(self.song.return_tracks)
		else:  # Tracks Only
			return tuple(self.song.visible_tracks)
		

	################################################################################################################


	def is_arm_exclusive(self) -> bool:
		return self.control_surface.song.exclusive_arm


	################################################################################################################
	
	
	def _on_btn_in_top_row_pressed(self, value, sender: ButtonElement) -> None:

		log(f"MixerComponent._on_btn_in_top_row_pressed({value}, {sender}) called.")

		cc: int = sender.original_identifier()
		# midi_channel = sender.original_channel()	
		# msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)

		channel_strip = self._strips[cc - Constants.Mixer.BUTTONS_TOP_BASE]

		if value == Constants.Hardware.BUTTON_PRESSED:
			channel_strip.top_row_button_pressed()
		

	################################################################################################################
	
	
	def _on_btn_in_btm_row_pressed(self, value, sender: ButtonElement) -> None:

		log(f"MixerComponent._on_btn_in_btm_row_pressed({value}, {sender}) called.")
		
		cc = sender.original_identifier()
		# midi_channel = sender.original_channel()	
		# msg_type = sender.message_type() # Returns the type enum (MIDI_CC_TYPE or MIDI_NOTE_TYPE)

		channel_strip = self._strips[cc - Constants.Mixer.BUTTON_BOTTOM_BASE]

		if value == H.BUTTON_PRESSED:
			channel_strip.bottom_row_button_pressed()


	################################################################################################################

	
	def _on_btn_page_down_pressed(self, value) -> None:

		log(f"MixerComponent._on_btn_page_down_pressed({value}) called.")
		
		all_tracks = tuple(self.control_surface.song.visible_tracks) + tuple(self.control_surface.song.return_tracks) + (self.control_surface.song.master_track,)

		if value and len(all_tracks) > self.bank_size:
			self._strip_offset += self.bank_size
			#self._validate_strip_offset()
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()


	################################################################################################################
	
	
	def _on_btn_page_up_pressed(self, value) -> None:
		
		log(f"MixerComponent._on_btn_page_up_pressed({value}) called.")

		all_tracks = tuple(self.control_surface.song.visible_tracks) + tuple(self.control_surface.song.return_tracks) + (self.control_surface.song.master_track,)

		if value and self._strip_offset > 0:
			self._strip_offset -= self.bank_size
			#self._validate_strip_offset()
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()


	################################################################################################################

	
	def _on_btn_sel_bbs_pressed(self, value) -> None:

		log(f"MixerComponent._on_btn_sel_bbs_pressed({value}) called.")

		if value:
			# should revolve around sends
			if self._slider_mode >= SLM.SEND: # If send mode is already sends increment them.
				log(f"\t|----->Doing A.")
				newSendMode = SLM.SEND + ((self._slider_mode + 1) % len(self.song.return_tracks))
				self.set_slider_mode(newSendMode)
			else:  # Else simply go to the first send mode.
				log(f"\t|----->Doing B.")
				self.set_slider_mode(SLM.SEND + self._last_send_index)
				

	################################################################################################################

	
	def _on_btn_sel_faders_pressed(self, value) -> None:
		log(f"MixerComponent._on_btn_sel_faders_pressed({value}) called.")

		if value:
			if self._slider_mode != SLM.VOLUME:

				self.set_slider_mode(SLM.VOLUME)

			else:
				self._layout_mode = list(LayoutMode)[((self._layout_mode.value[0] + 1) % len(LayoutMode))]
				self._display_component.show_timed_message(f"{self._layout_mode.value[1]}", 2.0, True, ROW.TR)
				self._strip_offset = 0 # Reset the offset.
				self.reassign_strips()
				self.control_surface.request_rebuild_midi_map()


	################################################################################################################
	
	
	def _on_btn_sel_tbs_pressed(self, value) -> None:

		log(f"MixerComponent._on_btn_sel_tbs_pressed({value}) called.")

		if value:
			self.set_slider_mode(SLM.PAN)


	################################################################################################################


	def on_tracks_added_or_deleted(self) -> None:
		
		log("MixerController.on_tracks_added_or_deleted called().")
		
		#self._validate_strip_offset()
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map()


	################################################################################################################


	def on_track_name_changed(self) -> None:
		self.reassign_strips()


	################################################################################################################


	def reassign_strips(self) -> None:
		
		log("MixerController.reassign_strips() called.")

		# Remove existing listeners.
		for track in self._assigned_tracks:
			if track and track.name_has_listener(self.on_track_name_changed):
				track.remove_name_listener(self.on_track_name_changed)

		# Reset assigned tracks list.
		self._assigned_tracks = []
		# Get tracks based on display mode
		tracks = self._get_filtered_tracks()

		# tracks_str = ''.join('\t\t\t' + str(track) + '\n' for track in tracks)
		# log(f"\t----->DisplayMode: {self._layout_mode.value[1]}  Tracks:\n{tracks_str}")

		track_names = []
		parameters = []
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
				track.add_name_listener(self.on_track_name_changed)
				self._assigned_tracks.append(track)
			
			else:
				strip.set_assigned_track(None)
				track_names.append("")
				parameters.append(None)
			
	
		self._display_component.setup_right_display(track_names, parameters)
		#self.control_surface.request_rebuild_midi_map() # We don't do it here if something has changed then it needs
		# to be done
		
		log("<-----Returning from MixerController.reassign_strips()")
		

	################################################################################################################


	def receive_midi_cc(self, cc_no, cc_value):
		"""Route incoming CC events for mixer navigation and transport control."""
		
		log(f"MixerController.receive_midi_cc({cc_no}, {cc_value}) called.")
			
		if cc_no in Constants.Mixer.SLIDERS:
			channel_strip = self._strips[cc_no - Constants.Mixer.SLIDER_BASE]
			channel_strip.slider_moved(cc_value)

		else:
			log("\t|----->Midi cc not handled by MixerController.")

		log(f"<-----Returning from MixerController.receive_midi_cc({cc_no}, {cc_value}).")
		return None


	################################################################################################################


	@override
	def refresh_state(self):
		
		log("MixerController.refresh_state() called.")
		
		self.update_selected_row_leds()
		self.reassign_strips()
		self.control_surface.request_rebuild_midi_map() # <---- Not sure if required here.
		# self._lock_enquiry_delay = 3
		
		log("<-----Returning from MixerController.refresh_state().")


	################################################################################################################


	def set_selected_track(self, track):
		if track:
			self.control_surface.song.view.selected_track = track


	################################################################################################################


	def set_slider_mode(self, new_mode: int):

		log(f"DisplayComponent.set_slider_mode({new_mode}) called.")

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

			self.update_selected_row_leds()
			self.reassign_strips()
			self.control_surface.request_rebuild_midi_map()



	################################################################################################################


	def track_about_to_arm(self, track):
		
		if track and self.control_surface.song.exclusive_arm:
			for candidate in self.control_surface.song.tracks:
				
				if candidate.can_be_armed and candidate.arm and candidate != track:
					candidate.arm = False


	################################################################################################################


	@override
	def update(self):
		log("MixerComponent.update() called.")


	################################################################################################################


	@override
	def update_display(self):
		pass
		# if self._lock_enquiry_delay > 0:
		# 	self._lock_enquiry_delay -= 1
			
		# 	if self._lock_enquiry_delay == 0:
		# 		self.send_midi((176, 103, 1))
		
		# if self._rewind_button_down:
		# 	self.song.jump_by(-FORW_REW_JUMP_BY_AMOUNT)
		
		# if self._forward_button_down:
		# 	self.song.jump_by(FORW_REW_JUMP_BY_AMOUNT)


	################################################################################################################


	def update_selected_row_leds(self):
		
		if self._slider_mode == SLM.VOLUME:
			
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_PRESSED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_RELEASED))

		elif self._slider_mode == SLM.PAN:
			
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_PRESSED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_RELEASED))
		
		elif self._slider_mode >= SLM.SEND:
			
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((M.START_BYTE, Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_PRESSED))


	################################################################################################################


	# def validate_slider_mode(self):
	# 	if self._slider_mode - SLM.SEND >= len(self.song.return_tracks):
	# 		self._slider_mode = SLM.VOLUME


	################################################################################################################


	def _validate_strip_offset(self) -> None:

		# Get filtered tracks (same as reassign_strips)
		tracks = self._get_filtered_tracks()

		# if not tracks:
		# 	self._strip_offset = 0
		# 	return

		# Calculate the largest multiple of bank_size that is <= len(tracks) - 1
		# This gives us: 0, bank_size, 2*bank_size, ... up to the last full/partial bank
		max_offset = max(0, ((len(tracks) - 1) // self.bank_size) * self.bank_size)
		
		# Clamp to valid range
		self._strip_offset = min(self._strip_offset, max_offset)
		self._strip_offset = max(0, self._strip_offset)
		
		# Align to bank_size (ensures offset is always 0, bank_size, 2*bank_size, ...)
		self._strip_offset = (self._strip_offset // self.bank_size) * self.bank_size


	################################################################################################################


	# def on_is_playing_changed(self):
		
	# 	if self._transport_locked or self.support_mkII():
			
	# 		if self._parent.song.is_playing:
				
	# 			self.send_midi((M.START_BYTE, 51, Constants.Hardware.BUTTON_PRESSED))
	# 			self.send_midi((M.START_BYTE, 50, Constants.Hardware.BUTTON_RELEASED))
			
	# 		else:
	# 			self.send_midi((M.START_BYTE, 51, Constants.Hardware.BUTTON_RELEASED))
	# 			self.send_midi((M.START_BYTE, 50, Constants.Hardware.BUTTON_PRESSED))


	################################################################################################################


####################################################################################################################



class MixerChannelStrip(object):
	"""Represent one mixer strip with mute, arm, and slider behaviour."""

	################################################################################################################

	def __init__(self, mixer_controller_parent: MixerComponent, index: int):

		self._mixer_controller : MixerComponent = mixer_controller_parent
		self._index : int = index
		self._assigned_track : Live.Track.Track | None = None
		# self._control_second_button = True

	################################################################################################################


	@property
	def song(self) -> Live.Song.Song:
		return self._mixer_controller.song


	################################################################################################################


	def assigned_track(self) -> Live.Track.Track | None:
		return self._assigned_track


	################################################################################################################


	def set_assigned_track(self, track: Live.Track.Track | None):

		#if self._assigned_track is not None:
			#if self._assigned_track != self.song.master_track:
				#self._assigned_track.remove_mute_listener(self._on_mute_changed)
			#if self._assigned_track.can_be_armed:
				#self._assigned_track.remove_arm_listener(self._on_arm_changed)

		self._assigned_track = track
		#if self._assigned_track is not None:
			#if self._assigned_track != self.song.master_track:
				#self._assigned_track.add_mute_listener(self._on_mute_changed)
			#if self._assigned_track.can_be_armed:
				#self._assigned_track.add_arm_listener(self._on_arm_changed)

		#self._on_mute_changed()
		#self._on_arm_changed()


	################################################################################################################


	def slider_parameter(self) -> Live.DeviceParameter.DeviceParameter | None:
		"""Gets the actual Live.DeviceParameter currently controlled by the slider."""
		
		if self._assigned_track is not None:
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


	def slider_moved(self, cc_value: int) -> None:

		log(f"MixerController.slider_moved({cc_value}) called.")
		parameter = self.slider_parameter() # get the parameter.

		if parameter and hasattr(parameter, "min") and hasattr(parameter, "max") and parameter.max != parameter.min:
			parameter.value = parameter.min + (parameter.max - parameter.min) * (float(cc_value) / 127.0)


	################################################################################################################


	def take_control_of_second_button(self, take_control : bool) -> None:
		pass
		# if self._mixer_controller.support_mkII():
			
		# 	self._mixer_controller.parent.send_midi(
		# 		(
		# 			self._mixer_controller.cc_status_byte(),
		# 			self._index + Constants.Mixer.BUTTON_BOTTOM_BASE,
		# 			0,
		# 		)
		# 	)
		#self._control_second_button = take_control # <--- Would appear to do nothing.
		#self._on_mute_changed() 
		#self._on_arm_changed()


	################################################################################################################


	def top_row_button_pressed(self) -> None:
		
		if self._assigned_track and self._assigned_track in tuple(self.song.visible_tracks) + tuple(self.song.return_tracks):
			log("\t----->Muting track.")
			self._assigned_track.mute = not self._assigned_track.mute


	################################################################################################################


	def bottom_row_button_pressed(self) -> None:

		if self._assigned_track and self._assigned_track in self.song.visible_tracks:
			
			self._mixer_controller.track_about_to_arm(self._assigned_track)
			self._assigned_track.arm = not self._assigned_track.arm
			log("\t----->Arming track.")

			if self._assigned_track.arm and self._assigned_track.view.select_instrument():
				self._mixer_controller.set_selected_track(self._assigned_track)
				log("\t----->Setting track selected.")


	################################################################################################################


	def _on_mute_changed(self) -> None:
		pass
		# if self._mixer_controller.support_mkII() and self._assigned_track is not None:
		# 	value = 0
		# 	if self._assigned_track in tuple(self.song.tracks) + tuple(self.song.return_tracks):
		# 		value = 1 if not self._assigned_track.mute else 0
		# 	self._mixer_controller.parent.send_midi(
		# 		(
		# 			self._mixer_controller.cc_status_byte(),
		# 			self._index + Constants.Mixer.BUTTONS_TOP_BASE
		# 		)
		# 	)

	################################################################################################################


	def _on_arm_changed(self) -> None:
		pass
		# if self._control_second_button or self._mixer_controller.support_mkII():
		# 	value = 0
		# 	if self._assigned_track and self._assigned_track in self.song.tracks and self._assigned_track.can_be_armed and self._assigned_track.arm:
		# 		value = 1
		# 	self._mixer_controller.send_midi(
		# 		(
		# 			self._mixer_controller.cc_status_byte(),
		# 			self._index + Constants.Mixer.BUTTON_BOTTOM_BASE,
		# 			value,
		# 		)
		# 	)



####################################################################################################################
####################################################################################################################
