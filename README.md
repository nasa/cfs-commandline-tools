# commandline-tools
Simple command line utilities to send a command or view telemery on the console.

## Testing command checksums

On a Linux host with a C compiler and Python 3, run:

```sh
python3 -m unittest discover -s tests -v
```

The tests build the non-EDS `cmd_send` tool in a temporary directory and receive
its packets using an ephemeral UDP port bound to `127.0.0.1`. They do not contact
a flight system. Set `CMDSEND_BINARY` to test an existing build, or `CC` and
`CFLAGS` to customize the temporary build.
