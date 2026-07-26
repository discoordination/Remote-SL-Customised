import os
from datetime import datetime
import inspect


from .consts import Constants


# myLogger.py
import os
from datetime import datetime
import inspect
from enum import Enum
from typing import Optional

from .consts import Constants  # if LOGGING_ENABLED is in consts

# --- Configuration ---
LOG_FILE_PATH = r"C:\\Users\\willw\\Desktop\\script_debug.txt"
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR

# --- Configuration ---
LOG_FILE_PATH = r"C:\\Users\\willw\\Desktop\\script_debug.txt"
LOG_LEVEL = "DEBUG"           # DEBUG, INFO, WARNING, ERROR
LOG_ENABLED = True
LOG_MIDI = True               # ← Toggle MIDI message logging
LOG_ASSIGNMENTS = True        # ← Toggle control assignment logging


# --- Log Levels ---
class LogLevel(Enum):
	DEBUG = 0
	INFO = 1
	WARNING = 2
	ERROR = 3

_level_map = {
	"DEBUG": LogLevel.DEBUG,
	"INFO": LogLevel.INFO,
	"WARNING": LogLevel.WARNING,
	"ERROR": LogLevel.ERROR,
}


_current_level = getattr(LogLevel, LOG_LEVEL, LogLevel.DEBUG)


# --- Core Logger ---
class Logger:
	_instance = None


	
	def __new__(cls):
		if cls._instance is None:
			cls._instance = super().__new__(cls)
			cls._instance._initialized = False
		return cls._instance


	
	def __init__(self):
		if self._initialized:
			return
		self._initialized = True
		self._component = None
		self._log_file = LOG_FILE_PATH
		self.clear()



	def clear(self):
		"""Clear the log file on session start."""
		try:
			with open(self._log_file, 'w') as f:
				f.write(f"=== Remote SL Session {datetime.now().isoformat()} ===\n")
		except Exception:
			pass



	def set_component(self, name: str):
		"""Set the current component name for context."""
		self._component = name



	def log(self, message: str, level: LogLevel = LogLevel.DEBUG, component: Optional[str] = None):
		"""Write a log message with level and context."""

		if not LOG_ENABLED or level.value < _current_level.value:
			return

		current_frame = inspect.currentframe()
		
		# Get caller info – go back TWO frames (skip the log() wrapper)

		while current_frame:
			filename = current_frame.f_code.co_filename
			if "myLogger.py" not in filename:
				break
			current_frame = current_frame.f_back
    

		if current_frame:
			filename = os.path.basename(current_frame.f_code.co_filename)
			func = current_frame.f_code.co_name
			line = current_frame.f_lineno
		else:
			filename = func = line = "?"
			line = 0
	
		timestamp = datetime.now().isoformat(timespec='milliseconds')
		comp = component or self._component or "Unknown"
		level_name = level.name
			
		try:
			with open(self._log_file, 'a') as f:
				f.write(f"[{timestamp}] [{level_name}] {comp}.{func}():{line} - {message}\n")
		except Exception:
			pass



	def log_midi(self, direction: str, midi_bytes: tuple, component: Optional[str] = None):
		"""Log MIDI messages with direction (IN/OUT)."""
		if not LOG_MIDI:
			return
		hex_str = ' '.join(f'{b:02X}' for b in midi_bytes)
		self.log(f"MIDI {direction}: {hex_str}", LogLevel.DEBUG, component)



	def log_assignment(self, strip_index: int, cc_no: int, param_name: str, component: Optional[str] = None):
		"""Log control assignments."""
		if not LOG_ASSIGNMENTS:
			return
		self.log(f"ASSIGN: Strip {strip_index} → CC {cc_no} → {param_name}", LogLevel.DEBUG, component)


# --- Convenience Functions ---
_logger = Logger()





def log(message: str, component: Optional[str] = None):
	"""Log at DEBUG level (default)."""
	_logger.log(message, LogLevel.DEBUG, component)





def log_info(message: str, component: Optional[str] = None):
	_logger.log(message, LogLevel.INFO, component)





def log_warning(message: str, component: Optional[str] = None):
	_logger.log(message, LogLevel.WARNING, component)





def log_error(message: str, component: Optional[str] = None):
	_logger.log(message, LogLevel.ERROR, component)




def log_midi(direction: str, midi_bytes: tuple, component: Optional[str] = None):
    _logger.log_midi(direction, midi_bytes, component)




def log_assignment(strip_index: int, cc_no: int, param_name: str, component: Optional[str] = None):
    _logger.log_assignment(strip_index, cc_no, param_name, component)



def set_log_component(name: str):
	_logger.set_component(name)






# --- Utility Functions (keep as-is) ---
def dump_attributes(object, fp):
	fp.write("Attributes:\n\n")
	for attr in dir(object):
		if not attr.startswith('_') and not callable(getattr(object, attr)):
			fp.write(f"Property: {type(object).__name__}.{attr}.\n")
	fp.write("\n")






def dump_methods(object, fp):
	fp.write("Methods:\n\n")
	for method in dir(object):
		if not method.startswith('_') and callable(getattr(object, method)):
			fp.write(f"Method: {type(object).__name__}.{method}().\n")
	fp.write("\n")






def dump_object_info(object, filepath=None):
	if filepath is None:
		filepath = os.path.join(os.path.dirname(LOG_FILE_PATH), f"{type(object).__name__}.txt")
	try:
		with open(filepath, 'w') as fp:
			dump_attributes(object, fp)
			dump_methods(object, fp)
	except Exception:
		log_error(f"Failed to dump object info for {type(object).__name__}")






def generate_stub(target_class, output_filename="output.pyi"):
	import inspect
	desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
	file_path = os.path.join(desktop_path, output_filename)
	with open(file_path, "w", encoding="utf-8") as f:
		class_name = target_class.__name__
		f.write(f"class {class_name}:\n")
		if target_class.__doc__:
			f.write(f'    """{target_class.__doc__.strip()}"""\n\n')
		for attr_name in sorted(dir(target_class)):
			if attr_name.startswith("__") and attr_name != "__init__":
				continue
			attr_value = getattr(target_class, attr_name)
			if inspect.isroutine(attr_value):
				try:
					signature = str(inspect.signature(attr_value))
				except (ValueError, TypeError):
					signature = "(*args, **kwargs)"
				f.write(f"    def {attr_name}{signature} -> Any:\n")
				if attr_value.__doc__:
					doc = attr_value.__doc__.strip()
					indented_doc = "\n".join(f"        {line}" for line in doc.splitlines())
					f.write(f'        """\n{indented_doc}\n        """\n')
				f.write("        ...\n\n")
			else:
				f.write(f"    {attr_name}: Any\n")
	return file_path





# # Set a completely independent, hardcoded file destination path
# # For Windows: Use a path like r"C:\Users\YourName\Desktop\script_debug.txt"
# # For Mac: Use a path like "/Users/YourName/Desktop/script_debug.txt"
# LOG_FILE_PATH = r"C:\\Users\\willw\\Desktop\\script_debug.txt"
# MID_LOG_PATH = r"C:\\Users\\willw\\Desktop\\midi_debug.txt"
# DUMPED_ATTRIBUTES_PATH = r"C:\\Users\willw\Desktop\\"



# def clear_log():
# 	"""Wipes the file clean on initial boot."""
# 	try:
# 		# Open in 'w' mode to completely overwrite/truncate the file to 0 bytes
# 		with open(LOG_FILE_PATH, "w") as f:
# 			f.write("=== NEW ABLETON SESSION LOADED ===\n")
# 	except Exception:
# 		pass


# if Constants.Logging.ENABLED:
# 	def log(message):
# 		"""Force appends a string directly into your custom desktop file."""
# 		try:
# 			timestamp = datetime.now().isoformat(timespec="seconds")
# 			# Open in append mode ('a') so it acts as a real-time stream log
# 			with open(LOG_FILE_PATH, "a") as f:
# 				f.write(f"[{timestamp}] - {message}\n")
# 		except Exception as e:
# 			# Fallback safeguard in case there is a folder permission error
# 			pass
# else:
# 	def log(message):
# 		pass
	


# def dump_attributes(object, fp):

# 	fp.write("Attributes:\n\n")

# 	for attribute in dir(object):
# 		if not attribute.startswith('_') and not callable(getattr(object, attribute)):
# 			fp.write(f"Property: {type(object).__name__}.{attribute}.\n")

# 	fp.write("\n")


# def dump_methods(object, fp):
# 	# 2. Print all executable functions and methods (actions)

# 	fp.write("Methods:\n\n")

# 	for method in dir(object):
# 		if not method.startswith('_') and callable(getattr(object, method)):
# 			fp.write(f"Method: {type(object).__name__}.{method}().\n")

# 	fp.write("\n")


# def dump_object_info(object):
	
# 	try:
# 		with open(f"{DUMPED_ATTRIBUTES_PATH}{type(object).__name__}.txt", "w") as fp:
# 			dump_attributes(object, fp)
# 			dump_methods(object, fp)
# 	except:
# 		log("File Error while dumping attributes...")





# def generate_stub(target_class, output_filename="output.pyi"):
#     """
#     Dynamically inspects an Ableton class at runtime and writes a 
#     fully typed .pyi stub file with docstrings and method signatures.
#     """
#     # Choose a safe output path (e.g., your Desktop or project folder)
#     desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
#     file_path = os.path.join(desktop_path, output_filename)
	
#     with open(file_path, "w", encoding="utf-8") as f:
#         # Write Class Header
#         class_name = target_class.__name__
#         f.write(f"class {class_name}:\n")
		
#         # Write Class Docstring if it exists
#         if target_class.__doc__:
#             f.write(f'    """{target_class.__doc__.strip()}"""\n\n')
			
#         # Inspect all attributes and methods
#         for attr_name in sorted(dir(target_class)):
#             # Skip standard hidden dunder methods except __init__
#             if attr_name.startswith("__") and attr_name != "__init__":
#                 continue
				
#             attr_value = getattr(target_class, attr_name)
			
#             # Check if it is a method/function
#             if inspect.isroutine(attr_value):
#                 try:
#                     # Capture the exact argument layout (self, c_instance, etc.)
#                     signature = str(inspect.signature(attr_value))
#                 except (ValueError, TypeError):
#                     # Fallback for compiled C++ bindings where signatures are hidden
#                     signature = "(*args, **kwargs)"
				
#                 f.write(f"    def {attr_name}{signature} -> Any:\n")
				
#                 # Append the method's docstring inside the stub
#                 if attr_value.__doc__:
#                     doc = attr_value.__doc__.strip()
#                     # Indent the docstring correctly
#                     indented_doc = "\n".join(f"        {line}" for line in doc.splitlines())
#                     f.write(f'        """\n{indented_doc}\n        """\n')
				
#                 f.write("        ...\n\n")
#             else:
#                 # It's a property or class variable
#                 f.write(f"    {attr_name}: Any\n")
				
#     return file_path





# # Safe execution check wrapper
# try:
# 	clear_log()
# except Exception:
# 	pass
