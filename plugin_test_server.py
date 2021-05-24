#!/usr/bin/python3

import argparse
import json
import sys
import logging

from socketserver import ThreadingMixIn, UnixStreamServer, StreamRequestHandler

import msgpack


class MpStream():
	def __init__(self, socket):
		self.socket = socket
		self.packer = msgpack.Packer()
		self.unpacker = msgpack.Unpacker(socket)

	def send(self, msg):
		self.socket.write(self.packer.pack(msg))

# ==== test servers ====


class StreamServer(ThreadingMixIn, UnixStreamServer):
	pass


class MsgPackHandler(StreamRequestHandler):
	def __init__(self, request, client_address, server):
		super().__init__(request, client_address, server)
		self.stream = MpStream(request)
		# self.unpacker = msgpack.Unpacker(request)
		self.on_methods = server.on_methods
		self.log_data = []
		self.method_counts = {}

	def get_curr_spec(self, method):
		"""
		given a method, return the current spec instance (or empty dict)
		and advance to the next one (with wraparound)
		"""
		if method not in self.on_methods:
			return {}

		method_count = self.method_counts.get(method, 0)
		method_spec = self.on_methods[method]
		curr_spec = method_spec[method_count % len(method_spec)]
		self.method_counts[method] = method_count + 1
		return curr_spec

	def handle(self):
		"called for a given connection from a client"
		for msg in self.stream.unpacker:
			self.log_data.append({"request": msg})
			type, msgid, method, params = msg

			curr_spec = self.get_curr_spec(method)

			error, result = curr_spec.get('return', ('not implemented', None))
			self.stream.send((1, msgid, error, result))

	def finish(self):
		"at the end of a connection, show what happened"
		print(json.dumps(self.log_data))
		self.finish()


class MsgPackMockServer():

	def __init__(self, streamserver, on_methods):
		super().__init__()
		streamserver.on_methods = on_methods
		self.streamserver = streamserver

	@staticmethod
	def start(spec):
		print("msgpack server....")
		socket = spec.get('socket', 'mock.socket')
		print(f"opening socket {socket}")
		on_methods = spec.get('on_methods', {})
		MsgPackMockServer(StreamServer(socket, MsgPackHandler), on_methods)


# ==== test clients ====


class MsgPackTestClient():

	def __init__(self, socket, try_methods):
		super().__init__()
		self.socketname = socket
		self.log_data = []
		self.try_methods = try_methods

	def try_method(self, m):
		method, params = m
		msg_id = 1
		self.stream.send((0, msg_id, method, params))

		for msg in self.stream.unpacker:
			#  TODO: compare with some expected
			if len(msg) == 3:
				self.log_data.append({"notification": msg})
			elif len(msg) == 4:
				r_type, r_msgid, r_err, r_result = msg
				if r_type == 1 and r_msgid == msg_id:
					self.log_data.append({"response": msg})
					if r_err:
						logging.error(f"receive error: {r_err}")
					return
				raise AssertionError(f"unexpected response: {msg}")
			else:
				raise AssertionError(f"malformed message received: {msg}")

	def try_all(self):
		with open(self.socketname) as socket:
			self.stream = MpStream(socket)
			for i, m in enumerate(self.try_methods):
				try:
					self.try_method(m)
				except Exception as e:
					logging.error(f"trying method #{i}: {e}")

	@staticmethod
	def start(spec):
		print("msgpack client....")
		socket = spec.get('socket', 'mock.socket')
		print(f"opening socket {socket}")
		try_methods = spec.get('try_methods', [])
		MsgPackTestClient(socket, try_methods).try_all()


# ==== command start ====


test_roles = {
	'server': {
		'MsgPack:1': MsgPackMockServer.start,
	},
	'client': {
		'MsgPack:1': MsgPackTestClient.start,
	},
}


def route_protocol(spec):
	role = spec.get('role')
	if role not in test_roles:
		raise NotImplementedError(f"unkown role '{role}'")

	protocol_handlers = test_roles[role]

	protocol = spec.get('protocol', 'MsgPack:1')
	if protocol not in protocol_handlers:
		raise NotImplementedError(f"unknown protocol '{protocol}'")

	return protocol_handlers[protocol](spec)


def main():
	parser = argparse.ArgumentParser(
		description="mocking a test server")
	# parser.add_argument('-v', '--version', action='version', version='plugin_test_server 1.0')
	# parser.add_argument('-n', '--name', metavar='<name>', help='An optional parameter')
	# parser.add_argument('-e', '--extra', action='store_true', help='This Value is False by default')
	parser.add_argument('-s', '--spec', help="JSON file with test specification (default /dev/stdin)")
	args = parser.parse_args()

	spec = load_spec(args.spec)
	route_protocol(spec)


def load_spec(fpath: str):
	if fpath is None:
		return json.load(sys.stdin)

	with open(fpath) as specfile:
		return json.load(specfile)


if __name__ == '__main__':
	main()
