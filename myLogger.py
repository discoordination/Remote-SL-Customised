import os
from datetime import datetime
import inspect


from .consts import LOGGING_ENABLED

# Set a completely independent, hardcoded file destination path
# For Windows: Use a path like r"C:\Users\YourName\Desktop\script_debug.txt"
# For Mac: Use a path like "/Users/YourName/Desktop/script_debug.txt"
LOG_FILE_PATH = r"C:\\Users\\willw\\Desktop\\script_debug.txt"
DUMPED_ATTRIBUTES_PATH = r"C:\\Users\willw\Desktop\\"



def clear_log():
	"""Wipes the file clean on initial boot."""
	try:
		# Open in 'w' mode to completely overwrite/truncate the file to 0 bytes
		with open(LOG_FILE_PATH, "w") as f:
			f.write("=== NEW ABLETON SESSION LOADED ===\n")
	except Exception:
		pass


if LOGGING_ENABLED:
	def log(message):
		"""Force appends a string directly into your custom desktop file."""
		try:
			timestamp = datetime.now().isoformat(timespec="seconds")
			# Open in append mode ('a') so it acts as a real-time stream log
			with open(LOG_FILE_PATH, "a") as f:
				f.write(f"[{timestamp}] - {message}\n")
		except Exception as e:
			# Fallback safeguard in case there is a folder permission error
			pass
else:
	def log(message):
		pass
	


def dump_attributes(object, fp):

	fp.write("Attributes:\n\n")

	for attribute in dir(object):
		if not attribute.startswith('_') and not callable(getattr(object, attribute)):
			fp.write(f"Property: {type(object).__name__}.{attribute}.\n")

	fp.write("\n")


def dump_methods(object, fp):
	# 2. Print all executable functions and methods (actions)

	fp.write("Methods:\n\n")

	for method in dir(object):
		if not method.startswith('_') and callable(getattr(object, method)):
			fp.write(f"Method: {type(object).__name__}.{method}().\n")

	fp.write("\n")


def dump_object_info(object):
	
	try:
		with open(f"{DUMPED_ATTRIBUTES_PATH}{type(object).__name__}.txt", "w") as fp:
			dump_attributes(object, fp)
			dump_methods(object, fp)
	except:
		log("File Error while dumping attributes...")





def generate_stub(target_class, output_filename="output.pyi"):
    """
    Dynamically inspects an Ableton class at runtime and writes a 
    fully typed .pyi stub file with docstrings and method signatures.
    """
    # Choose a safe output path (e.g., your Desktop or project folder)
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    file_path = os.path.join(desktop_path, output_filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        # Write Class Header
        class_name = target_class.__name__
        f.write(f"class {class_name}:\n")
        
        # Write Class Docstring if it exists
        if target_class.__doc__:
            f.write(f'    """{target_class.__doc__.strip()}"""\n\n')
            
        # Inspect all attributes and methods
        for attr_name in sorted(dir(target_class)):
            # Skip standard hidden dunder methods except __init__
            if attr_name.startswith("__") and attr_name != "__init__":
                continue
                
            attr_value = getattr(target_class, attr_name)
            
            # Check if it is a method/function
            if inspect.isroutine(attr_value):
                try:
                    # Capture the exact argument layout (self, c_instance, etc.)
                    signature = str(inspect.signature(attr_value))
                except (ValueError, TypeError):
                    # Fallback for compiled C++ bindings where signatures are hidden
                    signature = "(*args, **kwargs)"
                
                f.write(f"    def {attr_name}{signature} -> Any:\n")
                
                # Append the method's docstring inside the stub
                if attr_value.__doc__:
                    doc = attr_value.__doc__.strip()
                    # Indent the docstring correctly
                    indented_doc = "\n".join(f"        {line}" for line in doc.splitlines())
                    f.write(f'        """\n{indented_doc}\n        """\n')
                
                f.write("        ...\n\n")
            else:
                # It's a property or class variable
                f.write(f"    {attr_name}: Any\n")
                
    return file_path





# Safe execution check wrapper
try:
	clear_log()
except Exception:
	pass
