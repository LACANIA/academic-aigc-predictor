"""Provider-neutral preprocessing and evidence validation for a host-LLM skill.

No detector scores, drawings, network clients, or model SDKs are read here.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import re
import statistics
import unicodedata

import pymupdf

from .audit import sha256_file

PROTOCOL_VERSION = "precheck-0.1.0"
RISK_LEVELS = {"low", "moderate", "high", "unable_to_judge"}
FACTOR_NAMES = {"disciplinary_convention", "repetition", "unsupported_generalization", "technical_argument", "historical_hypothesis"}
NAMED_HEADINGS = {s.casefold():s for s in ["Abstract", "References", "Bibliography", "Acknowledgments", "Acknowledgements", "Funding", "Disclosures", "Data Availability", "AI-assisted preparation"]}
POST_REFERENCE_HEADINGS = {s.casefold() for s in ["Acknowledgments", "Acknowledgements", "Funding", "Disclosures", "Data Availability", "AI-assisted preparation"]}


def normalized(text):
    # Preserve lexical hyphens; their discretionary/semantic status is unknown.
    text = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "-", text)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def word_count(text):
    return len(re.findall(r"[A-Za-z]+(?:[-’'][A-Za-z]+)*", text))


def canonical_hash(value):
    import json
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _is_caption(text):
    # "Figure 2 summarizes ..." is body prose, unlike "Fig. 2. Mechanisms ...".
    return bool(re.match(r"^(?:Fig\.|Figure|Table)\s*\d+[.:]", text, re.I))


def _heading(text, bold=False):
    text = normalized(text)
    if text.casefold() in NAMED_HEADINGS:
        return NAMED_HEADINGS[text.casefold()]
    roman = re.match(r"^[IVXLCDM]+\.\s+([A-Z][A-Za-z ,/&-]+)$", text)
    if roman and word_count(roman.group(1)) <= 12:
        return roman.group(1)
    if len(text) < 130 and re.match(r"^(?:\d+(?:\.\d+)*\.?|[A-Z]\.)\s+[A-Z]", text) and not re.search(r"[;=≤≥]", text):
        return re.sub(r"^(?:\d+(?:\.\d+)*\.?|[A-Z]\.)\s+", "", text)
    if bold and 2 <= word_count(text) <= 9 and len(text) < 90 and not text.isupper() and re.fullmatch(r"[A-Z][A-Za-z -]+", text):
        return text
    return None


def preprocess_pdf(path: Path, document_key: str, layout_mode='auto'):
    path = Path(path)
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", document_key):
        raise ValueError("document_key must be an opaque alphanumeric ID")
    if layout_mode not in {'auto','legacy','columns'}:
        raise ValueError('Unknown layout mode')
    if layout_mode!='legacy':
        from .layout import extract_layout
        data=extract_layout(path,document_key,force=layout_mode=='columns')
        if data is not None:
            selected=[p for p in data['paragraphs'] if p['analysis_candidate']]
            if not selected:raise ValueError('No continuous English prose candidates')
            packet={'protocol_version':PROTOCOL_VERSION,'document_key':document_key,'title':data['title'],
                'body_page_count':len(data['pages']),
                'paragraphs':[{k:p[k] for k in ['paragraph_id','body_page','section','role','normalized_text','word_count']} for p in selected],
                'excluded_summary':dict(Counter(p['role'] for p in data['paragraphs'] if not p['analysis_candidate'])),
                'eligibility_notice':'Coordinate-ordered prose, algorithm language and biographies are provisional; table/formula/figure text remains separately preserved.'}
            data['model_packet']=packet;data['packet_hash']=canonical_hash(packet)
            return data
    paragraphs, pages = [], []
    section, title = "Preliminaries", None
    with pymupdf.open(path) as pdf:
        if pdf.needs_pass:
            raise ValueError("Password-protected PDF; no extraction performed")
        report_body = [i for i, p in enumerate(pdf) if "AI Writing Submission" in p.get_text()]
        target_pages = report_body or list(range(len(pdf)))
        for body_page, index in enumerate(target_pages, 1):
            page = pdf[index]
            raw = page.get_text("dict")
            sizes = [s["size"] for b in raw["blocks"] if b["type"] == 0 for l in b["lines"] for s in l["spans"] if word_count(s["text"]) > 2]
            median_size = statistics.median(sizes) if sizes else 10
            page_paragraphs = []
            for bi, block in enumerate(raw["blocks"]):
                if block["type"] != 0:
                    continue
                lines = []
                for li, line in enumerate(block["lines"]):
                    if report_body and (line["bbox"][1] < 65 or line["bbox"][3] > page.rect.height - 62):
                        continue
                    text = "".join(s["text"] for s in line["spans"])
                    if not text.strip():
                        continue
                    bold = any("Bold" in s["font"] or s["flags"] & 16 for s in line["spans"])
                    lines.append({"original_text": text, "bbox": list(line["bbox"]), "line_index": li,
                                  "bold": bold, "max_font_size": max(s["size"] for s in line["spans"])})
                # A single PDF block can contain References and every entry.
                # Split explicit standalone headings even inside such blocks.
                segments, current = [], []
                in_references = section in {"References", "Bibliography"}
                for line in lines:
                    standalone = None if line["max_font_size"] > median_size * 1.3 else _heading(line["original_text"], line["bold"])
                    if in_references and normalized(line["original_text"]).casefold() not in POST_REFERENCE_HEADINGS:
                        standalone = None
                    if standalone:
                        if current:
                            segments.append(current); current = []
                        segments.append([line])
                        in_references = standalone in {"References", "Bibliography"}
                    else:
                        current.append(line)
                if current:
                    segments.append(current)
                for segment in segments:
                    text = "\n".join(l["original_text"] for l in segment)
                    norm = normalized(text)
                    heading = _heading(text, len(segment) == 1 and segment[0]["bold"])
                    if section in {"References", "Bibliography"} and norm.casefold() not in POST_REFERENCE_HEADINGS:
                        heading = None
                    if heading:
                        section = heading
                        role = "heading"
                    elif re.match(r"^Abstract(?:\s*:|\s+)", norm, re.I):
                        section, role = "Abstract", "prose"
                    elif re.match(r"^(?:Index Terms|Keywords)\b", norm, re.I):
                        role = "metadata"
                    elif section in {"References", "Bibliography"}:
                        role = "references"
                    elif not title and max(l["max_font_size"] for l in segment) > median_size * 1.3 and word_count(text) > 5:
                        title, role = norm, "title"
                    elif section == "Preliminaries" and body_page == 1:
                        role = "metadata"
                    elif _is_caption(norm):
                        role = "caption"
                    elif word_count(text) < 12:
                        role = "formula_table_or_short_fragment"
                    elif sum(c in "=≤≥∑∫√∥" for c in text) >= 3:
                        role = "mixed_math_prose"
                    else:
                        role = "prose"
                    eligible = role in {"prose", "mixed_math_prose"}
                    # References/heading cuts are text evidence, not hidden labels.
                    record = {
                        "paragraph_id": f'{document_key}_p{body_page:02d}_{len(page_paragraphs)+1:03d}',
                        "body_page": body_page, "pdf_page": index+1, "pdf_block_index": bi,
                        "section": section, "role": role, "analysis_candidate": eligible,
                        "eligibility": "candidate_not_officially_confirmed" if eligible else "excluded_or_uncertain",
                        "original_text": text, "normalized_text": norm, "word_count": word_count(norm),
                        "line_evidence": [{"bbox": l["bbox"], "original_text": l["original_text"], "line_index": l["line_index"]} for l in segment],
                        "normalization_notes": ["Whitespace collapsed; Unicode NFKC; line-end lexical hyphens retained"],
                    }
                    page_paragraphs.append(record)
            paragraphs.extend(page_paragraphs)
            pages.append({"body_page": body_page, "pdf_page": index+1, "width": page.rect.width, "height": page.rect.height,
                          "text_layer_present": bool(page_paragraphs), "image_count": len(page.get_images())})
    candidates = [p for p in paragraphs if p["analysis_candidate"]]
    # Model-facing packet deliberately omits path/hash/cover/score/highlight data.
    packet = {"protocol_version": PROTOCOL_VERSION, "document_key": document_key, "title": title,
              "body_page_count": len(pages),
              "paragraphs": [{k: p[k] for k in ["paragraph_id", "body_page", "section", "role", "normalized_text", "word_count"]} for p in candidates],
              "excluded_summary": dict(Counter(p["role"] for p in paragraphs if not p["analysis_candidate"])),
              "eligibility_notice": "Local prose candidates, not the detector's confirmed denominator; math fragments and captions may be excluded."}
    if not candidates:
        raise ValueError("No continuous English prose candidates; no model or OCR invoked")
    return {"protocol_version": PROTOCOL_VERSION, "document_key": document_key, "source_path": str(path.resolve()),
            "source_hash": sha256_file(path), "source_kind": "report_embedded_body" if report_body else "standalone_pdf",
            "title": title, "pages": pages, "paragraphs": paragraphs,
            "analysis_candidate_count": len(candidates), "analysis_word_count": sum(p["word_count"] for p in candidates),
            "model_packet": packet, "packet_hash": canonical_hash(packet)}


