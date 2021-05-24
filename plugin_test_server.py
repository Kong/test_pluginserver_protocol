#!/usr/bin/python3

import argparse
from typing import cast, Any, Optional
import json
import sys

from socketserver import ThreadingMixIn, UnixStreamServer, StreamRequestHandler

import msgpack


class StreamServer(ThreadingMixIn, UnixStreamServer):
	pass


class MsgPackHandler(StreamRequestHandler):
	def __init__(self, request, client_address, server):
		super().__init__(request, client_address, server)
		self.unpacker = msgpack.Unpacker(request)
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

	def send(self, msg):
		"log and send a msgpack response"
		self.log_data.append({"response": msg})
		self.request.write(msgpack.pack(msg))

	def handle(self):
		"called for a given connection from a client"
		for msg in self.unpacker:
			self.log_data.append({"request": msg})
			type, msgid, method, params = msg

			curr_spec = self.get_curr_spec(method)

			error, result = curr_spec.get('return', ('not implemented', None))
			self.send((1, msgid, error, result))

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


protocol_servers = {
	'MsgPack:1': MsgPackMockServer.start,
}


def route_protocol(spec):
	protocol = spec.get('protocol', 'MsgPack:1')
	if protocol not in protocol_servers:
		raise NotImplementedError(f"unknown protocol '{protocol}'")

	return protocol_servers[protocol](spec)


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

