#!/usr/bin/python

import shelve
import os.path
import time

class RCSwitch:
	def __init__(self, mcu_callback, aq):

		self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_switches"), writeback=True)

		if not self.db.has_key('switches'):
			print('Creating new switches db')
			self.db['switches'] = []


		#self.db['switches'] = []
		#self.db['switches'].append(dict(state=0, on="000100010000010101010001", off="000100010000010101010100", name = "Raid"))
		#self.db['switches'].append(dict(state=0, on="000100010001000101010001", off="000100010001000101010100", name = "Nothing"))
		#self.db['switches'].append(dict(state=0, on="000100010001010001010001", off="000100010001010001010100", name = "TV"))
		#self.db['switches'].append(dict(state=0, on="000100010001010100010001", off="000100010001010100010100", name = "Speakers"))
		#self.db_flush()

		self.mcu_callback = mcu_callback
		self.aq = aq

	def db_flush(self):
		self.db.sync()
		self.db.close()
		self.db = shelve.open(os.path.join(os.path.dirname(__file__), "db/db_switches"), writeback=True)

	def update_db(self, new_switches):
		self.db['switches'] = new_switches
		self.db_flush()

	def append_db(self, new_switch):
		self.db['switches'].append(new_switch)
		self.db_flush()

	def get_switches(self):
		return self.db['switches']

	def get_switches_len(self):
		return len(self.db['switches'])

	def get_state_by_id(self, id):
		switch = self.get_switch_by_id(id)
		if switch:
			return int(switch['state'])
		return None

	def get_switch_by_id(self, id):
		return self.db['switches'][id]

	def get_switch_id_by_cmd(self, cmd):
		found = False
		for id in range(len(self.db['switches'])):
			switch = self.db['switches'][id]
			if cmd in [switch['on'], switch['off']]:
				found = True
				break
		if found:
			return id
		return None

	def get_switch_id_by_name(self, name):
		found = False
		for id in range(len(self.db['switches'])):
			switch = self.db['switches'][id]
			if name == switch['name']:
				found = True
				break
		if found:
			return id
		return None

	def set_switch(self, id, state):
		switch = self.get_switch_by_id(id)

		if switch:
			newstate = int(state)

			if not self.is_switch_one_command_type(id):
				off_ret = switch['off_ret']
				on_ret = switch['on_ret']

				if newstate:
					switch['state'] = 1
					self.mcu_callback('[T' + str(on_ret) +']' + switch['on'])
				else:
					switch['state'] = 0
					self.mcu_callback('[T' + str(off_ret) +']' + switch['off'])
				self.db_flush()
				self.aq.refresh_state(self.aq.REASON_RC)
			else:
				if state == 1:
					switch['state'] = 1
					on_ret = switch['on_ret'] - switch['counter']
					self.mcu_callback('[T' + str(on_ret) +']' + switch['on'])
					switch['counter'] = (switch['counter'] + on_ret) % (switch['on_ret'] + switch['off_ret'])
				else:
					switch['state'] = 0
					off_ret = switch['on_ret'] + switch['off_ret'] - switch['counter']
					self.mcu_callback('[T' + str(off_ret) +']' + switch['off'])
					switch['counter'] = (switch['counter'] + off_ret) % (switch['on_ret'] + switch['off_ret'])
				self.db_flush()
				self.aq.refresh_state(self.aq.REASON_RC)

	def process_received_cmd(self, cmd):
		if cmd.find("[R]") <> -1:
			self.handle_remote_r_cmd(cmd)

	def handle_remote_r_cmd(self, cmd):
		cmd = cmd.replace("[R]", "").strip()
		id = self.get_switch_id_by_cmd(cmd)
		if id <> None:
			switch = self.get_switch_by_id(id)

			if not self.is_switch_one_command_type(id):
				if cmd == switch['on']:
					newstate = 1
				else:
					newstate = 0
			else:
				curr_state = switch['state']

				switch['counter']  = (switch['counter'] + 1)  % (switch['on_ret'] + switch['off_ret'])
				if (switch['counter']) <> 0:
					newstate = 1
				elif (switch['counter']) == 0:
					newstate = 0
				else:
					newstate = curr_state

				print 'switch: ', id, 'state:', newstate, 'counter: ', switch['counter']

			if switch['state'] <> newstate:
				switch['state'] = int(newstate)
				self.db_flush()
				print 'switch: ', id, 'state:', newstate, 'counter: ', switch['counter']
				self.aq.refresh_state(self.aq.REASON_RC)

	def move_up(self, id):
		if id > 0:
			self.db['switches'].insert(id-1, self.db['switches'].pop(id))
			self.db_flush()

	def move_down(self, id):
		if id < len(self.db['switches']):
			self.db['switches'].insert(id+1, self.db['switches'].pop(id))
			self.db_flush()

	def remove(self, id):
		self.db['switches'].pop(id)
		self.db_flush()


	def is_switch_one_command_type(self, id):
		switch = self.get_switch_by_id(id)
		if switch:
			return switch['on'] == switch['off']
		return False

	def set_initial_states(self):
		self.mcu_callback('ping')

		for id in range(len(self.db['switches'])):
			switch = self.get_switch_by_id(id)
			time.sleep(2)
			self.set_switch(id, switch['state'])






