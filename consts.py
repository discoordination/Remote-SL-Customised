# consts.py

from dataclasses import dataclass
from typing import List, Tuple


# Type aliases for better type hints
CCList = List[int]
CCRange = List[int]
SysexMessage = Tuple[int, ...]


# === Helper Functions ===
def _range(start: int, count: int = 8) -> List[int]:
    """Create a list of CC numbers starting at 'start'."""
    return list(range(start, start + count))


# === Main Constants Container ===
class Constants:
    """Container for all Remote SL Classic constants."""


    class Logging:
        ENABLED : bool = True

    
    # === Hardware Constants ===
    class Hardware:
        """Basic hardware configuration."""
        NUM_CONTROLS_PER_ROW: int = 8
        NUM_CHARS_PER_DISPLAY_STRIP:int = 9
        NUM_CHARS_PER_DISPLAY_LINE:int = NUM_CHARS_PER_DISPLAY_STRIP * NUM_CONTROLS_PER_ROW
        NUM_CHANNELS:int = 15
        MIDI_CHANNEL:int = 0
        BUTTON_PRESSED:int = 1
        BUTTON_RELEASED:int = 0
        ABLETON_PID:int = 4
    



    # === MIDI Status Bytes ===
    class MIDI:
        """MIDI status byte constants."""
        NOTE_OFF:int = 128
        NOTE_ON:int = 144
        STATUS:int = 176
        SYSEX:int = 240
    



    # === Transport Controls ===
    class Transport:
        """Transport control CC numbers."""
        # Individual CCs
        REWIND:int = 72
        FORWARD:int = 73
        STOP:int = 74
        PLAY:int = 75
        RECORD:int = 76
        LOOP:int = 77
        LOCK:int = 79
        
        # Group all transport CCs
        ALL:CCList = [REWIND, FORWARD, STOP, PLAY, RECORD, LOOP, LOCK]
        
        # Map CC to action name (useful for debugging)
        NAMES = {
            REWIND: "Rewind",
            FORWARD: "Forward", 
            STOP: "Stop",
            PLAY: "Play",
            RECORD: "Record",
            LOOP: "Loop",
            LOCK: "Lock"
        }
    
    


    # === Mixer Controls ===
    class Mixer:
        """Mixer section CC numbers."""
        # Individual CCs
        SLIDER_BASE = 16
        BUTTONS_TOP_BASE = 40
        BUTTON_BOTTOM_BASE = 48
        PAGE_UP = 90
        PAGE_DOWN = 91
        SELECT_SLIDERS = 85
        SELECT_BUTTONS_TOP = 86
        SELECT_BUTTONS_BOTTOM = 87
        
        # Derived groups
        SLIDERS = _range(SLIDER_BASE)  # [16-23]
        BUTTONS_TOP_ROW = _range(BUTTONS_TOP_BASE)  # [40-47]
        BUTTONS_BOTTOM_ROW = _range(BUTTON_BOTTOM_BASE)  # [48-55]
        
        # Navigation buttons
        NAVIGATION = [PAGE_UP, PAGE_DOWN]
        SELECT_BUTTONS = [SELECT_SLIDERS, SELECT_BUTTONS_TOP, SELECT_BUTTONS_BOTTOM]
        FORWARDED_CCS = [] #NAVIGATION + SELECT_BUTTONS + BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW
        FORWARDED_NOTES = []
        
        # All mixer CCs
        ALL = SLIDERS + BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW + NAVIGATION + SELECT_BUTTONS
        
        # Buttons that need LED feedback
        LED_BUTTONS = BUTTONS_TOP_ROW + BUTTONS_BOTTOM_ROW + SELECT_BUTTONS
    



    # === Effect Controls ===
    class Effect:
        """Effect section CC numbers."""

        # Individual CCs
        UPPER_BUTTON_BASE = 24
        ENCODER_BASE = 56
        LOWER_BUTTON_BASE = 32
        
        POTI_BASE = 8
        PAGE_UP = 88
        PAGE_DOWN = 89
        
        # Selector buttons
        SELECT_TOP_BUTTON_ROW = 80
        SELECT_ENCODER = 81
        SELECT_BOTTOM_BUTTON_ROW = 82
        SELECT_POTS = 83
        SELECT_DRUM_PAD = 84
        
        # Grouped controls
        UPPER_BUTTONS = _range(UPPER_BUTTON_BASE)  # [24-31]
        ENCODERS = _range(ENCODER_BASE)  # [56-63]
        LOWER_BUTTONS = _range(LOWER_BUTTON_BASE)  # [32-39]
        POTS = _range(POTI_BASE)  # [8-15]
        NAVIGATION = [PAGE_UP, PAGE_DOWN]
        SELECT_BUTTONS = [SELECT_TOP_BUTTON_ROW, SELECT_ENCODER, SELECT_BOTTOM_BUTTON_ROW, SELECT_POTS, SELECT_DRUM_PAD]
        
        # All effect CCs
        ALL = POTS + UPPER_BUTTONS + LOWER_BUTTONS + ENCODERS + NAVIGATION + SELECT_BUTTONS
        
        # Which rows are forwardable (no LED feedback needed)
        FORWARDABLE = NAVIGATION + SELECT_BUTTONS + UPPER_BUTTONS
        
        # Drum pads (notes, not CCs)
        DRUM_PAD_BASE_NOTE = 36
        DRUM_PADS = _range(DRUM_PAD_BASE_NOTE)
        
        # Encoder feedback (MKII)
        ENCODER_FEEDBACK_BASE = 112
        ENCODER_FEEDBACK = _range(ENCODER_FEEDBACK_BASE)
        
        ENCODER_LED_MODE_BASE = 120
        ENCODER_LED_MODES = _range(ENCODER_LED_MODE_BASE)
    


    # === System Exclusive Messages ===
    class SysEx:
        """System exclusive messages."""
        WELCOME = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 1, 1, 247)
        GOODBYE = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 1, 0, 247)
        ALL_LEDS_OFF = (176, 78, 0)
        


        # Display clear messages
        @staticmethod
        def clear_display(side: str = "left") -> tuple:
            """Get display clear sysex for left or right display."""
            base = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 2, 2)
            if side == "left":
                return base + (4, 247)
            else:
                return base + (5, 247)
        


        @staticmethod
        def display_text(text: str, row: int = 1) -> tuple:
            """Create sysex for display text."""
            from ableton.v3.base import as_ascii
            
            header = (240, 0, 32, 41, 3, 3, 18, 0, 4, 0, 2, 1, 0, row, 4)
            text_bytes = tuple(as_ascii(text.ljust(72)[:72]))
            return header + text_bytes + (247,)
    


    # === Pad Translation ===
    PAD_TRANSLATION = (
        (0, 2, 36, 0),
        (1, 2, 37, 0),
        (2, 2, 38, 0),
        (3, 2, 39, 0),
        (0, 3, 40, 0),
        (1, 3, 41, 0),
        (2, 3, 42, 0),
        (3, 3, 43, 0),
    )
    


    # === Control Types ===
    class ControlType:
        """Control type constants."""
        POT = "pot"
        ENCODER = "encoder"
        BUTTON = "button"
        SLIDER = "slider"
        DRUM_PAD = "drum_pad"
    



    # === Slider Modes ===
    class SliderMode:
        """Mixer slider modes."""
        VOLUME = 0
        PAN = 1
        SEND = 2
    


    # === Display Rows ===
    class DisplayRow:
        """Display row identifiers."""
        TOP_LEFT = 1
        TOP_RIGHT = 2
        BOTTOM_LEFT = 3
        BOTTOM_RIGHT = 4




# === Convenience Aliases ===
# These make the code more readable while maintaining clear namespacing
H = Constants.Hardware
M = Constants.MIDI
T = Constants.Transport
# MXR = Constants.Mixer
# FX = Constants.Effect
# SYX = Constants.SysEx
# CTRL = Constants.ControlType
# SL = Constants.SliderMode
# ROW = Constants.DisplayRow



# === Exports ===
__all__ = [
    'Constants',
 #   'H', 'M', 'T', 'MXR', 'FX', 'SYX', 'CTRL', 'SL', 'ROW',
    'CCList', 'CCRange', 'SysexMessage'
]
