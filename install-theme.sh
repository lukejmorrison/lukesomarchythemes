#!/usr/bin/env bash
# Link a theme folder from this collection into Omarchy and apply it.

set -euo pipefail

slug="${1:-}"
if [[ -z $slug || $slug == -h || $slug == --help ]]; then
  echo "Usage: ./install-theme.sh <theme-slug>" >&2
  echo "Themes:" >&2
  root="$(cd "$(dirname "$0")" && pwd)"
  for d in "$root"/*/; do
    [[ -f ${d}colors.toml ]] && echo "  $(basename "$d")" >&2
  done
  exit 1
fi

root="$(cd "$(dirname "$0")" && pwd)"
src="$root/$slug"
dest="$HOME/.config/omarchy/themes/$slug"

if [[ ! -d $src ]]; then
  echo "No theme folder: $src" >&2
  exit 1
fi

if [[ ! -f $src/colors.toml ]]; then
  echo "Not an Omarchy theme (missing colors.toml): $src" >&2
  exit 1
fi

mkdir -p "$HOME/.config/omarchy/themes"
ln -sfn "$src" "$dest"
omarchy theme set "$slug"
echo "Applied $slug from $src"
