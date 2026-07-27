# tracker.py
import functools

CALL_COUNTS = {}
ALL_METHODS = set()

def count_calls(func):
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		key = func.__qualname__
		CALL_COUNTS[key] = CALL_COUNTS.get(key, 0) + 1
		return func(*args, **kwargs)
	return wrapper

class TrackedMixin:
	"""Mixin that automatically wraps all methods of any subclass."""

	def __init_subclass__(cls, **kwargs):

		super().__init_subclass__(**kwargs)

		for name, value in list(cls.__dict__.items()):
			
			if callable(value):
				wrapped = count_calls(value)
				setattr(cls, name, wrapped)
				ALL_METHODS.add(f"{cls.__name__}.{name}")
