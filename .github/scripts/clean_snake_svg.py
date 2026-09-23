"""Remove snk's progress bar and crop each SVG to the cyber contribution grid."""
from __future__ import annotations

import re
import sys
from pathlib import Path

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    svg = path.read_text(encoding="utf-8")
    # The `u` rects form snk's progress bar beneath the grid. They render as an
    # unnecessary black slab on GitHub's image proxy, so remove and crop them.
    svg = re.sub(r'<rect class="u [^"]+"[^>]*/>', "", svg)
    svg = svg.replace('viewBox="-16 -32 880 192" width="880" height="192"', 'viewBox="-16 -16 880 144" width="880" height="144"')
    path.write_text(svg, encoding="utf-8")
