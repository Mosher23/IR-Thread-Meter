"""Strict, dependency-free validation of our release manifest and Matter image."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import struct
from urllib.parse import quote

REPOSITORY = "Mosher23/IR-Thread-Meter"
VID, PID = 0xFFF1, 0x8000
BOOTSTRAP_VERSION = 8
MAX_PAYLOAD = 0x1E0000
MAX_IMAGE = MAX_PAYLOAD + 4096
MAX_JSON = 128 * 1024


@dataclass(frozen=True)
class Release:
    tag: str
    version: int
    version_string: str
    minimum: int
    maximum: int
    size: int
    sha256: str
    url: str
    notes_url: str
    usb_only: bool = False


def parse_manifest(data: dict, tag: str, asset_urls: set[str]) -> Release:
    """Only accept our product, hardware and a same-release GitHub asset."""
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported OTA manifest schema")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+(?:\.[0-9]+)?", tag):
        raise ValueError("Not a stable firmware release tag")
    for key in ("vendor_id", "product_id", "hardware_version", "software_version"):
        if type(data.get(key)) is not int:
            raise ValueError(f"Invalid {key}")
    if (data["vendor_id"], data["product_id"], data["hardware_version"]) != (VID, PID, 1):
        raise ValueError("Release is not for this XIAO meter hardware")
    version = data["software_version"]
    version_string = data.get("version_string")
    if not isinstance(version_string, str) or not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", version_string):
        raise ValueError("Invalid version string")
    if tag != f"v{version_string}":
        raise ValueError("Manifest version does not match GitHub tag")
    notes = f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
    if data.get("delivery") == "usb" and version == BOOTSTRAP_VERSION:
        return Release(tag, version, version_string, version, version, 0, "", "", notes, True)
    if data.get("delivery", "ota") != "ota":
        raise ValueError("Unsupported release delivery method")
    for key in ("min_version", "max_version", "size"):
        if type(data.get(key)) is not int:
            raise ValueError(f"Invalid {key}")
    minimum, maximum = data["min_version"], data["max_version"]
    if not (BOOTSTRAP_VERSION <= minimum <= maximum < version <= 0xFFFFFFFF):
        raise ValueError("Invalid version range or missing USB bootstrap requirement")
    if not 16 < data["size"] <= MAX_IMAGE:
        raise ValueError("OTA image exceeds the flash slot size")
    checksum = data.get("sha256", "")
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid SHA-256 checksum")
    expected = f"https://github.com/{REPOSITORY}/releases/download/{quote(tag, safe='')}/IR_Power_Meter.ota"
    if data.get("url") != expected or expected not in asset_urls:
        raise ValueError("OTA asset is not attached to the selected repository release")
    return Release(tag, version, version_string, minimum, maximum, data["size"],
                   checksum, expected, notes)


def ota_header(image: bytes) -> tuple[dict, bytes]:
    """Decode the limited Matter OTA header types emitted by ota_image_tool.py.

    A deliberately strict reader: anonymous structure, context tags, unsigned
    integers, UTF-8 strings and octet strings. No nested/unknown wire types.
    """
    if not 16 < len(image) <= MAX_IMAGE:
        raise ValueError("Invalid OTA file size")
    magic, total, length = struct.unpack_from("<IQI", image)
    if magic != 0x1BEEF11E or total != len(image) or not 2 <= length <= 4096:
        raise ValueError("Invalid Matter OTA header")
    end = 16 + length
    if end >= len(image) or image[16] != 0x15 or image[end - 1] != 0x18:
        raise ValueError("Invalid OTA TLV structure")
    fields, pos = {}, 17
    while pos < end - 1:
        if pos + 2 > end - 1:
            raise ValueError("Truncated OTA field")
        control, tag = image[pos:pos + 2]
        pos += 2
        kind = control & 0x1F
        if control >> 5 != 1 or tag in fields:
            raise ValueError("Invalid/duplicate OTA header tag")
        if 4 <= kind <= 7:
            width = 1 << (kind - 4)
            if pos + width > end - 1:
                raise ValueError("Truncated integer")
            value = int.from_bytes(image[pos:pos + width], "little")
            pos += width
        elif 12 <= kind <= 19:
            width = 1 << ((kind - 12) % 4)
            if pos + width > end - 1:
                raise ValueError("Truncated string length")
            size = int.from_bytes(image[pos:pos + width], "little")
            pos += width
            if pos + size > end - 1:
                raise ValueError("Truncated string")
            value = image[pos:pos + size]
            pos += size
            if kind < 16:
                value = value.decode("utf-8")
        else:
            raise ValueError("Unsupported OTA header type")
        fields[tag] = value
    return fields, image[end:]


def validate_image(image: bytes, release: Release) -> None:
    """Check release hash, actual product/version header, and payload digest."""
    if release.usb_only or len(image) != release.size or hashlib.sha256(image).hexdigest() != release.sha256:
        raise ValueError("OTA download size or SHA-256 mismatch")
    header, payload = ota_header(image)
    expected = {0: VID, 1: PID, 2: release.version, 3: release.version_string,
                4: len(payload), 5: release.minimum, 6: release.maximum, 8: 1,
                9: hashlib.sha256(payload).digest()}
    if any(header.get(key) != value for key, value in expected.items()):
        raise ValueError("Matter OTA header/digest does not match the release")
    if not payload or payload[0] != 0xE9 or len(payload) > MAX_PAYLOAD:
        raise ValueError("Not a slot-sized ESP application image")
    if len(payload) < 0x70 or payload[0x20:0x24] != struct.pack("<I", 0xABCD5432):
        raise ValueError("Missing ESP-IDF application description")
    embedded_version = payload[0x30:0x50].split(b"\x00", 1)[0].decode("ascii")
    if embedded_version != release.version_string:
        raise ValueError("Matter OTA header and actual ESP application version disagree")


def compatibility(client, attributes: dict, endpoint: int) -> str | None:
    """Return an actionable reason rather than failing other HA platforms."""
    info = getattr(client, "server_info", None)
    if getattr(info, "schema_version", 0) < 13 or not callable(getattr(client, "upload_ota_file", None)):
        return "OTA upload requires Matter Server API schema 13 and a compatible HA Matter client"
    if (attributes.get("0/40/2"), attributes.get("0/40/4"), attributes.get("0/40/7")) != (VID, PID, 1):
        return "The selected device identity is not the supported XIAO IR Power Meter"
    current = attributes.get("0/40/9")
    if type(current) is not int or current < BOOTSTRAP_VERSION or attributes.get(f"{endpoint}/{0xFFF1FC01}/4") is not True:
        return "Install the v1.7 (or newer) USB bootstrap first to save the antenna and enable rollback"
    return None
