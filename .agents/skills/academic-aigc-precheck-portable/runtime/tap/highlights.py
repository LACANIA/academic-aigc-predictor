"""STEP-02: sample-scoped PDF geometry and text evidence, no AI prediction."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from pathlib import Path
import re
import statistics
import unicodedata

import pymupdf as fitz

from .audit import audit_pdf, is_blue_candidate, sha256_file

EXTRACTOR_VERSION = "step02-0.1.0"
PROFILE = {"rgb": (0.320312, 0.777344, 0.855469), "rgb_tolerance": 0.04,
           "opacity": (0.35, 0.45), "character_coverage_threshold": 0.45,
           "uncertain_coverage_floor": 0.05, "max_rect_height_pt": 35}


def intersection(a, b):
    rect = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return rect if rect[2] > rect[0] and rect[3] > rect[1] else None


def area(rect):
    return max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])


def union_area(rects):
    """Exact axis-aligned rectangle union; never add overlapping areas twice."""
    rects = [r for r in rects if area(r) > 0]
    xs = sorted({r[i] for r in rects for i in (0, 2)})
    result = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((r[1], r[3]) for r in rects if r[0] < right and r[2] > left)
        total = 0.0
        low = high = None
        for a, b in intervals:
            if low is None:
                low, high = a, b
            elif a > high:
                total += high - low
                low, high = a, b
            else:
                high = max(high, b)
        if low is not None:
            total += high - low
        result += (right - left) * total
    return result


def coverage(rect, regions):
    clipped = [i for r in regions if (i := intersection(rect, r))]
    return min(1.0, union_area(clipped) / area(rect)) if area(rect) else 0.0


def components(regions):
    """Group touching rectangles; keep their union, not a filled bounding box."""
    groups = []
    remaining = set(range(len(regions)))
    while remaining:
        group = {remaining.pop()}
        queue = list(group)
        while queue:
            i = queue.pop()
            a = regions[i]["rect"]
            for j in list(remaining):
                b = regions[j]["rect"]
                if a[0] <= b[2] + 0.5 and b[0] <= a[2] + 0.5 and a[1] <= b[3] + 0.5 and b[1] <= a[3] + 0.5:
                    remaining.remove(j)
                    group.add(j)
                    queue.append(j)
        members = [regions[i] for i in sorted(group)]
        groups.append({"region_ids": [r["region_id"] for r in members],
                       "rectangles": [r["rect"] for r in members],
                       "union_area_pt2": union_area([r["rect"] for r in members])})
    return groups


def extract_page_text(page, page_number):
    blocks, characters, lines = [], [], []
    raw = page.get_text("rawdict")
    for bi, block in enumerate(raw["blocks"]):
        if block["type"] != 0:
            continue
        output = {"block_id": f"p{page_number}_b{bi}", "page": page_number, "bbox": list(block["bbox"]), "line_ids": [], "character_ids": []}
        for li, line in enumerate(block["lines"]):
            # Header/footer exclusion is recorded by scope, not silently negative.
            if line["bbox"][1] < 65 or line["bbox"][3] > page.rect.height - 62:
                continue
            lid = f"p{page_number}_b{bi}_l{li}"
            ids, text = [], []
            for span in line["spans"]:
                for c in span["chars"]:
                    cid = len(characters)
                    ids.append(cid)
                    text.append(c["c"])
                    characters.append({"character_id": f"p{page_number}_c{cid}", "page": page_number,
                                       "block_id": output["block_id"], "line_id": lid,
                                       "text": c["c"], "bbox": list(c["bbox"]), "origin": list(c["origin"]),
                                       "font": span["font"], "font_size": span["size"],
                                       "synthetic": c.get("synthetic", False)})
            if not ids:
                continue
            lines.append({"line_id": lid, "page": page_number, "bbox": list(line["bbox"]),
                          "character_indexes": ids, "original_text": "".join(text)})
            output["line_ids"].append(lid)
            output["character_ids"].extend(ids)
        if output["line_ids"]:
            blocks.append(output)
    return blocks, lines, characters


def detect_regions(page, page_number, chars):
    accepted, rejected, unresolved = [], [], []
    audit_count = 0
    for index, drawing in enumerate(page.get_drawings()):
        fill = drawing.get("fill")
        if is_blue_candidate(fill):
            audit_count += 1
        if not fill or len(fill) != 3 or not (fill[2] - fill[0] > 0.15 and fill[1] > 0.35 and fill[2] > 0.45):
            continue
        rect = list(drawing["rect"])
        hits = [c for c in chars if c["text"].strip() and intersection(rect, c["bbox"])]
        record = {"region_id": f"p{page_number}_d{index}", "page": page_number, "drawing_index": index,
                  "seqno": drawing.get("seqno"), "rect": rect, "fill_rgb": list(fill),
                  "fill_opacity": drawing.get("fill_opacity"), "drawing_type": drawing["type"],
                  "path_operations": [item[0] for item in drawing["items"]], "overlapping_character_count": len(hits)}
        profile_color = max(abs(a - b) for a, b in zip(fill, PROFILE["rgb"])) <= PROFILE["rgb_tolerance"]
        rectangular = len(drawing["items"]) == 1 and drawing["items"][0][0] == "re"
        overlay = drawing["type"] == "f" and PROFILE["opacity"][0] <= (drawing.get("fill_opacity") or 0) <= PROFILE["opacity"][1]
        body = rect[1] >= 65 and rect[3] <= page.rect.height - 62
        shape = area(rect) > 0 and rect[3] - rect[1] <= PROFILE["max_rect_height_pt"] and rect[2] - rect[0] < page.rect.width * 0.85
        if profile_color and rectangular and overlay and body and shape and hits:
            record["decision"] = "accepted_text_overlay"
            accepted.append(record)
        elif overlay and profile_color:
            record["decision"] = "unresolved_overlay_geometry_or_text_overlap"
            unresolved.append(record)
        else:
            record["decision"] = "rejected_artwork_or_nonprofile_object"
            rejected.append(record)
    for char in chars:
        relevant = [r for r in accepted if intersection(char["bbox"], r["rect"])]
        cov = coverage(char["bbox"], [r["rect"] for r in relevant])
        char.update(highlight_area_fraction=round(cov, 6),
                    geometrically_highlighted=cov >= PROFILE["character_coverage_threshold"],
                    geometry_ambiguous=PROFILE["uncertain_coverage_floor"] < cov < PROFILE["character_coverage_threshold"],
                    unresolved_region_overlap=any(intersection(char["bbox"], r["rect"]) for r in unresolved),
                    region_ids=[r["region_id"] for r in relevant])
    return accepted, rejected, unresolved, audit_count


