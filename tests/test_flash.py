"""Dry-run the flash helper without any serial port or hardware."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meter_flash", ROOT / "scripts/flash.py")
flash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flash)


class FlashHelperTests(unittest.TestCase):
    def test_external_bootstrap_never_erases_flash(self):
        folder = ROOT / "dist/release"
        if not folder.exists():
            self.skipTest("Local compiled release assets not available in CI")
        argv = ["flash.py", "--port", "/dev/cu.usbmodem21201", "--antenna", "external",
                "--folder", str(folder), "--yes"]
        with patch.object(sys, "argv", argv), patch.object(flash, "version", return_value="4.12.0"), \
             patch.object(flash.subprocess, "run") as run:
            flash.main()
        command = run.call_args.args[0]
        self.assertIn("write_flash", command)
        self.assertIn("0x1d000", command)
        self.assertIn(str(folder / "IR_Power_Meter_external.bin"), command)
        self.assertNotIn("erase_flash", command)

    def test_bad_checksum_fails_before_opening_serial(self):
        folder = ROOT / "dist/release"
        if not folder.exists():
            self.skipTest("Local compiled release assets not available in CI")
        argv = ["flash.py", "--port", "/dev/cu.usbmodem21201", "--antenna", "external",
                "--folder", str(folder)]
        with patch.object(sys, "argv", argv), \
             patch.object(flash.hashlib, "sha256", return_value=type("Digest", (), {"hexdigest": lambda _: "bad"})()), \
             patch.object(flash.subprocess, "run") as run, \
             self.assertRaises(SystemExit):
            flash.main()
        run.assert_not_called()
