"""Build cmd_send and check real UDP packets using only loopback sockets."""

import functools
import operator
import os
from pathlib import Path
import shlex
import socket
import struct
import subprocess
import tempfile
import unittest


class TestCommandChecksum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = os.environ.get("CMDSEND_BINARY")
        if cls.binary is None:
            root = Path(__file__).resolve().parents[1]
            cls.binary = str(Path(cls.build.name) / "cmd_send")
            sources = [
                "cmd_send.c",
                "send_udp.c",
                "console_utils.c",
                "passthru_encode.c",
            ]
            command = shlex.split(os.environ.get("CC", "cc"))
            command += ["-std=c99", "-D_DEFAULT_SOURCE", "-I" + str(root / "src")]
            command += shlex.split(os.environ.get("CFLAGS", ""))
            command += [str(root / "src" / name) for name in sources]
            command += ["-o", cls.binary]
            subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=60
            )

    def packet(self, protocol, payload_options, endian="BE", extra=()):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(3)
            command = [
                self.binary,
                "--host",
                "127.0.0.1",
                "--port",
                str(receiver.getsockname()[1]),
                "--protocol",
                protocol,
                "--endian",
                endian,
                *extra,
                *payload_options,
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return receiver.recv(4096)

    def assert_packet(self, packet, protocol, payload, endian="BE", override=None):
        header_size = 8 if protocol == "cfsv1" else 12
        header = struct.pack(">HHH", 0x1800, 0xC000, header_size + len(payload) - 7)
        if protocol == "cfsv2":
            header += struct.pack(">HH", 0x0400 if endian == "LE" else 0, 0)
        expected = bytearray(header + bytes([0, 0]) + payload)
        expected[header_size - 1] = (
            functools.reduce(operator.xor, expected, 0xFF)
            if override is None
            else override
        )
        self.assertEqual(packet, bytes(expected))
        self.assertEqual(packet[header_size:], payload)
        if override is None:
            self.assertEqual(functools.reduce(operator.xor, packet, 0), 0xFF)
            if payload:
                corrupted = bytearray(packet)
                corrupted[-1] ^= 1
                self.assertNotEqual(functools.reduce(operator.xor, corrupted, 0), 0xFF)

    def test_checksum_covers_payload_for_both_command_protocols(self):
        for protocol in ("cfsv1", "cfsv2"):
            for endian in ("BE", "LE"):
                for payload in (b"", b"\x01", b"\x01\x02\x04", b"\x01\x01"):
                    with self.subTest(
                        protocol=protocol, endian=endian, payload=payload
                    ):
                        options = [
                            part
                            for value in payload
                            for part in ("--uint8", str(value))
                        ]
                        packet = self.packet(protocol, options, endian)
                        self.assert_packet(packet, protocol, payload, endian)

    def test_numeric_and_padded_string_payload_bytes_are_unchanged(self):
        for protocol in ("cfsv1", "cfsv2"):
            for endian, prefix in (("BE", ">"), ("LE", "<")):
                cases = [
                    (["--uint32", "0x10203040"], struct.pack(prefix + "I", 0x10203040)),
                    (["--float", "1.25"], struct.pack(prefix + "f", 1.25)),
                    (["--string", "6:AB"], b"AB\x00\x00\x00\x00"),
                ]
                for options, payload in cases:
                    with self.subTest(
                        protocol=protocol, endian=endian, options=options
                    ):
                        self.assert_packet(
                            self.packet(protocol, options, endian),
                            protocol,
                            payload,
                            endian,
                        )

    def test_explicit_checksum_override_is_preserved(self):
        for protocol in ("cfsv1", "cfsv2"):
            for checksum in (0, 0x5A, 0xFF):
                with self.subTest(protocol=protocol, checksum=checksum):
                    packet = self.packet(
                        protocol, ["--uint8", "1"], extra=["--pktcksum", str(checksum)]
                    )
                    self.assert_packet(packet, protocol, b"\x01", override=checksum)

    def test_protocols_without_command_secondary_headers_are_unchanged(self):
        payload = b"AB\x00\x00"
        for protocol, header_size in (("ccsdspri", 6), ("ccsdsext", 10)):
            with self.subTest(protocol=protocol):
                packet = self.packet(protocol, ["--string", "4:AB"])
                header = b""
                if header_size:
                    header = struct.pack(
                        ">HHH", 0x1000, 0xC000, header_size + len(payload) - 7
                    )
                if protocol == "ccsdsext":
                    header += b"\x00" * 4
                self.assertEqual(packet, header + payload)

    def test_packet_length_limit_and_header_overrides(self):
        for protocol, header_size in (("cfsv1", 8), ("cfsv2", 12)):
            with self.subTest(protocol=protocol):
                payload = b"A" + b"\x00" * (2048 - header_size - 1)
                packet = self.packet(protocol, ["--string", str(len(payload)) + ":A"])
                self.assertEqual(len(packet), 2048)
                self.assert_packet(packet, protocol, payload)
                overridden = self.packet(
                    protocol,
                    ["--uint8", "1"],
                    extra=[
                        "--pktapid",
                        "33",
                        "--pktfc",
                        "42",
                        "--pktseqcnt",
                        "7",
                        "--pktlen",
                        "100",
                    ],
                )
                self.assertEqual(
                    struct.unpack(">HHH", overridden[:6]), (0x1821, 0xC007, 100)
                )
                self.assertEqual(overridden[header_size - 2], 42)
                self.assertEqual(functools.reduce(operator.xor, overridden, 0), 0xFF)


if __name__ == "__main__":
    unittest.main()
