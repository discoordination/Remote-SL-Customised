####################################################################################################################
# Source Generated with Decompyle++
# File: DisplayController.pyc (Python 3.11)
####################################################################################################################

"""Controller logic for the Remote SL display strips."""

from ableton.v3.base import as_ascii

import sys
# Ableton 12 runs 3.11, so it falls back to the dummy decorator silently.
# VS Code (configured to 3.12+) will still parse it perfectly for static analysis.
if sys.version_info >= (3, 12):
    from typing import override
else:
    def override(func):
        return func

from .consts import *
from .RemoteSLComponent import RemoteSLComponent
from .myLogger import log


####################################################################################################################


class DisplayController(RemoteSLComponent):
	"""Handle the two display strips and their associated text updates."""

	################################################################################################################


	def __init__(self, remote_sl_parent):
		
		RemoteSLComponent.__init__(self, remote_sl_parent)

		self._message_popup_ticks = 0
		self.left_strip_names = [str() for _ in range(NUM_CONTROLS_PER_ROW)]
		self.left_strip_parameters = [None for _ in range(NUM_CONTROLS_PER_ROW)]
		self.right_strip_names = [str() for _ in range(NUM_CONTROLS_PER_ROW)]
		self.right_strip_parameters = [None for _ in range(NUM_CONTROLS_PER_ROW)]

		self.refresh_state()


	################################################################################################################


	@override
	def disconnect(self):
		"""Clear the hardware displays when the controller is disconnected."""

		self.send_clear_displays()


	################################################################################################################


	def generate_strip_string(self, display_string):
		"""Create a padded display string for a single strip."""

		if not display_string:
			return " " * NUM_CHARS_PER_DISPLAY_STRIP

		display_string = display_string.strip()
		if (
			len(display_string) > NUM_CHARS_PER_DISPLAY_STRIP - 1
			and display_string.endswith("dB")
			and "." in display_string
		):
			display_string = display_string[:-2]

		return display_string[:NUM_CHARS_PER_DISPLAY_STRIP].ljust(NUM_CHARS_PER_DISPLAY_STRIP)


	################################################################################################################


	@override
	def refresh_state(self):
		"""Reset the cached display state for the rows."""

		log("DisplayController.refresh_state() called.")
		self._last_send_row_id_messages = [None, [], [], [], []]
		log("<-----Returning from DisplayController.refresh_state().")


	################################################################################################################


	def send_clear_displays(self):
		"""Send the sysex command that clears the left and right displays."""
		
		start_clear_sysex = (240, 0, 32, 41, 3, 3, 18, 0)
		
		left_end_sysex = (ABLETON_PID, 0, 2, 2, 4, 247)
		right_end_sysex = (ABLETON_PID, 0, 2, 2, 5, 247)
		
		self.send_midi(start_clear_sysex + left_end_sysex)
		self.send_midi(start_clear_sysex + right_end_sysex)


	################################################################################################################


	def send_display_string(self, message, row_id, offset=0):
		"""Send a formatted display string to the hardware."""
		
		final_message = " " * offset + message

		if len(final_message) < NUM_CHARS_PER_DISPLAY_LINE:
			fill_up = NUM_CHARS_PER_DISPLAY_LINE - len(final_message)
			final_message = final_message + " " * fill_up
		
		elif len(final_message) >= NUM_CHARS_PER_DISPLAY_LINE:
			final_message = final_message[0:NUM_CHARS_PER_DISPLAY_LINE]

		final_offset = 0

		sysex_header = (240, 0, 32, 41, 3, 3, 18, 0, ABLETON_PID, 0, 2, 1)
		sysex_pos = (final_offset, row_id)
		sysex_text_command = (4,)
		sysex_text = tuple(as_ascii(final_message))
		sysex_close_up = (247,)
		full_sysex = sysex_header + sysex_pos + sysex_text_command + sysex_text + sysex_close_up

		if self._last_send_row_id_messages[row_id] != full_sysex:
			self._last_send_row_id_messages[row_id] = full_sysex
			self.send_midi(full_sysex)


	################################################################################################################


	def setup_left_display(self, names, parameters):
		"""Store the names and parameter labels shown on the left display."""

		log(f"--- DISPLAY CONTROLLER INCOMING ---")
		log(f"PARAM_NAMES VAL: {str(names)} (Length: {len(names)})")
		log(f"PARAMETERS VAL: {str(parameters)} (Length: {len(parameters)})")
		# ------------------------------------------------------------------------
		self.left_strip_names = names
		self.left_strip_parameters = parameters


	################################################################################################################

	def setup_right_display(self, names, parameters):
		"""Store the names and parameter labels shown on the right display."""

		self.right_strip_names = names
		self.right_strip_parameters = parameters


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
	def update_display(self):
		"""Refresh the display content for the four display rows natively."""

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
			
			#if hasattr(self, '_last_send_row_id_messages'):
			for row_key in (1, 2, 3, 4):
				self._last_send_row_id_messages[row_key] = ""
					
		elif self._message_popup_ticks > 0:
			# Keep the screen completely frozen during the active countdown hold
			return None

		# --------------------------------------------

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
					
				if len(strip_names) == NUM_CONTROLS_PER_ROW:
					for name in strip_names:
						message_string += self.generate_strip_string(name)
				else:
					message_string = self.generate_strip_string("") * NUM_CONTROLS_PER_ROW
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


	def write_full_row_string(self, text, row_id):
		"""Public endpoint to print a continuous, perfectly spaced phrase across a full row."""

		# Safely pass the text string down to the internal private Sysex compiler
		self.send_display_string(text, row_id, offset=0)



####################################################################################################################
####################################################################################################################

