####################################################################################################################
## Copyright (C) 2026 William Werkmeister
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
####################################################################################################################
####################################################################################################################
# 
# __init__.pyc 

"""Entry point for the Remote SL Classic 61 controller script.

This module registers the controller with Ableton Live and exposes the
capabilities that the Live framework expects from a Remote Script.
"""



from ableton.v3.control_surface.capabilities import *

from .RemoteSL import RemoteSL
from .myLogger import *


# okay so this morning...  Add transport controls...  Continue checking order of moving through functions...


# c_instance known methods.
# handle()  -                returns the script's low level handle.
# log(str)  -                writes a string to live's log.
# show_message(str) -        writes a message to Live's status bar.
# send_midi(tuple)  -        sends a raw midi tuple (ch, cc, val) to the control surface.
# request_rebuild_midi_map - Requests that rebuild_midi_map be called.
# set_pad_translation() -
# instance_identifier -   
# song() -
# toggle_lock() -



def create_instance(c_instance):
	"""Create and return the Remote SL controller instance."""

	log_info("*-> Creating instance...")
	instance = RemoteSL(c_instance)
	instance.show_message("RemoteSL_Customised created...")

	return instance



def get_capabilities():
	"""Return the modern controller ports and identification information for Live 12."""
	
	log_info("*-> Getting capabilities...")
	
	# Use the clean, standardized string constants expected by Live 12
	return {
		"ports": [
			# Port 1 (Generic MIDI)
			inport(props=[NOTES_CC, REMOTE]),

			# Port 2 (Automap / Script data engine)
			inport(props=[NOTES_CC, REMOTE, SCRIPT]), #NOTES_CC, REMOTE, SCRIPT]),

			# Port 3 (Keyboard/Synth hardware layer)
			inport(props=[NOTES_CC]),
			
			# Outputs
			outport(props=[NOTES_CC, SYNC]),
			outport(props=[SCRIPT]),
			outport(props=[]),
		],

		"controller_id": controller_id(
			vendor_id=4661,
			product_ids=[3],
			model_name="ReMOTE ZeRO SL",
		),
	}

