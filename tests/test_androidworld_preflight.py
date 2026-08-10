from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "androidworld_preflight.py"
SPEC = importlib.util.spec_from_file_location("androidworld_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AndroidWorldPreflightTests(unittest.TestCase):
    def test_parse_adb_devices_with_metadata(self) -> None:
        output = """List of devices attached
emulator-5554 device product:sdk_gphone_x86_64 model:sdk_gphone_x86_64 transport_id:1
192.0.2.3:5555 offline transport_id:2
"""
        devices = MODULE._parse_devices(output)
        self.assertEqual(devices[0]["serial"], "emulator-5554")
        self.assertEqual(devices[0]["model"], "sdk_gphone_x86_64")
        self.assertEqual(devices[1]["state"], "offline")

    def test_host_bridge_route_requires_a_reachable_android_emulator_gateway(self) -> None:
        self.assertTrue(
            MODULE._host_bridge_route_ready(
                {"returncode": 0, "output": "10.0.2.2 via 10.0.2.2 dev wlan0 src 10.0.2.16"}
            )
        )
        self.assertFalse(MODULE._host_bridge_route_ready({"returncode": 1, "output": "RTNETLINK: Network is unreachable"}))
        self.assertFalse(MODULE._host_bridge_route_ready(None))


if __name__ == "__main__":
    unittest.main()
