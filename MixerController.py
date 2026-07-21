####################################################################################################################
# Source Generated with Decompyle++
# File: MixerController.pyc (Python 3.11)
####################################################################################################################

"""Mixer-section controller logic for the Remote SL script."""

from __future__ import annotations	# to avoid the circular reference on RemoteSL and not use quotes...

import Live as Live


import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
    from typing import override
else:
    def override(func):
        return func

from typing import TYPE_CHECKING

from .consts import *
from .RemoteSLComponent import RemoteSLComponent

if TYPE_CHECKING:
	from .RemoteSL import RemoteSL
from .DisplayController import DisplayController
from .myLogger import log

####################################################################################################################

SLIDER_MODE_VOLUME = 0
SLIDER_MODE_PAN = 1
SLIDER_MODE_SEND = 2
FORW_REW_JUMP_BY_AMOUNT = 1


####################################################################################################################

class MixerController(RemoteSLComponent):
	"""Handle tracks, transport controls, and slider modes for the mixer section."""

	################################################################################################################

	def __init__(self, remote_sl_parent: RemoteSL, display_controller: DisplayController):
		"""Initialise the mixer controller state and display references."""
		
		RemoteSLComponent.__init__(self, remote_sl_parent)

		self._display_controller = display_controller
		self._parent = remote_sl_parent
		self._forward_button_down = False
		self._rewind_button_down = False
		self._strip_offset = 0
		self._slider_mode = SLIDER_MODE_VOLUME
		self._strips = [MixerChannelStrip(self, index) for index in range(Constants.Hardware.NUM_CONTROLS_PER_ROW)]
		self._assigned_tracks = []
		self._transport_locked = False
		self._lock_enquiry_delay = 0

		self.song.add_visible_tracks_listener(self.on_tracks_added_or_deleted)
		self.song.add_record_mode_listener(self.on_record_mode_changed)
		self.song.add_is_playing_listener(self.on_is_playing_changed)
		self.song.add_loop_listener(self.on_loop_changed)

		self.reassign_strips()


	################################################################################################################


	@override
	def disconnect(self):
		"""Remove listeners and release the assigned tracks when the script disconnects."""

		log("MixerController.disconnect() called.")
		
		self.song.remove_visible_tracks_listener(self.on_tracks_added_or_deleted)
		self.song.remove_record_mode_listener(self.on_record_mode_changed)
		self.song.remove_is_playing_listener(self.on_is_playing_changed)
		self.song.remove_loop_listener(self.on_loop_changed)
		
		for strip in self._strips:
			strip.set_assigned_track(None)

		for track in self._assigned_tracks:
			if track and track.name_has_listener(self.on_track_name_changed):
				track.remove_name_listener(self.on_track_name_changed)


	################################################################################################################


	def remote_sl_parent(self):
		return self._parent


	################################################################################################################


	def slider_mode(self):
		return self._slider_mode


	################################################################################################################


	def receive_midi_cc(self, cc_no, cc_value):
		"""Route incoming CC events for mixer navigation and transport control."""
		
		log(f"MixerController.receive_midi_cc({cc_no}, {cc_value}) called.")
		
		if cc_no in Constants.Mixer.NAVIGATION:
			self.handle_page_up_down_ccs(cc_no, cc_value)
		
		elif cc_no in Constants.Mixer.SELECT_BUTTONS:
			self.handle_select_button_ccs(cc_no, cc_value)
			
		elif cc_no in Constants.Mixer.BUTTONS_TOP_ROW:
			channel_strip = self._strips[cc_no - Constants.Mixer.BUTTONS_TOP_BASE]
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				channel_strip.first_button_pressed()
		
		elif cc_no in Constants.Mixer.BUTTONS_BOTTOM_ROW:
			channel_strip = self._strips[cc_no - Constants.Mixer.BUTTON_BOTTOM_BASE]
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				channel_strip.second_button_pressed()
			
		elif cc_no in Constants.Mixer.SLIDERS:
			channel_strip = self._strips[cc_no - Constants.Mixer.SLIDER_BASE]
			channel_strip.slider_moved(cc_value)
			
		elif cc_no in Constants.Transport.ALL:
			self.handle_transport_ccs(cc_no, cc_value)

		else:
			log("\t|----->Midi cc not handled by MixerController.")

		log(f"<-----Returning from MixerController.receive_midi_cc({cc_no}, {cc_value}).")
		return None



	################################################################################################################


	@override
	def build_midi_map(self, midi_map_handle):
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
			
			Live.MidiMap.forward_midi_cc(self._parent.handle(), midi_map_handle, Constants.Hardware.MIDI_CHANNEL, cc_no)

		for cc_no in Constants.Mixer.FORWARDED_CCS: # + ts_ccs: <--- Removed this as we are handling separately.
			Live.MidiMap.forward_midi_cc(self._parent.handle(), midi_map_handle, Constants.Hardware.MIDI_CHANNEL, cc_no)

		for note in Constants.Mixer.FORWARDED_NOTE:
			Live.MidiMap.forward_midi_note(self._parent.handle(), midi_map_handle, Constants.Hardware.MIDI_CHANNEL, note)

		log(f"<-----Returning from MixerController.build_midi_map({midi_map_handle}).")

	################################################################################################################


	@override
	def refresh_state(self):
		
		log("MixerController.refresh_state() called.")
		
		self.update_selected_row_leds()
		self.reassign_strips()
		self._lock_enquiry_delay = 3
		
		log("<-----Returning from MixerController.refresh_state().")



	################################################################################################################


	@override
	def update_display(self):
		
		if self._lock_enquiry_delay > 0:
			self._lock_enquiry_delay -= 1
			
			if self._lock_enquiry_delay == 0:
				self.send_midi((176, 103, 1))
		
		if self._rewind_button_down:
			self.song.jump_by(-FORW_REW_JUMP_BY_AMOUNT)
		
		if self._forward_button_down:
			self.song.jump_by(FORW_REW_JUMP_BY_AMOUNT)


	################################################################################################################


	def reassign_strips(self):
		
		log("MixerController.reassign_strips() called.")

		track_index = self._strip_offset
		track_names = []
		parameters = []

		for track in self._assigned_tracks:
			if track and track.name_has_listener(self.on_track_name_changed):
				track.remove_name_listener(self.on_track_name_changed)

		self._assigned_tracks = []
		all_tracks = tuple(self.song.visible_tracks) + tuple(self.song.return_tracks) + (self.song.master_track,)

		for strip in self._strips:
			
			if track_index < len(all_tracks):
				
				track = all_tracks[track_index]
				strip.set_assigned_track(track)
				track_names.append(track.name)
				parameters.append(strip.slider_parameter())
				track.add_name_listener(self.on_track_name_changed)
				self._assigned_tracks.append(track)
			
			else:
				
				strip.set_assigned_track(None)
				track_names.append("")
				parameters.append(None)
			
			track_index += 1

		self._display_controller.setup_right_display(track_names, parameters)
		self.request_rebuild_midi_map()
		
		log("<-----Returning from MixerController.reassign_strips()")

		# if self.support_mkII():
			
		# 	page_up_value = Constants.Hardware.BUTTON_RELEASED
		# 	page_down_value = Constants.Hardware.BUTTON_RELEASED
			
		# 	if len(all_tracks) > Constants.Hardware.NUM_CONTROLS_PER_ROW and self._strip_offset < len(all_tracks) - Constants.Hardware.NUM_CONTROLS_PER_ROW:
		# 		page_up_value = Constants.Hardware.BUTTON_PRESSED

		# 	if self._strip_offset > 0:
		# 		page_down_value = Constants.Hardware.BUTTON_PRESSED

		# 	self.send_midi((self.cc_status_byte(), MX_DISPLAY_PAGE_UP, page_up_value))
		# 	self.send_midi((self.cc_status_byte(), MX_DISPLAY_PAGE_DOWN, page_down_value))


	################################################################################################################


	def handle_page_up_down_ccs(self, cc_no, cc_value):
		
	
		all_tracks = tuple(self._parent.song.visible_tracks) + tuple(self._parent.song.return_tracks) + (self._parent.song.master_track,)
		
		if cc_no == Constants.Mixer.PAGE_UP:
			if cc_value == Constants.Hardware.BUTTON_PRESSED and len(all_tracks) > Constants.Hardware.NUM_CONTROLS_PER_ROW:
				
				self.validate_strip_offset()
				self.reassign_strips()
			
			return None

		if cc_no == Constants.Mixer.PAGE_DOWN:
			if cc_value == Constants.Hardware.BUTTON_PRESSED and self._strip_offset > 0:
				
				self.validate_strip_offset()
				self.reassign_strips()
			
			return None


	################################################################################################################


	def handle_select_button_ccs(self, cc_no, cc_value):
		
		if cc_no == Constants.Mixer.SELECT_SLIDERS:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				
				self.set_slider_mode(SLIDER_MODE_VOLUME)
			
			return None

		if cc_no == Constants.Mixer.SELECT_BUTTONS_TOP:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				
				self.set_slider_mode(SLIDER_MODE_PAN)
			
			return None

		if cc_no == Constants.Mixer.SELECT_BUTTONS_BOTTOM:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				
				self.set_slider_mode(SLIDER_MODE_SEND)
			
			return None


	################################################################################################################


	def handle_transport_ccs(self, cc_no, cc_value):
		
		if cc_no == Constants.Transport.REWIND:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self._rewind_button_down = True
				self._parent.song.jump_by(-FORW_REW_JUMP_BY_AMOUNT)
			else:
				self._rewind_button_down = False
			return None

		if cc_no == Constants.Transport.FORWARD:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self._forward_button_down = True
				self._parent.song.jump_by(FORW_REW_JUMP_BY_AMOUNT)
			else:
				self._forward_button_down = False
			return None

		if cc_no == Constants.Transport.STOP:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				#self._parent.song.is_playing = False
				self._parent.song.stop_playing()
			return None

		if cc_no == Constants.Transport.PLAY:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self._parent.song.start_playing()
			return None

		if cc_no == Constants.Transport.LOOP:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self._parent.song.loop = not self._parent.song.loop
			return None

		if cc_no == Constants.Transport.RECORD:
			if cc_value == Constants.Hardware.BUTTON_PRESSED:
				self._parent.song.record_mode = not self._parent.song.record_mode
			return None

		if cc_no == Constants.Transport.LOCK:
			self._transport_locked = cc_value != Constants.Hardware.BUTTON_RELEASED
			self.on_transport_lock_changed()


	################################################################################################################


	def on_transport_lock_changed(self):
		
		for strip in self._strips:
			strip.take_control_of_second_button(not self._transport_locked)

		if self._transport_locked:
			self.on_is_playing_changed()
			self.on_loop_changed()
			self.on_record_mode_changed()


	################################################################################################################


	def on_tracks_added_or_deleted(self):
		
		log("MixerController.on_tracks_added_or_deleted called().")
		
		self.validate_strip_offset()
		self.validate_slider_mode()
		self.reassign_strips()


	################################################################################################################


	def on_track_name_changed(self):
		self.reassign_strips()


	################################################################################################################


	def validate_strip_offset(self):
		all_tracks = tuple(self._parent.song.visible_tracks) + tuple(self._parent.song.return_tracks) + (self._parent.song.master_track,)
		self._strip_offset = min(self._strip_offset, len(all_tracks) - 1)
		self._strip_offset = max(0, self._strip_offset)


	################################################################################################################


	def validate_slider_mode(self):
		if self._slider_mode - SLIDER_MODE_SEND >= len(self._parent.song.return_tracks):
			self._slider_mode = SLIDER_MODE_VOLUME


	################################################################################################################


	def set_slider_mode(self, new_mode):
		if self._slider_mode >= SLIDER_MODE_SEND and new_mode >= SLIDER_MODE_SEND:
			
			if self._slider_mode - SLIDER_MODE_SEND + 1 < len(self._parent.song.return_tracks):
				self._slider_mode += 1
			else:
				self._slider_mode = SLIDER_MODE_SEND
			
			self.update_selected_row_leds()
			self.reassign_strips()

		elif self._slider_mode != new_mode:
			
			self._slider_mode = new_mode
			self.update_selected_row_leds()
			self.reassign_strips()


	################################################################################################################


	def update_selected_row_leds(self):
		
		if self._slider_mode == SLIDER_MODE_VOLUME:
			
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_PRESSED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_RELEASED))
		
		elif self._slider_mode == SLIDER_MODE_PAN:
			
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_PRESSED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_RELEASED))
		
		elif self._slider_mode >= SLIDER_MODE_SEND:
			
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_SLIDERS, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_TOP, Constants.Hardware.BUTTON_RELEASED))
			self.send_midi((self.cc_status_byte(), Constants.Mixer.SELECT_BUTTONS_BOTTOM, Constants.Hardware.BUTTON_PRESSED))


	################################################################################################################


	def on_record_mode_changed(self):
		
		if not self._transport_locked or self.support_mkII():
			
			record_cc = Constants.Transport.RECORD

			if self.support_mkII():
				record_cc = 53

			record_value = Constants.Hardware.BUTTON_PRESSED

			if not self._parent.song.record_mode:
				record_value = Constants.Hardware.BUTTON_RELEASED

			self.send_midi((self.cc_status_byte(), record_cc, record_value))


	################################################################################################################


	def on_is_playing_changed(self):
		
		if self._transport_locked or self.support_mkII():
			
			if self._parent.song.is_playing:
				
				self.send_midi((self.cc_status_byte(), 51, Constants.Hardware.BUTTON_PRESSED))
				self.send_midi((self.cc_status_byte(), 50, Constants.Hardware.BUTTON_RELEASED))
			
			else:
				self.send_midi((self.cc_status_byte(), 51, Constants.Hardware.BUTTON_RELEASED))
				self.send_midi((self.cc_status_byte(), 50, Constants.Hardware.BUTTON_PRESSED))


	################################################################################################################


	def on_loop_changed(self):
		
		if self._transport_locked or self.support_mkII():
			if self.song.loop:
				self.send_midi((self.cc_status_byte(), 52, Constants.Hardware.BUTTON_PRESSED))
			else:
				self.send_midi((self.cc_status_byte(), 52, Constants.Hardware.BUTTON_RELEASED))


	################################################################################################################


	def is_arm_exclusive(self):
		return self._parent.song.exclusive_arm


	################################################################################################################


	def set_selected_track(self, track):
		if track:
			self._parent.song.view.selected_track = track


	################################################################################################################


	def track_about_to_arm(self, track):
		
		if track and self._parent.song.exclusive_arm:
			for candidate in self._parent.song.tracks:
				
				if candidate.can_be_armed and candidate.arm and candidate != track:
					candidate.arm = False



####################################################################################################################




class MixerChannelStrip(object):
	"""Represent one mixer strip with mute, arm, and slider behaviour."""

	################################################################################################################

	def __init__(self, mixer_controller_parent, index):
		self._mixer_controller = mixer_controller_parent
		self._index = index
		self._assigned_track = None
		self._control_second_button = True

	################################################################################################################


	@property
	def song(self):
		return self._mixer_controller.song


	################################################################################################################


	def assigned_track(self):
		return self._assigned_track


	################################################################################################################


	def set_assigned_track(self, track):
		if self._assigned_track is not None:
			if self._assigned_track != self.song.master_track:
				self._assigned_track.remove_mute_listener(self._on_mute_changed)
			if self._assigned_track.can_be_armed:
				self._assigned_track.remove_arm_listener(self._on_arm_changed)

		self._assigned_track = track
		if self._assigned_track is not None:
			if self._assigned_track != self.song.master_track:
				self._assigned_track.add_mute_listener(self._on_mute_changed)
			if self._assigned_track.can_be_armed:
				self._assigned_track.add_arm_listener(self._on_arm_changed)

		self._on_mute_changed()
		self._on_arm_changed()


	################################################################################################################


	def slider_parameter(self):
		
		if self._assigned_track:
			slider_mode = self._mixer_controller.slider_mode()
			if slider_mode == SLIDER_MODE_VOLUME:
				return self._assigned_track.mixer_device.volume
			if slider_mode == SLIDER_MODE_PAN:
				return self._assigned_track.mixer_device.panning
			if slider_mode >= SLIDER_MODE_SEND:
				send_index = slider_mode - SLIDER_MODE_SEND
				if send_index < len(self._assigned_track.mixer_device.sends):
					return self._assigned_track.mixer_device.sends[send_index]
		return None


	################################################################################################################


	def slider_moved(self, cc_value):
		parameter = self.slider_parameter()
		if parameter and hasattr(parameter, "min") and hasattr(parameter, "max") and parameter.max != parameter.min:
			parameter.value = parameter.min + (parameter.max - parameter.min) * (float(cc_value) / 127.0)


	################################################################################################################


	def take_control_of_second_button(self, take_control):
		
		if self._mixer_controller.support_mkII():
			
			self._mixer_controller.remote_sl_parent().send_midi(
				(
					self._mixer_controller.cc_status_byte(),
					self._index + Constants.Mixer.BUTTON_BOTTOM_BASE,
					0,
				)
			)
		self._control_second_button = take_control
		self._on_mute_changed()
		self._on_arm_changed()


	################################################################################################################


	def first_button_pressed(self):
		if self._assigned_track and self._assigned_track in tuple(self.song.visible_tracks) + tuple(self.song.return_tracks):
			self._assigned_track.mute = not self._assigned_track.mute


	################################################################################################################


	def second_button_pressed(self):
		if self._assigned_track and self._assigned_track in self.song.visible_tracks:
			self._mixer_controller.track_about_to_arm(self._assigned_track)
			self._assigned_track.arm = not self._assigned_track.arm
			if self._assigned_track.arm and self._assigned_track.view.select_instrument():
				self._mixer_controller.set_selected_track(self._assigned_track)


	################################################################################################################


	def _on_mute_changed(self):
		if self._mixer_controller.support_mkII() and self._assigned_track is not None:
			value = 0
			if self._assigned_track in tuple(self.song.tracks) + tuple(self.song.return_tracks):
				value = 1 if not self._assigned_track.mute else 0
			self._mixer_controller.remote_sl_parent().send_midi(
				(
					self._mixer_controller.cc_status_byte(),
					self._index + Constants.Mixer.BUTTONS_TOP_BASE
				)
			)

	################################################################################################################


	def _on_arm_changed(self):
		if self._control_second_button or self._mixer_controller.support_mkII():
			value = 0
			if self._assigned_track and self._assigned_track in self.song.tracks and self._assigned_track.can_be_armed and self._assigned_track.arm:
				value = 1
			self._mixer_controller.send_midi(
				(
					self._mixer_controller.cc_status_byte(),
					self._index + Constants.Mixer.BUTTON_BOTTOM_BASE,
					value,
				)
			)



####################################################################################################################
####################################################################################################################
