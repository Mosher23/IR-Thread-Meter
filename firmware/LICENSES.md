# Licensing notes

This adaptation contains code under multiple compatible open-source terms.

## Project adaptation

The original `zigbee-smartmeter-reader` project is published under the GNU
General Public License version 3. This derivative adaptation should therefore
be redistributed under GPL-3.0 while preserving source and attribution.

Original project: https://gitlab.com/clausmuus/zigbee-smartmeter-reader

## SML parser

`main/sml.cpp`, `main/sml.h`, and `main/smlCrcTable.h` are derived from
`olliiiver/sml_parser` and retain their LGPL-2.1 notices.

Original parser: https://github.com/olliiiver/sml_parser

## ESP-Matter patterns

The Matter endpoint, OpenThread initialization, event callback, and delegate
patterns were adapted from Espressif ESP-Matter examples, which state that the
example code is public domain or CC0, at the recipient's option.

ESP-Matter: https://github.com/espressif/esp-matter

This file is a summary, not legal advice. Refer to each upstream project's full
license text before redistribution.
