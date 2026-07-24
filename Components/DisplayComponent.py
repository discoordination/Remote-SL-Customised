####################################################################################################################
# Source Generated with Decompyle++
# File: DisplayComponent.pyc (Python 3.11)
####################################################################################################################

"""Controller logic for the Remote SL display strips."""

from ableton.v2.control_surface import Component
from ableton.v3.base import as_ascii

from enum import Enum, IntEnum
import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
	from typing import override
else:
	def override(func):
		return func

from ..consts import Constants, H, SYX
from ..myLogger import log



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


class DisplayComponent(Component):
	"""Handle the two display strips and their associated text updates."""


	################################################################################################################


	def __init__(self, control_surface, name='DisplayComponent', *a, **k):

		log(f"DisplayComponent.__init__({control_surface},{name}) called.")

		super().__init__(name=name, *a, **k)
		
		self._control_surface = control_surface

		self.left_strip_names =		 	[str() for _ in range(H.NUM_CONTROLS_PER_ROW)]
		self.left_strip_parameters = 	[None for  _ in range(H.NUM_CONTROLS_PER_ROW)]
		self.right_strip_names =		[str() for _ in range(H.NUM_CONTROLS_PER_ROW)]
		self.right_strip_parameters = 	[None for  _ in range(H.NUM_CONTROLS_PER_ROW)]

		self._message_popup_ticks = 0 	# How long to display a popup message for? 

		# looks like an unknown object and 4 lines
		self._last_send_row_id_messages = [None, [], [], [], []] # <-- Refreshed in refresh_state...

		#self.refresh_state()

		log(f"<-----Returning from DisplayComponent.__init__({control_surface},{name})")


	################################################################################################################


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
		self.clear_displays()
		self.show_offline_message()

		super().disconnect()


	################################################################################################################


	def generate_strip_string(self, display_string):
		"""Create a padded display string for a single strip."""

		# Blank returns all spaces basically.
		if not display_string:
			return " " * Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP

		display_string = display_string.strip()

		# Special rules for something ending with dB then it takes away the dB.
		if (
			len(display_string) > Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP - 1
			and display_string.endswith("dB")
			and "." in display_string
		):
			log(f"dB stripped from {display_string}")
			display_string = display_string[:-2]

		return display_string[:Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP].ljust(Constants.Hardware.NUM_CHARS_PER_DISPLAY_STRIP)



	################################################################################################################


	@override
	def refresh_state(self):
		"""Reset the cached display state for the rows."""

		log("DisplayComponent.refresh_state() called.")
		self._last_send_row_id_messages = [None, [], [], [], []] # <------ Resets this object.
		log("<-----Returning from DisplayComponent.refresh_state().")


	################################################################################################################


	def send_display_string(self, message, row_id, offset=0):
		"""Send a formatted display string to the hardware."""

		final_message = " " * offset + message # add the offset to the string.

		# Fill to the end of the display line.
		if len(final_message) < Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE:
			fill_up =Constants.Hardware. NUM_CHARS_PER_DISPLAY_LINE - len(final_message)
			final_message = final_message + " " * fill_up

		# Or cut to length.
		elif len(final_message) >= Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE:
			final_message = final_message[0:Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE]

		sysex_pos = (0, row_id) # col: 0, row: row_id
		sysex_text = tuple(as_ascii(final_message))

		full_syx_msg = SYX.BEG_SYX + SYX.CMD.LCD_TEXT + SYX.SUB_CMD.TXT.CURS_ADDR + (sysex_pos) + SYX.SUB_CMD.TXT.TEXT_STRING + sysex_text + SYX.END_MSG

		if self._last_send_row_id_messages[row_id] != full_syx_msg:

			log(f"\t|----->Str to display: {' '.join(f'{x:02X}' for x in full_syx_msg)}")
			self._last_send_row_id_messages[row_id] = full_syx_msg
			self.control_surface.send_midi(full_syx_msg)


	################################################################################################################


	def setup_left_display(self, names, parameters):
		"""Store the names and parameter labels shown on the left display."""

		# log(f"--- DISPLAY CONTROLLER INCOMING ---")
		# log(f"PARAM_NAMES VAL: {str(names)} (Length: {len(names)})")
		# log(f"PARAMETERS VAL: {str(parameters)} (Length: {len(parameters)})")
		# ------------------------------------------------------------------------
		self.left_strip_names = names
		self.left_strip_parameters = parameters


	################################################################################################################

	def setup_right_display(self, names, parameters):
		"""Store the names and parameter labels shown on the right display."""

		self.right_strip_names = names
		self.right_strip_parameters = parameters


	################################################################################################################


	def show_offline_message(self):
		self.write_full_row_string_centred("Ableton is OFFLINE", ROW.TL, ROW.TR)


	################################################################################################################


	def show_timed_message(self, message_text, duration_seconds=2.0):
		"""Public endpoint to cleanly show a fluid, full-row message on a strict hardware hold timer."""

		log(f"DISPLAY ENGINE: Triggering timed message popup -> '{message_text}'")
		
		# Convert seconds to clock frames (update_display runs roughly 5 times a second)
		# 2.0 seconds * 5 = 10 ticks
		self._message_popup_ticks = int(duration_seconds * 5)
		
		# Directly broadcast your raw text string across Row 1 (Top Line Left)
		self.send_display_string(message_text, row_id=1, offset=0)
		# Completely wipe Row 3 (Bottom Line Left) so parameter values don't bleed into it
		self.send_display_string("", row_id=3, offset=0)


	################################################################################################################


	@override
	def update(self):
		"""Refresh the display content for the four display rows natively."""

		super().update()

		# --- THE CENTRAL NOTIFICATION TIMER GATE ---
 
		# -1 is off... 0 is end of timer.
		if (self._message_popup_ticks > -1):
			self._message_popup_ticks -= 1
			
		# The exact frame tick the 2 seconds expire, clear the local row string cache mirror
		# to natively trick the loop below into rebuilding your fresh parameters view!
		if self._message_popup_ticks == 0:
			log("DISPLAY ENGINE: Hold timer expired. Releasing screen back to layout matrix.")
			
			# Target the name-mangled private mirror storage dictionary
			# and fill it with blank strings so the redraw validation check triggers instantly
						
			# not sure what we are doing here....
			for row_key in (1, 2, 3, 4):
				self._last_send_row_id_messages[row_key] = ""
					
		elif self._message_popup_ticks > 0:
			# Keep the screen completely frozen during the active countdown hold
			return None

		# --------------------------------------------

		# rows are top_left, top_right, bottom_left, bottom_right
		for row_id in (1, 2, 3, 4):
			message_string = ""
			if row_id in (1, 2):
				if row_id == 1:
					strip_names = self.left_strip_names
				else:
					strip_names = self.right_strip_names
					
				# --- FIX: SINGLE-LINE TEXT PASS-THROUGH GUARD ---
				# If we receive exactly 1 long fluid text string instead of 8 column blocks
				if len(strip_names) == 1:
					message_string = strip_names[0]
					self.send_display_string(message_string, row_id, offset=0)
					continue
				# ------------------------------------------------
					
				if len(strip_names) == Constants.Hardware.NUM_CONTROLS_PER_ROW:
					for name in strip_names:
						message_string += self.generate_strip_string(name)
				else:
					log("Error: What am i seeing here????")
					message_string = self.generate_strip_string("") * Constants.Hardware.NUM_CONTROLS_PER_ROW
				self.send_display_string(message_string, row_id, offset=0)
				continue

			if row_id == 3:
				parameters = self.left_strip_parameters
			else:
				parameters = self.right_strip_parameters

			for parameter in parameters:
				if parameter:
					message_string += self.generate_strip_string(str(parameter))
				else:
					message_string += self.generate_strip_string("")

			self.send_display_string(message_string, row_id, offset=0)


	################################################################################################################


	def write_full_row_string(self, text: str, *rows: ROW):
		"""Public endpoint to print a continuous, perfectly spaced phrase across a full row."""

		log(f"DisplayComponent.write_full_row_string({text}, {rows}) called.")

		if rows.count == 0:
			rows = (ROW.TL,)

		# Safely pass the text string down to the internal private Sysex compiler
		for row in rows:
			self.send_display_string(text, row.value, offset=0)


	################################################################################################################


	def write_full_row_string_centred(self, text: str, *rows: ROW):

		log(f"DisplayComponent.write_full_row_string_centred({text}, {rows}) called.")

		if rows.count == 0:
			rows = (ROW.TL,)

		centred = text.center(Constants.Hardware.NUM_CHARS_PER_DISPLAY_LINE)

		self.write_full_row_string(centred, *rows)


	################################################################################################################



####################################################################################################################
####################################################################################################################

