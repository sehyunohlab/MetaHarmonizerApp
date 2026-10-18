#!/usr/bin/env bash
# Download the published KB bundle from the kb-latest release into DEST_DIR as
# kb_offline_bundle.tar.gz, joining its parts when it is published in parts
# (listed in order by kb_offline_bundle.tar.gz.parts). Needs GH_TOKEN.
#
#   scripts/fetch_kb_release.sh DEST_DIR
set -euo pipefail

dest=${1:?usage: fetch_kb_release.sh DEST_DIR}
mkdir -p "$dest"
gh release download kb-latest -p 'kb_offline_bundle.tar.gz*' -D "$dest" --clobber
if [ -f "$dest/kb_offline_bundle.tar.gz.parts" ]; then
  : > "$dest/kb_offline_bundle.tar.gz"
  while read -r part; do
    [ -n "$part" ] || continue
    [[ "$part" =~ ^[A-Za-z0-9._-]+\.part[0-9]{2}$ ]] || { echo "Invalid KB bundle part: $part" >&2; exit 1; }
    cat "$dest/$part" >> "$dest/kb_offline_bundle.tar.gz"
    rm -f "$dest/$part"
  done < "$dest/kb_offline_bundle.tar.gz.parts"
  rm -f "$dest/kb_offline_bundle.tar.gz.parts"
fi
