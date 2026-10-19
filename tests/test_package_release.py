"""Verify OTA-only packaging without antenna-specific build directories."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_ota import image_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meter_package_test", ROOT / "scripts/package_release.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class UniversalOtaPackageTests(unittest.TestCase):
    def source_fixture(self, root, version=16, version_string="1.15"):
        source = root / "firmware"
        (source / "main").mkdir(parents=True)
        (source / "main/MatterProjConfig.h").write_text(
            f'#define CHIP_DEVICE_CONFIG_DEVICE_SOFTWARE_VERSION {version}\n'
            f'#define CHIP_DEVICE_CONFIG_DEVICE_SOFTWARE_VERSION_STRING "{version_string}"\n')
        (source / "CMakeLists.txt").write_text(
            f'set(PROJECT_VER "{version_string}")\nset(PROJECT_VER_NUMBER {version})\n')
        (source / "sdkconfig.defaults").write_text(f'CONFIG_DEVICE_SOFTWARE_VERSION_NUMBER={version}\n')
        build = source / "build-ota"
        (build / "config").mkdir(parents=True)
        (build / "config/sdkconfig.h").write_text(
            '#define CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE 1\n'
            f'#define CONFIG_DEVICE_SOFTWARE_VERSION_NUMBER {version}\n'
            '#define CONFIG_SMARTMETER_REQUIRE_BOARD_CONFIG 1\n'
            '#define CONFIG_CHIP_FACTORY_NAMESPACE_PARTITION_LABEL "nvs"\n'
            '#define CONFIG_EXAMPLE_COMMISSIONABLE_DATA_PROVIDER 1\n'
            '#define CONFIG_EXAMPLE_DEVICE_INSTANCE_INFO_PROVIDER 1\n')
        (build / "project_description.json").write_text(json.dumps({"project_version": version_string}))
        (build / "IR_Meter_Thread_Matter.bin").write_bytes(b"application fixture")
        return source

    def test_universal_package_needs_no_usb_builds_or_usb_flashing_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source_fixture(root)
            output = root / "release"
            image = image_fixture(version=16, version_string="1.15", **{"6": 15})

            def create_image(command, *, check):
                self.assertTrue(check)
                self.assertEqual(command[2], "create")
                self.assertEqual(command[command.index("-vn") + 1], "16")
                self.assertEqual(command[command.index("-ma") + 1], "15")
                self.assertEqual(Path(command[-2]).parent.name, "build-ota")
                Path(command[-1]).write_bytes(image)

            with patch.dict("os.environ", {"ESP_MATTER_PATH": str(root / "sdk")}), \
                 patch.object(packager.subprocess, "run", side_effect=create_image) as run:
                packager.package(source, output, ota_only=True)
            run.assert_called_once()
            self.assertEqual({path.name for path in output.iterdir()},
                             {"IR_Power_Meter.ota", "ota-manifest.json", "provisioning.json", "SHA256SUMS"})
            manifest = json.loads((output / "ota-manifest.json").read_text())
            release = packager.ota.parse_manifest(manifest, "v1.15", {manifest["url"]})
            packager.ota.validate_image((output / "IR_Power_Meter.ota").read_bytes(), release)
            for line in (output / "SHA256SUMS").read_text().splitlines():
                checksum, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), checksum)

    def test_ota_only_rejects_usb_only_firmware_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.source_fixture(root, version=8, version_string="1.7")
            output = root / "release"
            with self.assertRaisesRegex(ValueError, "USB-only firmware"):
                packager.package(source, output, ota_only=True)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
