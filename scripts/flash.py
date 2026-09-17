#!/usr/bin/env python3
"""Explicit USB bootstrap; preserves pairing NVS and saved board settings."""
import argparse
import hashlib
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--antenna", choices=("internal", "external"), required=True)
    parser.add_argument("--folder", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--yes", action="store_true", help="Confirm bootstrap flash without prompting")
    args = parser.parse_args()
    files = [("0x0", "bootloader.bin"), ("0xc000", "partition-table.bin"),
             ("0x1d000", "ota_data_initial.bin"), ("0x20000", f"IR_Power_Meter_{args.antenna}.bin")]
    sums = dict(line.split("  ", 1)[::-1] for line in (args.folder / "SHA256SUMS").read_text().splitlines())
    for _, filename in files:
        if hashlib.sha256((args.folder / filename).read_bytes()).hexdigest() != sums.get(filename):
            parser.error(f"Checksum mismatch: {filename}")
    print("USB bootstrap rewrites bootloader, partition table, OTA selection and app slot 0.")
    print("Pairings and board configuration are NOT erased. Keep power connected.")
    print("Antenna argument initializes NEW board settings only; an existing saved choice wins.")
    if not args.yes and input("Type FLASH to continue: ") != "FLASH":
        return
    major = int(version("esptool").split(".")[0])
    command = [sys.executable, "-m", "esptool", "--chip", "esp32c6", "--port", args.port,
               "--baud", "460800", "write-flash" if major >= 5 else "write_flash"]
    for key, value in (("flash_mode", "dio"), ("flash_size", "4MB"), ("flash_freq", "80m")):
        command += ["--" + (key.replace("_", "-") if major >= 5 else key), value]
    for address, filename in files:
        command += [address, str(args.folder / filename)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
