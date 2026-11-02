"""STEP-03 context-and-case-based detector behavior protocol, no model API."""

from collections import Counter
import difflib
import json
from pathlib import Path
import re

import pymupdf

from .audit import sha256_file
from .highlights import detect_regions, extract_page_text
from .precheck import canonical_hash, normalized, preprocess_pdf

VERSION='behavior-0.1.0'
RULE_IDS={f'R{i:02d}' for i in range(1,8)}
DECLARATIONS={'Funding','Disclosures','Data Availability','AI-assisted preparation','Acknowledgments','Acknowledgements'}


def rule_cards(markdown):
    """Export hypotheses/limits, not the per-case observations in the audit file."""
    cards=[]
    names={'定义':'definition','适用条件':'conditions','可能反例':'counterexamples','证据强度':'evidence_strength','新论文假设':'hypothesis'}
    for match in re.finditer(r'## (R\d{2}) ([^\n]+)\n(.*?)(?=\n## |\Z)',markdown,re.S):
        rid,title,body=match.groups()
        card={'rule_id':rid,'title':title,'evidence_scope':'One development family; per-case observed labels withheld from this rule card'}
        for line in body.splitlines():
            found=re.match(r'- ([^：]+)：(.+)',line)
            if found and found.group(1) in names:
                value=re.sub(r'E\d{2}(?:/E\d{2})?', '',found.group(2))
                card[names[found.group(1)]]=value
        cards.append(card)
    return cards

def candidates(prepared):
    return [p for p in prepared['paragraphs'] if p['analysis_candidate'] or (p['section'] in DECLARATIONS and p['role'] not in {'heading','metadata'} and p['normalized_text'])]

def history_context(path,key,include_uncertainty=False):
    old=preprocess_pdf(path,key)
    if old['source_kind']!='report_embedded_body':
        raise ValueError('Historical weak labels require an AI Writing report body, not a plain paper PDF')
    labels={}
    # This is known-template paragraph geometry, not a generic official sentence labeler.
    with pymupdf.open(path) as pdf:
        cache={}
        for p in candidates(old):
            page_number=p['pdf_page']
            if page_number not in cache:
                page=pdf[page_number-1]
                _,_,chars=extract_page_text(page,page_number)
                detect_regions(page,page_number,chars)
                cache[page_number]=chars
            boxes=[l['bbox'] for l in p['line_evidence']]
            chosen=[c for c in cache[page_number] if c['text'].strip() and any(r[0]<=sum(c['bbox'][::2])/2<=r[2] and r[1]<=sum(c['bbox'][1::2])/2<=r[3] for r in boxes)]
            labels[p['paragraph_id']]={'highlighted_character_fraction':sum(c['geometrically_highlighted'] for c in chosen)/len(chosen) if chosen else None,
                                       'label_source':'historical_report_geometry_weak_label','character_count':len(chosen)}
            if include_uncertainty:
                h=sum(c['geometrically_highlighted'] for c in chosen)
                ambiguous=sum(c['geometry_ambiguous'] or c['unresolved_region_overlap'] for c in chosen)
                labels[p['paragraph_id']].update(ambiguous_character_count=ambiguous,
                    state='geometry_uncertain' if not chosen or ambiguous else 'unmarked' if not h else 'highlighted' if h==len(chosen) else 'partial')
    return old,labels

def align_history(new_paragraphs,old,labels):
    output=[]
    old_paragraphs=candidates(old)
    for new in new_paragraphs:
        matches=[]
        for p in old_paragraphs:
            similarity=difflib.SequenceMatcher(None,new['normalized_text'],p['normalized_text'],autojunk=False).ratio()
            matches.append((similarity,p))
        score,previous=max(matches,key=lambda x:x[0])
        if score<0.35:
            output.append({'paragraph_id':new['paragraph_id'],'change_type':'no_reliable_lexical_match','old_paragraph_id':None})
        else:
            output.append({'paragraph_id':new['paragraph_id'],'old_paragraph_id':previous['paragraph_id'],
                           'old_text':previous['normalized_text'],'lexical_similarity':round(score,6),
                           'change_type':'identical' if score==1 else 'modified_candidate',
                           'old_geometry':labels[previous['paragraph_id']],
                           'warning':'Lexical best match may be ambiguous; old labels never become new official labels.'})
    return output
