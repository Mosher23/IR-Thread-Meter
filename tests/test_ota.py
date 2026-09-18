"""Run with Python 3.11+: python -m unittest discover -s tests -v."""
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meter_ota_test", ROOT / "custom_components/smartmeter/ota.py")
ota = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ota
spec.loader.exec_module(ota)


def image_fixture(version=9, version_string="1.8", **changes):
    payload = bytearray(b"\xe9" + b"\x00" * 0xBF)
    struct.pack_into("<I", payload, 0x20, 0xABCD5432)
    payload[0x30:0x30 + len(version_string)] = version_string.encode()
    fields = {0: ota.VID, 1: ota.PID, 2: version, 3: version_string, 4: len(payload),
              5: 8, 6: 8, 8: 1, 9: hashlib.sha256(payload).digest()}
    fields.update({int(k): v for k, v in changes.items()})
    tlv = bytearray(b"\x15")
    for tag, value in fields.items():
        if isinstance(value, int):
            tlv += bytes((0x26, tag)) + value.to_bytes(4, "little")
        else:
            encoded = value.encode() if isinstance(value, str) else value
            tlv += bytes((0x2C if isinstance(value, str) else 0x30, tag, len(encoded))) + encoded
    tlv += b"\x18"
    return struct.pack("<IQI", 0x1BEEF11E, 16 + len(tlv) + len(payload), len(tlv)) + tlv + payload


def manifest_fixture(image=None):
    image = image or image_fixture()
    return {"schema": 1, "vendor_id": ota.VID, "product_id": ota.PID, "hardware_version": 1,
            "software_version": 9, "version_string": "1.8", "min_version": 8, "max_version": 8,
            "size": len(image), "sha256": hashlib.sha256(image).hexdigest(),
            "url": f"https://github.com/{ota.REPOSITORY}/releases/download/v1.8/IR_Power_Meter.ota"}


def ready_attributes():
    return {"0/40/2": ota.VID, "0/40/4": ota.PID, "0/40/7": 1, "0/40/9": 8,
            "0/40/10": "1.7", f"1/{0xFFF1FC01}/4": True}


class OtaValidationTests(unittest.TestCase):
    def release(self, data):
        return ota.parse_manifest(data, "v1.8", {data["url"]})

    def test_valid_image(self):
        ota.validate_image(image_fixture(), self.release(manifest_fixture()))

    def test_corruption(self):
        image = image_fixture()
        with self.assertRaises(ValueError):
            ota.validate_image(image[:-1] + b"X", self.release(manifest_fixture(image)))

    def test_manifest_fields(self):
        for key, value in (("vendor_id", 1), ("product_id", 2), ("hardware_version", 2),
                           ("software_version", True), ("min_version", 7), ("max_version", 10),
                           ("size", ota.MAX_IMAGE + 1), ("sha256", "oops"),
                           ("url", "https://example.com/image.ota"), ("version_string", "1.9")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.release(dict(manifest_fixture(), **{key: value}))

    def test_asset_must_exist(self):
        with self.assertRaises(ValueError):
            ota.parse_manifest(manifest_fixture(), "v1.8", set())

    def test_header_cannot_disagree_with_manifest_even_with_valid_file_hash(self):
        for field, value in (("0", 123), ("1", 123), ("2", 10), ("3", "1.9"),
                             ("5", 7), ("6", 9), ("8", 2), ("9", b"bad digest")):
            image = image_fixture(**{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                ota.validate_image(image, self.release(manifest_fixture(image)))

    def test_embedded_app_version_must_match_header(self):
        image = bytearray(image_fixture())
        _, payload = ota.ota_header(image)
        offset = len(image) - len(payload) + 0x30
        image[offset:offset + 3] = b"1.6"
        fields, payload = ota.ota_header(image)
        # Update TLV digest to make the payload internally consistent; the
        # embedded app version must still be rejected.
        old_digest = fields[9]
        digest_at = image.index(old_digest, 16, len(image) - len(payload))
        image[digest_at:digest_at + 32] = hashlib.sha256(payload).digest()
        with self.assertRaisesRegex(ValueError, "application version disagree"):
            ota.validate_image(bytes(image), self.release(manifest_fixture(image)))

    def test_malformed_headers(self):
        image = image_fixture()
        for damaged in (b"", image[:16], b"BAD!" + image[4:], image[:-2],
                        image[:12] + struct.pack("<I", 4097) + image[16:]):
            with self.assertRaises(ValueError):
                ota.ota_header(damaged)

    def test_bootstrap_same_version_manifest_is_valid_but_not_an_upgrade(self):
        data = dict(manifest_fixture(), software_version=8, version_string="1.7", delivery="usb")
        release = ota.parse_manifest(data, "v1.7", set())
        self.assertTrue(release.usb_only)
        with self.assertRaises(ValueError):
            ota.validate_image(image_fixture(version=8, version_string="1.7"), release)

    def test_capability_and_bootstrap_gate(self):
        client = SimpleNamespace(server_info=SimpleNamespace(schema_version=13), upload_ota_file=lambda _: None)
        attrs = ready_attributes()
        self.assertIsNone(ota.compatibility(client, attrs, 1))
        for key, value in (("0/40/9", 7), (f"1/{0xFFF1FC01}/4", False), ("0/40/2", 123)):
            self.assertIsNotNone(ota.compatibility(client, dict(attrs, **{key: value}), 1))
        client.server_info.schema_version = 12
        self.assertIn("schema 13", ota.compatibility(client, attrs, 1))
        client.server_info.schema_version = 13
        client.upload_ota_file = None
        self.assertIsNotNone(ota.compatibility(client, attrs, 1))


if __name__ == "__main__":
    unittest.main()
