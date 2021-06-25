
This project consist of a simple process to exercise the protocol between Kong and external pluginservers.

It can take place of either a pluginserver (to test Kong's use of the protocol) or of Kong itself (to test new pluginservers).

## Installing

The only requirement is the MsgPack library.  Install with `pip` like this:

```
pip3 install -r requirements.txt
```

Optionally within a virtualev.

## Running

```
usage: plugin_test_server.py [-h] [-s SPEC] [-v]

mocking a test server

optional arguments:
  -h, --help            show this help message and exit
  -s SPEC, --spec SPEC  JSON file with test specification (default /dev/stdin)
  -v, --verbose

```

The specfile is a JSON file specifying the role and actions it should take.  Alternatively, it could be passed to the standard input.

There are three required, "global" parameters:

### `protocol`

Currently the only implemented protocol is `"MsgPack:1"`.

### `socket`

Specifies the pathname of the socket file to use.  Can be either an absolute pathname or relative to the current directory.

### `role`

Can be either `"server"` or `"client"`.


## Server Role

Used to replace an actual pluginserver, to test Kong's implementation of the protocol.  It will create the socket file and wait for requests.  The current MsgPack  RPC protocol means the requests will come as a MsgPack array of the form:

```
[type, msgid, method, params]
```

### `on_methods`

Serves to specify the responses to send back for each method.  For example:

```
{
	"protocol": "MsgPack:1",
	"socket": "mock.socket",

	"role": "server",
	"on_methods": {
		"plugin.StartInstance": [
			{ "return": [null, "{}"]}
		],
		"plugin.HandleEvent": [
			{ "return": [null, ["kong.log.debug", ["hi"]]]}
		],
		"plugin.Step": [
			{ "return": [null, ["kong.log.debug", ["done"]]]},
			{ "return": [null, "ret"]}
		]
	},
}
```

Each handled method is an array of predefined responses.  For the `"plugin.StartInstance"` and `"plugin.HandleEvent"` cases, there's a single response, so it will be sent on each request of the respective method.  For `"plugin.Step"` there are two responses, so the first request will be get the first response, and the second request will get the second answer.  A third request, would get the first response again and so on, alternating between the two responses.  Input parameters are ignored.

Each request and response for a given client connection is logged and dumpled as a JSON text when the client (Kong) closes the connection.  This allows a test method to verify the right parameters are sent.

## Client Role

Used to test a pluginserver, perhaps to develop a new one on any language.  It doesn't create the socket file but expects it to be created by the server under test, waiting for it to exist if necessary.

### `start_cmd`

Optional command to start the pluginserver to test.

### `try_methods`

Example:

```
{
	"protocol": "MsgPack:1",
	"socket": "/usr/local/kong/go-bip-a.socket",

	"role": "client",
	"start_cmd": "/usr/local/kong/go-plugins/go-bip-a",
	"try_methods": [
		["plugin.StartInstance", [{"Name": "plugname", "Config": "{}"}]],
		["plugin.HandleEvent", [{"InstanceId": 0, "EventName": "access"}]],
		["plugin.Step", [{"EventId": 0, "Data": {}}]],
		["plugin.CloseInstance", [0]]
	]
}
```

Each item in the `"try_methods"` array specifies the method name and the arguments to send.  After sending each one, it will wait for the respective response before going to the next request.  Every message in the socket is output in the log, including requests sent and both responses and notifications sent by the server.

If it receives a malformed message, it terminates the connection (after logging the received message).  An error response, on the other hand, is logged appropriately and the test continues.
