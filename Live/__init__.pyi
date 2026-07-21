# Live.pyi - Local Linter Stub definition for Live 12
from typing import Any
from .Song import Song as Song

class Application:
    @staticmethod
    def get_application() -> Application: ...

class DeviceParameter:
    
    @property
    def default_value(self) -> float: ...

    @property
    def is_quantized(self) -> bool: ...

    @property
    def is_enabled(self) -> bool: ...
    
    @property
    def max(self) -> float: ...
    
    @property
    def min(self) -> float: ...

    @property
    def name(self) -> str: ...

    @property
    def value(self) -> float: ...

    @value.setter
    def value(self, value: float) -> None: ...


class MidiMap:
    
    class MapMode:
        absolute: Any
        relative_smooth_signed_bit: Any

    @staticmethod
    def map_midi_cc(midi_map_handle: Any, parameter: Any, channel: int, cc_no: int, map_mode: Any, needs_takeover: bool) -> None: ...
   
    @staticmethod
    def map_midi_cc_with_feedback_map(midi_map_handle: Any, parameter: Any, channel: int, cc_no: int, map_mode: Any, feedback_rule: Any, needs_takeover: bool) -> None: ...
   
    @staticmethod
    def forward_midi_cc(script_handle: Any, midi_map_handle: Any, channel: int, cc_no: int) -> None: ...
    
    @staticmethod
    def forward_midi_note(script_handle: Any, midi_map_handle: Any, channel: int, note_no: int) -> None: ...
    
    @staticmethod
    def send_feedback_for_parameter(midi_map_handle: Any, parameter: Any) -> None: ...
    
    class CCFeedbackRule:
        cc_no: int
        channel: int
        delay_in_ms: int
        cc_value_map: tuple
