#!/bin/bash
# When Kingdom Age is applied, use the fig-tree verse Matrix screensaver
# and refresh the RSS cache. When leaving it, restore the stock Omarchy
# wordmark if we still own branding.

set -euo pipefail

theme="${1:-}"
verses="$HOME/.config/omarchy/themes/kingdom-age/screensaver.txt"
branding="$HOME/.config/omarchy/branding/screensaver.txt"
stock="${OMARCHY_PATH:-/usr/share/omarchy}/logo.txt"

if [[ $theme == kingdom-age ]]; then
  if [[ -f $verses ]]; then
    mkdir -p "$(dirname "$branding")"
    cp "$verses" "$branding"
  fi
  helper="$HOME/.config/omarchy/themes/kingdom-age/scripts/omarchy-screensaver-rss"
  if [[ -x $helper ]]; then
    "$helper" refresh >/dev/null 2>&1 || true
  fi
  exit 0
fi

if [[ -f $branding ]] && grep -q 'KINGDOM AGE' "$branding" 2>/dev/null; then
  cp "$stock" "$branding"
fi
