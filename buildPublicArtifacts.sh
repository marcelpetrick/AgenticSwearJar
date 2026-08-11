#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
public_dir="$project_root/public"
mkdir -p "$public_dir/slides"

"$project_root/swear-stats" --strict-inputs --redact-terms \
  --json "$public_dir/report.json" --output "$public_dir/report.html"
python3 "$project_root/scripts/buildLinkedInCarousel.py" \
  "$public_dir/report.json" "$public_dir/linkedin-carousel.html"

carousel_url="file://$public_dir/linkedin-carousel.html"
for slide in 1 2 3 4; do
  chromium --headless --no-sandbox --disable-gpu --hide-scrollbars \
    --run-all-compositor-stages-before-draw --virtual-time-budget=1000 \
    --window-size=1080,1080 --screenshot="$public_dir/slides/slide-$slide.png" \
    "$carousel_url?slide=$slide" >/dev/null 2>&1
done

img2pdf "$public_dir"/slides/slide-{1,2,3,4}.png \
  --output "$public_dir/agentic-swear-jar-linkedin.pdf"
printf 'Public artifacts: %s\n' "$public_dir"
