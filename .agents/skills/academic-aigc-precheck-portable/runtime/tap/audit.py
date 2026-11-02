from __future__ import annotations
from pathlib import Path
from collections import Counter
import hashlib,re
import pymupdf

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def is_blue_candidate(fill: tuple | None) -> bool:
    """Broad RGB cyan screening, not a detector-specific highlight classifier."""
    if fill is None or len(fill) != 3:
        return False
    red, green, blue = fill
    return 0.15 <= red <= 0.65 and 0.60 <= green <= 0.92 and 0.70 <= blue <= 1 and blue - red >= 0.2

def overview_observation(text: str, page: int) -> dict | None:
    """Accept an explicit AI overview; do not infer a score from a filename."""
    if "AI Writing Overview" not in text:
        return None
    match = re.search(r"(?<![\d.])(100|[1-9]?\d|\*)%\s+detected as AI", text)
    if not match:
        return None
    display = match.group(1)
    return {
        "observed_score": None if display == "*" else int(display),
        "score_kind": "suppressed" if display == "*" else "exact_percent",
        "display_value": display + "%",
        "score_source_page": page,
        "label_source": "official_report_observation",
        "evidence": match.group(0),
    }

def audit_pdf(path: Path) -> dict:
    path = path.resolve()
    record = {"path": str(path), "name": path.name, "format": "pdf", "status": "error"}
    if not path.is_file():
        record["error"] = "File not found"
        return record
    record.update(size_bytes=path.stat().st_size, file_hash=sha256_file(path), hash_algorithm="sha256")
    try:
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass:
                record["error"] = "Encrypted PDF requires password; contents not inspected"
                return record
            texts = [page.get_text() for page in pdf]
            cover = texts[0] if texts else ""
            report = "Submission ID" in cover and any("AI Writing Overview" in t for t in texts[:2])
            observations = [o for i, t in enumerate(texts[:2], 1) if (o := overview_observation(t, i))] if report else []
            candidates = []
            colors = Counter()
            annotation_count = 0
            for i, page in enumerate(pdf, 1):
                annotation_count += sum(1 for _ in (page.annots() or []))
                # Exclude cover/overview: their blue design elements are not body highlights.
                if not report or "AI Writing Submission" not in texts[i - 1]:
                    continue
                count = 0
                for drawing in page.get_drawings():
                    fill = drawing.get("fill")
                    if is_blue_candidate(fill):
                        count += 1
                        colors[tuple(round(v, 6) for v in fill)] += 1
                if count:
                    candidates.append({"report_page": i, "candidate_drawing_count": count})
            raw_date = re.search(r"Submission Date\s*\n([^\n]+)", cover)
            submission = re.search(r"trn:oid:::[^\s]+", cover)
            record.update(
                status="ok", page_count=len(pdf),
                asset_kind="turnitin_ai_report" if report else "other_pdf",
                pages_with_extractable_text=sum(bool(t.strip()) for t in texts),
                extractable_character_count=sum(len(t.strip()) for t in texts),
                has_extractable_text=any(t.strip() for t in texts),
                text_layer_check="Nonempty get_text output; not a reading-order or OCR accuracy check",
                detector_name="Turnitin" if report else None,
                submission_id=submission.group(0) if submission and report else None,
                detection_date_raw=raw_date.group(1) if raw_date and report else None,
                detection_date_semantics="submission_time_proxy; actual model execution time not shown" if report else None,
                overview_observations=observations,
                annotation_count=annotation_count,
                blue_marker_audit={
                    "status": "candidate_vectors_found" if candidates else ("none_found_by_vector_check" if report else "not_applicable"),
                    "pages": candidates,
                    "candidate_drawing_count": sum(x["candidate_drawing_count"] for x in candidates),
                    "fill_colors": [{"rgb": list(color), "drawing_count": count} for color, count in colors.items()],
                    "limitation": "Vector candidates only; may include figure artwork. Not semantic labels, spans, or sentence counts. Raster highlights not assessed.",
                },
            )
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record
