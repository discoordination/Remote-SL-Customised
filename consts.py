####################################################################################################################
# consts.py
####################################################################################################################


#from dataclasses import dataclass
from typing import List, Tuple, Final
from enum import Enum, IntEnum

from ableton.v3.base import as_ascii


####################################################################################################################


# Type aliases for better type hints
CCList = List[int]
CCRange = List[int]
SysexMessage = Tuple[int, ...]


####################################################################################################################


# === Helper Functions ===
def _range(start: int, count: int = 8) -> CCList:
	"""Create a list of CC numbers starting at 'start'."""
	return list(range(start, start + count))


####################################################################################################################


# === Main Constants Container ===
class Constants:
	"""Container for all Remote SL Classic constants."""

	################################################################################################################

	class Logging:
		ENABLED : Final[bool] = True


	################################################################################################################

	
	# === Hardware Constants ===
	class Hardware:
		"""Basic hardware configuration."""

		NUM_CONTROLS_PER_ROW: Final[int] = 8
		NUM_CHARS_PER_DISPLAY_STRIP: Final[int] = 9
		NUM_CHARS_PER_DISPLAY_LINE: Final[int] = NUM_CHARS_PER_DISPLAY_STRIP * NUM_CONTROLS_PER_ROW
		NUM_CHANNELS: Final[int] = 15
		MIDI_CHANNEL: Final[int] = 0
		BUTTON_PRESSED: Final[int] = 1
		BUTTON_RELEASED: Final[int] = 0
		ABLETON_PID: Final[int] = 4
	

	################################################################################################################


	# === MIDI Status Bytes ===
	class MIDI:
		"""MIDI status byte constants."""

		NOTE_OFF: Final[int] = 128
		NOTE_ON: Final[int] = 144
		STATUS: Final[int] = 176
		SYSEX: Final[int] = 240
	

	################################################################################################################


	# === Transport Controls ===
	class Transport:
		"""Transport control CC numbers."""

		# Individual CCs
		REWIND: Final[int] = 72
		FORWARD: Final[int] = 73
		STOP: Final[int] = 74
		PLAY: Final[int] = 75
		RECORD: Final[int] = 76
		LOOP: Final[int] = 77
		LOCK: Final[int] = 79
		
		# Group all transport CCs
		ALL:Final[CCList] = [REWIND, FORWARD, STOP, PLAY, RECORD, LOOP, LOCK]
		
		# Map CC to action name (useful for debugging)
		NAMES: Final[dict[int, str]] = {
			REWIND: "Rewind",
			FORWARD: "Forward", 
			STOP: "Stop",
			PLAY: "Play",
			RECORD: "Record",
			LOOP: "Loop",
			LOCK: "Lock"
		}
	

	################################################################################################################	


	# === Mixer Controls ===
	class Mixer:
		"""Mixer section CC numbers."""

		# Individual CCs
		SLIDER_BASE: Final[int] = 16
		BUTTONS_TOP_BASE: Final[int] = 40
		BUTTON_BOTTOM_BASE: Final[int] = 48
		PAGE_UP: Final[int] = 90
		PAGE_DOWN: Final[int] = 91
		SELECT_SLIDERS: Final[int] = 85
		SELECT_BUTTONS_TOP: Final[int] = 86
		SELECT_BUTTONS_BOTTOM: Final[int] = 87
		
		# Derived groups
		SLIDERS: Final[CCList] = _range(SLIDER_BASE)  # [16-23]
		BUTTONS_TOP_ROW: Final[CCList] = _range(BUTTONS_TOP_BASE)  # [40-47]
		BUTTONS_BOTTOM_ROW: Final[CCList] = _range(BUTTON_BOTTOM_BASE)  # [48-55]
		
		# Navigation buttons
		NAVIGATION: Final[CCList] = [PAGE_UP, PAGE_DOWN]
		SELECT_BUTTONS: Final[CCList] = [SELECT_SLIDERS, SELECT_BUTTONS_TOP, SELECT_BUTTONS_BOTTOM]
		#FORWARDED_CCS = [] #NAVIGATION + SELECT_BUTTONS + BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW
		#FORWARDED_NOTES = []
		
		# All mixer CCs
		ALL: Final[CCList] = SLIDERS + BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW + NAVIGATION + SELECT_BUTTONS
		
		# Buttons that need LED feedback
		LED_BUTTONS: Final[CCList] = BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW + SELECT_BUTTONS
	

	################################################################################################################


	# === Effect Controls ===
	class Effect:
		"""Effect section CC numbers."""

		# Individual CCs
		UPPER_BUTTON_BASE: Final[int] = 24
		ENCODER_BASE: Final[int] = 56
		LOWER_BUTTON_BASE: Final[int] = 32
		
		POTS_BASE: Final[int] = 8
		PAGE_UP: Final[int] = 88
		PAGE_DOWN: Final[int] = 89
		
		# Selector buttons
		SELECT_TOP_BUTTON_ROW: Final[int] = 80
		SELECT_ENCODER: Final[int] = 81
		SELECT_BOTTOM_BUTTON_ROW: Final[int] = 82
		SELECT_POTS: Final[int] = 83
		SELECT_DRUM_PAD: Final[int] = 84
		
		# Grouped controls
		UPPER_BUTTONS: Final[CCList] = _range(UPPER_BUTTON_BASE)  # [24-31]
		ENCODERS: Final[CCList] = _range(ENCODER_BASE)  # [56-63]
		LOWER_BUTTONS: Final[CCList] = _range(LOWER_BUTTON_BASE)  # [32-39]
		POTS: Final[CCList] = _range(POTS_BASE)  # [8-15]
		NAVIGATION: Final[CCList] = [PAGE_UP, PAGE_DOWN]
		SELECT_BUTTONS: Final[CCList] = [SELECT_TOP_BUTTON_ROW, SELECT_ENCODER, SELECT_BOTTOM_BUTTON_ROW, SELECT_POTS, SELECT_DRUM_PAD]
		
		# All effect CCs
		ALL: Final[CCList] = POTS + UPPER_BUTTONS + LOWER_BUTTONS + ENCODERS + NAVIGATION + SELECT_BUTTONS
		
		# Which rows are forwardable (no LED feedback needed)
		FORWARDABLE: Final[CCList] = NAVIGATION + SELECT_BUTTONS + UPPER_BUTTONS
		
		# Drum pads (notes, not CCs)
		DRUM_PAD_BASE_NOTE: Final[int] = 36
		DRUM_PADS: Final[CCList] = _range(DRUM_PAD_BASE_NOTE)
		
		# # Encoder feedback (MKII)
		# ENCODER_FEEDBACK_BASE = 112
		# ENCODER_FEEDBACK = _range(ENCODER_FEEDBACK_BASE)
		
		# ENCODER_LED_MODE_BASE = 120
		# ENCODER_LED_MODES = _range(ENCODER_LED_MODE_BASE)
	

	################################################################################################################


	# === System Exclusive Messages ===
	class SysEx:
		"""System exclusive messages."""
		
		WELCOME: Final[SysexMessage] = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 1, 1, 247)
		GOODBYE: Final[SysexMessage] = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 1, 0, 247)
		ALL_LEDS_OFF: Final[SysexMessage] = (176, 78, 0)
		

		############################################################################################################


		# Display clear messages
		@staticmethod
		def clear_display(side: str = "left") -> SysexMessage:
			"""Get display clear sysex for left or right display."""

			base: SysexMessage = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 2, 2)

			if side == "left":
				return base + (4, 247)
			else:
				return base + (5, 247)
		

		############################################################################################################


		@staticmethod
		def display_text(text: str, row: int = 1) -> SysexMessage:
			"""Create sysex for display text."""
			
			header: SysexMessage = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 2, 1, 0, row, 4)
			text_bytes = tuple(as_ascii(text.ljust(72)[:72]))

			return header + text_bytes + (247,)

	
		############################################################################################################
	
	################################################################################################################


	# === Pad Translation ===
	PAD_TRANSLATION: Tuple[Tuple[int, ...], ...] = (
		(0, 2, 36, 0),
		(1, 2, 37, 0),
		(2, 2, 38, 0),
		(3, 2, 39, 0),
		(0, 3, 40, 0),
		(1, 3, 41, 0),
		(2, 3, 42, 0),
		(3, 3, 43, 0),
	)
	

	################################################################################################################


	# === Control Types ===
	class ControlType(Enum):
		"""Control type constants."""

		POT = "pot"
		ENCODER = "encoder"
		BUTTON = "button"
		SLIDER = "slider"
		DRUM_PAD = "drum_pad"
	

	################################################################################################################


	# === Slider Modes ===
	class SliderMode(IntEnum):
		"""Mixer slider modes."""

		VOLUME = 0
		PAN = 1
		SEND = 2

	
	################################################################################################################


	# === Display Rows ===
	class DisplayRow(Enum):
		"""Display row identifiers."""

		TOP_LEFT = 1
		TOP_RIGHT = 2
		BOTTOM_LEFT = 3
		BOTTOM_RIGHT = 4


####################################################################################################################


# === Convenience Aliases ===
# These make the code more readable while maintaining clear namespacing

H = Constants.Hardware
M = Constants.MIDI
T = Constants.Transport
MXR = Constants.Mixer
FX = Constants.Effect
SYX = Constants.SysEx
CTRL = Constants.ControlType
SLM = Constants.SliderMode
ROW = Constants.DisplayRow



####################################################################################################################


# === Exports ===

__all__ = [
	'Constants',
	'H', 'M', 'T', 'MXR', 'FX', 'SYX', 'CTRL', 'SLM', 'ROW',
	'CCList', 'CCRange', 'SysexMessage'
]


####################################################################################################################
####################################################################################################################

