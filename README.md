# Core Flight System : Framework : Tool : Command Line

This repository contains NASA's Command Line Utility (commandline-tool), which is a framework component of the Core Flight System.

**cFS Command Line is a testing utility not intended for mission deployment.** Simple command line utilities to send a command or view telemery on the console. A demonstration bundle of the Core Flight System is available at <https://github.com/nasa/cFS> (which includes commandline-tool as a submodule) and includes build and execution instructions.

For information about a mission ready cFS bundle, see: <https://github.com/nasa/cFS#cfs-gov-mission-ready-version> 

## Known issues
See all [open issues](https://github.com/nasa/cfs-commandline-tools/issues).

## Testing command checksums

On a Linux host with a C compiler and Python 3, run:

```sh
python3 -m unittest discover -s tests -v
```

The tests build the non-EDS `cmd_send` tool in a temporary directory and receive
its packets using an ephemeral UDP port bound to `127.0.0.1`. They do not contact
a flight system. Set `CMDSEND_BINARY` to test an existing build, or `CC` and
`CFLAGS` to customize the temporary build.
