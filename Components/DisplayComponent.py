####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
####################################################################################################################
#
# DisplayComponent.py
####################################################################################################################

"""Controller logic for the Remote SL display strips."""

from Live.DeviceParameter import DeviceParameter

from ableton.v2.control_surface import Component
from ableton.v3.base import as_ascii

from enum import Enum, IntEnum
from typing import Optional, Sequence
from dataclasses import dataclass

from copy import deepcopy

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.

if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from ..consts import Constants, H, SYX
from ..RemoteSL_Logger import log, log_info, log_midi, log_error, log_verbose


__all__ = ['DisplayComponent', 'ROW', 'DISPLAY']

####################################################################################################################



class DISPLAY(Enum):
	"""ENUM for left and right display"""
	LEFT = 0
	RIGHT = 1


####################################################################################################################


class ROW(IntEnum):
	"""Enum for all the rows."""
	TL = 0x01
	TR = 0x02
	BL = 0x03
	BR = 0x04


####################################################################################################################

class _Display:

	@dataclass
	class _DisplayRow:
		text: str = ""
		dirty: bool = True
		def isEmpty(self) -> bool:
			return self.text == ""
	
	def __init__(self):
		self._tl = _Display._DisplayRow()
		self._bl = _Display._DisplayRow()
		self._tr = _Display._DisplayRow()
		self._br = _Display._DisplayRow()


	def copy(self) -> '_Display':
		return deepcopy(self)

	@property
	def dirty(self) -> bool:
		return not all(not row.dirty for row in self.all_rows)

	@property
	def all_rows(self) -> list[_DisplayRow]:
		return [self._DisplayRow("",False), self._tl, self._tr, self._bl, self._br]

	@property
	def left_display_rows(self) -> list[_DisplayRow]:
		return [self._tl, self._bl]

	@property
	def right_display_rows(self) -> list[_DisplayRow]:
		return [self._tr, self._br]

	def all_rows_empty(self) -> bool:
		return all(row.isEmpty() for row in self.all_rows)

	def left_display_empty(self) -> bool:
		return all(row.isEmpty() for row in self.left_display_rows)

	def right_display_empty(self) -> bool:
		return all(row.isEmpty() for row in self.right_display_rows)

	def set_rows_clean(self, *rows) -> None:
		for row in rows:
			self.all_rows[row].dirty = False
			
	def set_all_clean(self) -> None:
		self.set_rows_clean(ROW.TL, ROW.TR, ROW.BL, ROW.BR)

	def set_all_dirty(self) -> None:
		for row in self.all_rows:
			row.dirty = True

	def set_row_string(self, row: ROW, text: str) -> None:
		# Cut to row length

		log(f"_Display.set_row_string(row: {row}, {text}")

		text = text[:H.NUM_CHARS_PER_DISPLAY_LINE]
		# Sets a rows string and checks if matches or not.  Only sets to dirty if changed.
		if row == ROW.TL:
			if self._tl.text != text:
				self._tl.text = text
				self._tl.dirty = True
		elif row == ROW.TR:
			if self._tr.text != text:
				self._tr.text = text
				self._tr.dirty = True
		elif row == ROW.BL:
			if self._bl.text != text:
				self._bl.text = text
				self._bl.dirty = True
		elif row == ROW.BR:
			if self._br.text != text:
				self._br.text = text
				self._br.dirty = True

	def clear_row(self, row: ROW):
		self.set_row_string(row, "")


####################################################################################################################


def format_param(param: Optional[DeviceParameter], decimals=2) -> str:
	"""Takes a device parameter and formats it to 2dp or as specified and keeps unit."""

	if param is None:
		return ""

	full = str(param)  # e.g., "-3.2 dB"

	# Split into number and unit
	parts = full.rsplit(' ', 1)
	if len(parts) == 2:
		value_str, unit = parts
		# Parse the numeric part, format it, then reattach the unit
		try:
			value = float(value_str)
			return f"{value:.{decimals}f} {unit}"
		except ValueError:
			return full
	else:
		# No unit – just format the value
		try:
			value = float(full)
			return f"{value:.{decimals}f}"
		except ValueError:
			return full


####################################################################################################################


class DisplayComponent(Component):
	"""Handle the two display strips and their associated text updates."""

	# Display could be represented as 2 lines of 8 strings.
	Str8Tup = tuple[str, str, str, str, str, str, str, str]
	DisplayPatch = tuple[Str8Tup, Str8Tup]


	################################################################################################################


	def __init__(self, control_surface, name='DisplayComponent', *a, **k):

		log_info(f"DisplayComponent.__init__({control_surface},{name}) called.")

		super().__init__(name=name, *a, **k)
		
		self._control_surface = control_surface

		# Initialize a blank display.  Created dirty.
		self._currentDisplay: _Display = _Display()

		# Memory for displaying popups.
		self._cachedDisplay: _Display = _Display()
		self._message_popup_ticks = -1 	# -1 means timer disabled positive is running and 0 means fire.


		# # Do you need this detail surely 4 strings would be sufficient for the display and you could format them all in advance.
		# self.left_strip_names =		 	[str() for _ in range(H.NUM_CONTROLS_PER_ROW)]
		# self.left_strip_parameters:  Sequence[Optional[DeviceParameter]] = 	[None for  _ in range(H.NUM_CONTROLS_PER_ROW)]
		# self.right_strip_names =		[str() for _ in range(H.NUM_CONTROLS_PER_ROW)]
		# self.right_strip_parameters: Sequence[Optional[DeviceParameter]] = 	[None for  _ in range(H.NUM_CONTROLS_PER_ROW)]


		#self.refresh_state()

		log(f"<-----Returning from DisplayComponent.__init__({control_surface},{name})")

	
	################################################################################################################

	@property
	def _dirty(self) -> bool:
		return self._currentDisplay.dirty

	@_dirty.setter
	def _dirty(self, newValue: bool) -> None:
		if newValue == True:
			self._currentDisplay.set_all_dirty()
		else:
			self._currentDisplay.set_all_clean()


	@property
	def control_surface(self):
		"""The control surface parent object."""
		return self._control_surface


	################################################################################################################


	def clear_display_row(self, row: ROW):
		"""Clear a row."""

		if (row == ROW.TL):
			self.control_surface.send_midi(SYX.CLEAR_ROW_TL)
		elif (row == ROW.TR):
			self.control_surface.send_midi(SYX.CLEAR_ROW_TR)
		elif (row == ROW.BL):
			self.control_surface.send_midi(SYX.CLEAR_ROW_BL)
		elif (row == ROW.BR):
			self.control_surface.send_midi(SYX.CLEAR_ROW_BR)


	################################################################################################################
		

	def clear_display(self, display: DISPLAY):
		"""Clear the one whole display."""
		
		if(display == DISPLAY.LEFT):
			self.control_surface.send_midi(SYX.CLEAR_LEFT_DISPLAY)
		else:
			self.control_surface.send_midi(SYX.CLEAR_RIGHT_DISPLAY)


	################################################################################################################
	

	def clear_displays(self):
		"""Send the sysex command that clears both the left and right displays."""

		self.control_surface.send_midi(SYX.CLEAR_BOTH_DISPLAYS)


	################################################################################################################


	@override
	def disconnect(self):
		"""Clear the hardware displays when the controller is disconnected."""

		log(f"DisplayComponent.disconnect() called.")

		self._currentDisplay = _Display()
		self._cachedDisplay = _Display()

		self.clear_displays()
		self.show_offline_message()

		super().disconnect()


	################################################################################################################


	def _generate_display_strip(self, names: list[str], parameters: Sequence[Optional[DeviceParameter]]) -> tuple[str, str]:

		if len(names) != H.NUM_CONTROLS_PER_ROW or len(parameters) != H.NUM_CONTROLS_PER_ROW:
			log_error("Wrong number of controls sent to _generate_display_strip.")
			raise RuntimeError("Wrong number of controls sent to _generate_display_strip.")

		top_line = ""
		for name in names:
			top_line += self._generate_strip_string(name)

		bottom_line = ""
		for param in parameters:
			bottom_line += self._generate_strip_string(format_param(param))

		return (top_line, bottom_line)
		


	################################################################################################################

	def _generate_strip_string(self, display_string: str) -> str:
		"""Create a padded display string for a single strip."""

		# Blank returns all spaces basically.
		if not display_string:
			return " " * Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP

		display_string = display_string.strip()

		# Special rules for something ending with dB then it takes away the dB.
		# TODO: Would be better maybe to limit to 2decimal places.
		if (
			len(display_string) > Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP - 1
			and display_string.endswith("dB")
			and "." in display_string
		):
			#log(f"dB stripped from {display_string}")
			display_string = display_string[:-2]

		return display_string[:Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP].ljust(Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP)


	################################################################################################################


	def _is_timed_message_being_displayed(self) -> bool: 
		return self._message_popup_ticks != -1


	################################################################################################################


	@override
	def refresh_state(self):
		"""Reset the cached display state for the rows."""

		log("DisplayComponent.refresh_state() called.")
		# ? is this even called???
		raise RuntimeError("DisplayComponent.refresh_state was called.")
		log("<-----Returning from DisplayComponent.refresh_state().")


	################################################################################################################


	def _send_display_string(self, message: str, row: ROW, offset:int = 0):
		"""This is the function that sends a fully formatted string to the hardware."""

		final_message = " " * offset + message # add the offset to the string.

		# Fill to the end of the display line.
		if len(final_message) < Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE:
			fill_up =Constants.Hardware. NUM_CHARS_PER_DISPLAY_LINE - len(final_message)
			final_message = final_message + " " * fill_up

		# Or cut to length.
		elif len(final_message) >= Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE:
			final_message = final_message[0:Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE]

		sysex_pos = (0, row) # col: 0, row: row_id
		sysex_text = tuple(as_ascii(final_message))

		full_syx_msg = SYX.BEG_SYX + SYX.CMD.LCD_TEXT + SYX.SUB_CMD.TXT.CURS_ADDR + (sysex_pos) + SYX.SUB_CMD.TXT.TEXT_STRING + sysex_text + SYX.END_MSG

		#if self._displayed_rows_cache[row] != full_syx_msg:

		log_midi(f"\t|----->Str to display: ", full_syx_msg)

		#self._displayed_rows_cache[row] = full_syx_msg
		self.control_surface.send_midi(full_syx_msg)


	################################################################################################################


	def setup_display_for_params(self, display: DISPLAY, names: list[str], parameters: Sequence[Optional[DeviceParameter]]):
		"""Here we generate strings for showing parameters on the left display"""

		display_to_set = self._cachedDisplay if self._is_timed_message_being_displayed() else self._currentDisplay

		log(f"DisplayComponent.setup_display_for_params({display}, {names}, {parameters} called.)")

		rows = self._generate_display_strip(names, parameters)
		display_to_set.set_row_string(ROW.TL if display == DISPLAY.LEFT else ROW.TR, rows[0])
		display_to_set.set_row_string(ROW.BL if display == DISPLAY.LEFT else ROW.BR, rows[1])


	################################################################################################################


	def show_button_controls_list(self, controls_top: tuple[str,str,str,str,str,str,str,str], display: DISPLAY):
		"""Show a list of controls over 2 lines """
		# TODO: Rename to setup_display_for_controls and write a function to make a line of 2 row controls
		raise NotImplementedError()

	################################################################################################################


	def show_offline_message(self):
		"""Show the Ableton is OFFLINE message."""
		self.write_centred_display_rows("Ableton is OFFLINE", ROW.TL, ROW.TR)


	################################################################################################################


	def show_timed_message(self, message_text: str, duration_seconds: float = 3.0, centred:bool = False, *rows: ROW):
		"""Public endpoint to cleanly show a fluid, full-row message on a strict hardware hold timer."""

		log_info(f"DISPLAY ENGINE: Triggering timed message popup -> '{message_text}'")

		# TODO: At some point you need to work out what happens when 1 timed message overwrites another...????
		#  		probably you want to queue them but keep the original display.

		# Convert seconds to clock frames (update_display runs roughly 5 times a second)

		if not rows:
			rows = (ROW.TL,)

		# only cache if not cached already.
		if not self._is_timed_message_being_displayed():
			self._cachedDisplay = self._currentDisplay.copy()
			self._cachedDisplay.set_all_dirty()

		# We need to be able to override the current popup so we disable the timer.
		# This means write rows will write to the current display instead of the cached.
		if self._is_timed_message_being_displayed():
			self._message_popup_ticks = -1 
		
		if not centred:
			self.write_display_rows(message_text, *rows)
		else:
			self.write_centred_display_rows(message_text, *rows)

		# Now we set the timer.
		self._message_popup_ticks = int(duration_seconds * 5)
		display = self._currentDisplay

		# Convoluted way to clear other row of display used for message if it's not also used for the message.
		for row in ROW:
			if row not in rows:
				if row == ROW.TL and ROW.BL in rows:
					display.clear_row(ROW.TL)
				elif row == ROW.TR and ROW.BR in rows:
					display.clear_row(ROW.TR)
				elif row == ROW.BL and ROW.TL in rows:
					display.clear_row(ROW.BL)
				elif row == ROW.BR and ROW.TR in rows:
					display.clear_row(ROW.BR)


	################################################################################################################


	@override
	def update(self):
		"""Refresh the display content for the four display rows natively."""

		super().update()

		# Tick the timer and check if expired.
		# -1 is off... 0 is end of timer.
		if (self._message_popup_ticks > -1):
			self._message_popup_ticks -= 1
			
		if self._message_popup_ticks == 0:
			log("DISPLAY ENGINE: Hold timer expired. Releasing screen back to layout matrix.")
			self._currentDisplay = self._cachedDisplay.copy()
			self._dirty = True

		# actually we want to display it.
		# elif self._message_popup_ticks > 0:
		# 	# Keep the screen completely frozen during the active countdown hold
		# 	return None

		if self._dirty:

			if self._currentDisplay.all_rows_empty():
				self.clear_displays()
				self._currentDisplay.set_all_clean()

			elif self._currentDisplay.left_display_empty():
				self.clear_display(DISPLAY.LEFT)
				self._currentDisplay.set_rows_clean(ROW.TL, ROW.BL)

			elif self._currentDisplay.right_display_empty():
				self.clear_display(DISPLAY.RIGHT)
				self._currentDisplay.set_rows_clean(ROW.TL, ROW.BL)
				
			else:

				for row in ROW:

					current_row = self._currentDisplay.all_rows[row]

					log(f"Writing row: {current_row}")

					if current_row.dirty == True:
						self._send_display_string(current_row.text, row, offset=0)
						
			self._dirty = False


	################################################################################################################


	def update_parameter(self, index_of_parameter: int, parameter: DeviceParameter):

		log(f"DisplayComponent.updateParameter({index_of_parameter}, {parameter}) called.")

		display_to_modify = self._currentDisplay if not self._is_timed_message_being_displayed() else self._cachedDisplay
		log(f"Writing to {'current_display' if not self._is_timed_message_being_displayed() else 'cached_display'}.")

		line = display_to_modify.right_display_rows[1].text
		if line == "":
			line = " " * H.NUM_CHARS_PER_DISPLAY_LINE

		log(f"\"{line}\"")
			
		strip = self._generate_strip_string(format_param(parameter))

		new_strips = line[:index_of_parameter * H.NUM_CHARS_PER_DISPLAY_STRIP] + strip + line[(index_of_parameter + 1) * H.NUM_CHARS_PER_DISPLAY_STRIP:]

		display_to_modify.set_row_string(ROW.BR, new_strips)
		

	################################################################################################################


	def write_display_rows(self, text: str, *rows: ROW):
		"""Updates the display string in memory.  Write happens on update."""

		log_verbose(f"DisplayComponent.write_display_rows(\"{text}\", {rows if rows else ''}) called.")
		log(f"Writing to {'current_display' if not self._is_timed_message_being_displayed() else 'cached_display'}.")

		display_to_modify = self._currentDisplay if not self._is_timed_message_being_displayed() else self._cachedDisplay

		if not rows:
			rows = (ROW.TL,)

		for row in rows:
			display_to_modify.set_row_string(row, text)


	################################################################################################################


	def write_centred_display_rows(self, text: str, *rows: ROW):
		"""Updates the display string in memory. Write happens on update."""

		log_verbose(f"DisplayComponent.write_centred_display_rows(\"{text}\", {rows if rows else ''}) called.")

		display_to_modify = self._currentDisplay if not self._is_timed_message_being_displayed() else self._cachedDisplay
		log(f"Writing to {'current_display' if not self._is_timed_message_being_displayed() else 'cached_display'}.")

		if len(rows) == 0:
			rows = (ROW.TL,)

		for row in rows:
			display_to_modify.set_row_string(row, text.center(Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE))


	################################################################################################################



####################################################################################################################
####################################################################################################################

