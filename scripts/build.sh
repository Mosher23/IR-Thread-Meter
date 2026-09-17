#!/usr/bin/env bash
set -eo pipefail
# Source ESP-IDF and ESP-Matter export.sh first. Spaces in paths are supported.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
variant="${1:-external}"
case "$variant" in
  internal|external) defaults="sdkconfig.defaults;sdkconfig.${variant}.defaults" ;;
  ota) defaults="sdkconfig.defaults;sdkconfig.ota.defaults" ;;
  *) echo "Usage: bash scripts/build.sh internal|external|ota" >&2; exit 2 ;;
esac
cd "$repo_dir/firmware"
idf.py -B "build-${variant}" -D CCACHE_ENABLE=1 -D "SDKCONFIG=sdkconfig.${variant}" \
  -D "SDKCONFIG_DEFAULTS=$defaults" build
