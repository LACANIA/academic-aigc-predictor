"""Coordinate-based two-column extraction. Text/geometry only, no detector labels."""
from collections import Counter,defaultdict
from pathlib import Path
import math
import re
import statistics
import unicodedata

import pymupdf

from .audit import sha256_file

VERSION='coordinate-columns-0.1.0'
WORDS=re.compile(r'[A-Za-z]{3,}')
STOP={'the','and','for','with','this','that','from','these','which','into','here','let','both','each','their','has','are','was','will','can','not','its','all'}


def language(text):
    words=WORDS.findall(text)
    ordinary=[w for w in words if w.lower() not in {'sin','cos','max','min','sup','inf','log','det','diag','tr'}]
    return len(ordinary)>=3 or (len(ordinary)>=2 and any(w.lower() in STOP for w in ordinary))


def raw_document(path):
    pages=[];characters=[];lines=[]
    with pymupdf.open(path) as pdf:
        if pdf.needs_pass:raise ValueError('Password-protected PDF')
        report_pages=[i for i,p in enumerate(pdf) if 'AI Writing Submission' in p.get_text()]
        for body,index in enumerate(report_pages or range(len(pdf)),1):
            page=pdf[index];raw=page.get_text('rawdict');items=[]
            for bi,b in enumerate(raw['blocks']):
                if b['type']!=0:continue
                for li,l in enumerate(b['lines']):
                    ids=[];text=[];sizes=[];fonts=[];flags=[]
                    for si,s in enumerate(l['spans']):
                        for ci,c in enumerate(s['chars']):
                            cid=f'p{index+1}_b{bi}_l{li}_s{si}_c{ci}'
                            characters.append({'character_id':cid,'pdf_page':index+1,'body_page':body,'text':c['c'],
                                'bbox':list(c['bbox']),'origin':list(c['origin']),'font':s['font'],'size':s['size'],'flags':s['flags']})
                            ids.append(cid);text.append(c['c'])
                        sizes.append(s['size']);fonts.append(s['font']);flags.append(s['flags'])
                    value=''.join(text)
                    if not value.strip():continue
                    row={'line_id':f'p{index+1}_b{bi}_l{li}','pdf_page':index+1,'body_page':body,'pdf_block_index':bi,'line_index':li,
                         'bbox':list(l['bbox']),'original_text':value,'char_ids':ids,'font_size':max(sizes),
                         'font':max(zip(sizes,fonts))[1],'bold':any(f&16 for f in flags),'italic':any(f&2 for f in flags),
                         'original_order':len(lines)}
                    lines.append(row);items.append(row)
            horizontal=[]
            for drawing in page.get_drawings():
                for item in drawing['items']:
                    if item[0]=='l' and abs(item[1].y-item[2].y)<0.8 and abs(item[1].x-item[2].x)>page.rect.width*.3:
                        horizontal.append([min(item[1].x,item[2].x),item[1].y,max(item[1].x,item[2].x)])
            pages.append({'pdf_page':index+1,'body_page':body,'width':page.rect.width,'height':page.rect.height,
                          'text_layer_present':bool(items),'image_count':len(page.get_images()),'lines':items,'horizontal_rules':horizontal})
    return pages,lines,characters,bool(report_pages)


def detect_columns(pages):
    evidence=[]
    for page in pages:
        w=page['width'];left=right=0
        for l in page['lines']:
            x0,y0,x1,y1=l['bbox']
            if not language(l['original_text']) or y0<page['height']*.065 or y1>page['height']*.94 or l['font_size']<9:continue
            if x1-x0>w*.55:continue
            if x0<w*.25 and x1<w*.51:left+=1
            if x0>w*.48:right+=1
        evidence.append({'page':page['pdf_page'],'left_language_lines':left,'right_language_lines':right})
    return sum(e['left_language_lines']>=6 and e['right_language_lines']>=6 for e in evidence)>=2,evidence


def normalize_mapped(lines,char_lookup,spatial_spaces=True):
    """Same evidence-preserving normalization as precheck, plus explicit flags."""
    units=[];notes=[]
    for line in lines:
        previous=None
        for cid in line['char_ids']:
            current=char_lookup[cid]
            if spatial_spaces and previous and previous['text'].isalnum() and current['text'].isalnum():
                gap=current['bbox'][0]-previous['bbox'][2]
                threshold=.22*min(previous['size'],current['size'])
                math_to_text=bool(re.search(r'CMMI|Math',previous['font'])) and bool(re.search(r'Roman|Times',current['font']))
                if gap>threshold or (math_to_text and gap>.06*current['size']):
                    units.append((' ',None));notes.append('Word space inserted from a measurable glyph gap; original glyphs retained')
            for c in unicodedata.normalize('NFKC',current['text']):units.append((c,cid))
            previous=current
        units.append(('\n',None))
    value=''.join(c for c,i in units);remove=set()
    for m in re.finditer(r'(?<=[A-Za-z])-\s*\n\s*(?=[a-z])',value):
        remove.update(range(m.start()+1,m.end()));notes.append('Line-end hyphen retained; lexical compound vs discretionary break uncertain')
    result=[]
    for i,(c,cid) in enumerate(units):
        if i in remove:continue
        if c.isspace():
            if result and result[-1][0]!=' ':result.append((' ',None))
        else:result.append((c,cid))
    if result and result[-1][0]==' ':result.pop()
    return ''.join(c for c,i in result),[i for c,i in result],list(dict.fromkeys(notes))


def style_heading(l,body_size):
    text=l['original_text'].strip()
    named={'REFERENCES':'References','BIBLIOGRAPHY':'Bibliography','ACKNOWLEDGMENT':'Acknowledgments','ACKNOWLEDGMENTS':'Acknowledgments',
        'ACKNOWLEDGEMENTS':'Acknowledgements','APPENDIX':'Appendix','DATA AND CODE AVAILABILITY':'Data and Code Availability',
        'DATA AVAILABILITY':'Data Availability','FUNDING':'Funding','DISCLOSURES':'Disclosures'}
    if text in named and (l['bold'] or l['font_size']>=body_size):return named[text],1
    # Typeface and size are essential: a body line starting "30. Step ..." is not a heading.
    distinct=l['font_size']<=body_size*1.25 and l['font_size']>=body_size*.82 and (l['bold'] or l['italic'])
    if distinct and re.match(r'^(?:[IVXLCDM]+|[A-Z]|\d+(?:\.\d+)*)\.\s+[A-Z]',text) and len(text)<150:
        return re.sub(r'^(?:[IVXLCDM]+|[A-Z]|\d+(?:\.\d+)*)\.\s+','',text),1 if re.match(r'^[IVXLCDM]+\.',text) else 2
    if distinct and l['bold'] and text.isupper() and 2<=len(text.split())<=12 and re.fullmatch(r'[A-Z /,&-]+',text):return text,1
    return None


def mark_page(page,repeated):
    w,h=page['width'],page['height'];ls=page['lines']
    sizes=[l['font_size'] for l in ls if language(l['original_text']) and 8<l['font_size']<14]
    body=page.get('document_body_size',statistics.median(sizes) if sizes else 10)
    body_font=Counter(l['font'] for l in ls if language(l['original_text']) and abs(l['font_size']-body)<.3).most_common(1)
    body_font=body_font[0][0] if body_font else ''
    captions=[]
    keyword_blocks={l['pdf_block_index'] for l in ls if re.match(r'^(?:INDEX TERMS|KEYWORDS)\b',l['original_text'],re.I)}
    for l in ls:
        t=l['original_text'].strip();canon=re.sub(r'\d','',t).strip()
        y0,y1=l['bbox'][1],l['bbox'][3]
        l['column']='span' if l['bbox'][0]<w*.48 and l['bbox'][2]>w*.52 else ('left' if sum(l['bbox'][::2])/2<w/2 else 'right')
        l['role']='body';l['heading_info']=None
        if (y0<h*.065 or y1>h*.94) and (canon in repeated or re.fullmatch(r'\d+',t)):
            l['role']='page_header' if y0<h*.065 else 'page_footer';continue
        if l['pdf_block_index'] in keyword_blocks:l['role']='metadata';continue
        if re.match(r'^(?:FIG(?:URE)?\.?|TABLE|ALGORITHM)\s+\d+[.:]',t,re.I):
            l['role']='caption';captions.append(l)
        else:
            proposed=style_heading(l,body)
            # Section text aligns with a column margin; plot legends float inside it.
            margin=page.get('column_margins',[w*.063,w*.517])[0 if l['column']=='left' else 1]
            if proposed and l['column']!='span' and abs(l['bbox'][0]-margin)>20:proposed=None
            if proposed and page.get('heading_fonts') and l['font'] not in page['heading_fonts']:proposed=None
            l['heading_info']=proposed
    caption_blocks={l['pdf_block_index'] for l in captions}
    heading_blocks={l['pdf_block_index'] for l in ls if l['heading_info']}
    for l in ls:
        if l['role']=='body' and l['pdf_block_index'] in caption_blocks and l['font_size']<body*.96:l['role']='caption'
    regions=[]
    for cap in captions:
        if not re.match(r'^(?:TABLE|ALGORITHM)\b',cap['original_text'],re.I):continue
        y=cap['bbox'][3]
        next_cap=min([c['bbox'][1] for c in captions if c['bbox'][1]>y]+[h*.94])
        body_next=min([l['bbox'][1] for l in ls if l['bbox'][1]>y+3 and l['font_size']>=body*.97 and l['role']=='body']+[next_cap])
        limit=min(next_cap,body_next)
        rules=[r for r in page['horizontal_rules'] if y-1<=r[1]<limit]
        if len(rules)>=2:
            top=min(r[1] for r in rules);bottom=max(r[1] for r in rules)
            if top-y<40 and bottom-top>10:regions.append({'bbox':[min(r[0] for r in rules),top-1,max(r[2] for r in rules),bottom+2],
                'kind':'algorithm' if cap['original_text'].lower().startswith('algorithm') else 'table'})
    for l in ls:
        if l['role']!='body':continue
        x,y=(l['bbox'][0]+l['bbox'][2])/2,(l['bbox'][1]+l['bbox'][3])/2
        region=next((r for r in regions if r['bbox'][0]-2<=x<=r['bbox'][2]+2 and r['bbox'][1]<=y<=r['bbox'][3]),None)
        if region:l['role']=region['kind'];l['column']='span';l['heading_info']=None
        elif l['font']!=body_font and not l['heading_info'] and l['font_size']<=body and 'Times' not in l['font'] and not re.match(r'CM|TeX',l['font']):
            if not (l['pdf_block_index'] in heading_blocks and l['original_text'].isupper() and (l['bold'] or l['italic'])):l['role']='figure_text'
    page['body_font_size']=body;page['regions']=regions
    page['language_blocks']=sorted({l['pdf_block_index'] for l in ls if l['role']=='body' and not l['heading_info'] and language(l['original_text'])})
    return page


def order_page(page):
    """Full-width bands are barriers; within each open band read left then right."""
    margins=[l for l in page['lines'] if l['role'] in {'page_header','page_footer'}]
    content=[l for l in page['lines'] if l not in margins]
    barriers=[r['bbox'][1::2] for r in page['regions']]
    span_blocks=defaultdict(list)
    for l in content:
        if l['column']=='span':span_blocks[l['pdf_block_index']].append(l)
    for group in span_blocks.values():barriers.append([min(l['bbox'][1] for l in group),max(l['bbox'][3] for l in group)])
    bands=[]
    for a,b in sorted(barriers):
        if bands and a<=bands[-1][1]+2:bands[-1][1]=max(b,bands[-1][1])
        else:bands.append([a,b])
    output=sorted([l for l in margins if l['role']=='page_header'],key=lambda l:l['bbox'][1]);remaining=content[:]
    def ordinary(group):return sorted(group,key=lambda l:(0 if l['column']=='left' else 1,l['bbox'][1],l['pdf_block_index'],l['line_index']))
    for band_index,(a,b) in enumerate(bands):
        before=[l for l in remaining if (l['bbox'][1]+l['bbox'][3])/2<a]
        for l in before:l['layout_band']=f'body-{band_index}'
        output+=ordinary(before);remaining=[l for l in remaining if l not in before]
        within=[l for l in remaining if (l['bbox'][1]+l['bbox'][3])/2<=b]
        for l in within:l['layout_band']=f'span-{band_index}'
        output+=sorted(within,key=lambda l:(l['pdf_block_index'],l['line_index']))
        remaining=[l for l in remaining if l not in within]
    for l in remaining:l['layout_band']=f'body-{len(bands)}'
    for l in margins:l['layout_band']='margin'
    output+=ordinary(remaining)
    output+=sorted([l for l in margins if l['role']=='page_footer'],key=lambda l:l['bbox'][1])
    return output


def extract_layout(path,key,force=False):
    pages,lines,chars,is_report=raw_document(path);detected,evidence=detect_columns(pages)
    if not detected and not force:return None
    counts=Counter()
    for page in pages:
        seen=set()
        for l in page['lines']:
            if l['bbox'][1]<page['height']*.065 or l['bbox'][3]>page['height']*.94:
                seen.add(re.sub(r'\d','',l['original_text']).strip())
        counts.update(seen)
    repeated={k for k,v in counts.items() if v>=2 and k}
    sizes=[l['font_size'] for l in lines if language(l['original_text']) and 8<l['font_size']<14]
    body_size=statistics.median(sizes) if sizes else 10
    heading_fonts={l['font'] for l in lines if re.match(r'^(?:[IVXLCDM]+|[A-Z]|\d+)\.\s+[A-Z]',l['original_text'])
                   and (l['bold'] or l['italic']) and l['original_text'].isupper() and body_size*.82<=l['font_size']<=body_size*1.25}
    left=[l['bbox'][0] for p in pages for l in p['lines'] if language(l['original_text']) and abs(l['font_size']-body_size)<.3 and l['bbox'][0]<p['width']*.25 and l['bbox'][2]<p['width']*.51]
    right=[l['bbox'][0] for p in pages for l in p['lines'] if language(l['original_text']) and abs(l['font_size']-body_size)<.3 and l['bbox'][0]>p['width']*.48]
    ordered=[]
    for page in pages:
        page['document_body_size']=body_size
        page['heading_fonts']=sorted(heading_fonts)
        page['column_margins']=[statistics.median(left) if left else page['width']*.063,statistics.median(right) if right else page['width']*.517]
        ordered+=order_page(mark_page(page,repeated))
    language_blocks={(p['pdf_page'],b) for p in pages for b in p['language_blocks']}
    lookup={c['character_id']:c for c in chars};records=[];section='Preliminaries';main='Preliminaries';title=None;refs=False;bio=False
    for line in ordered:
        text=line['original_text'].strip();role=line['role'];heading=line['heading_info'] if role=='body' else None
        continuation=(role=='body' and records and records[-1]['role']=='heading' and text.isupper()
            and line['pdf_block_index']==records[-1]['pdf_block_index'] and line['pdf_page']==records[-1]['pdf_page']
            and line['font_size']<11 and (line['bold'] or line['italic']) and not re.match(r'^(?:[IVXLCDM]+|[A-Z]|\d+)\.\s',text))
        if continuation:
            records[-1]['_lines'].append(line);section=records[-1]['section']+' '+text;records[-1]['section']=section
            if main==records[-1].get('_old_heading'):main=section;records[-1]['main_section']=section
            continue
        if heading:
            section,level=heading
            if level==1:main=section
            refs=section in {'References','Bibliography'};bio=False;role='heading'
        elif role=='body':
            if re.match(r'^ABSTRACT(?:\s|:)',text,re.I):section=main='Abstract';role='prose'
            elif re.match(r'^(?:INDEX TERMS|KEYWORDS)\b',text,re.I):role='metadata'
            elif refs and re.match(r"^[A-Z][A-Z .'-]{2,}\s+(?:is|received|was)\b",text):refs=False;bio=True;section=main='Author Biographies';role='biography'
            elif bio:role='biography'
            elif refs:role='references'
            elif line['font_size']>16 and language(text) and (title is None or (records and records[-1]['role']=='title' and records[-1]['pdf_block_index']==line['pdf_block_index'])):
                title=(title+' '+text) if title else text;role='title'
            elif main=='Preliminaries' and line['body_page']==1:role='metadata'
            else:
                tail=(line['pdf_page'],line['pdf_block_index']) in language_blocks and bool(re.fullmatch(r"[A-Za-z][A-Za-z ,;:'’().-]*",text)) and bool(WORDS.search(text))
                role='prose' if language(text) or tail else 'formula'
        elif role=='algorithm':role='algorithm_prose'
        elif role=='figure_text' and main=='Preliminaries' and line['body_page']==1:
            role='metadata'
        group=None
        if records:
            prev=records[-1]
            compatible=role==prev['role'] or (role in {'prose','formula'} and prev['role'] in {'prose','formula','mixed_math_prose'} and (role=='prose' or prev['role']!='formula'))
            if compatible and section==prev['section'] and role!='heading' and line['pdf_page']==prev['pdf_page'] and line['pdf_block_index']==prev['pdf_block_index'] and line['column']==prev['column']:
                group=prev
                if role!=prev['role']:prev['role']='mixed_math_prose'
        if group:group['_lines'].append(line)
        else:records.append({'pdf_page':line['pdf_page'],'body_page':line['body_page'],'pdf_block_index':line['pdf_block_index'],
            'column':line['column'],'section':section,'main_section':main,'role':role,'_lines':[line],'_old_heading':section})
    # Restore cross-column/page continuations only when both language and boundary evidence support them.
    joined=[]
    for r in records:
        if r['role'] in {'page_header','page_footer'}:joined.append(r);continue
        previous=next((x for x in reversed(joined) if x['role'] not in {'page_header','page_footer'}),None)
        # A floating figure/table may precede a lowercase continuation on the next page.
        # Skip it only for a visible line-end hyphen, never on subject-matter similarity.
        if r['role']=='prose' and r['_lines'][0]['original_text'].strip()[:1].islower():
            for candidate in reversed(joined):
                if candidate['role'] in {'page_header','page_footer','caption','table','figure_text','formula'}:continue
                if (candidate['role']=='prose' and candidate['section']==r['section']
                    and candidate['_lines'][-1]['pdf_page']!=r['pdf_page']
                    and candidate['_lines'][-1]['original_text'].strip().endswith('-')):previous=candidate
                break
        if previous and r['role'] in {'prose','biography'} and previous['role']==r['role'] and previous['section']==r['section']:
            end=previous['_lines'][-1]['original_text'].strip();start=r['_lines'][0]['original_text'].strip()
            boundary=(previous['_lines'][-1]['pdf_page']!=r['pdf_page'] or previous['_lines'][-1]['column']!=r['column'])
            if boundary and end and not re.search(r'[.!?□]$',end) and not re.match(r'^(?:\d+\)|[IVX]+\.)',start):
                previous['_lines']+=r['_lines'];continue
        joined.append(r)
    paragraphs=[]
    for i,r in enumerate(joined,1):
        group=r.pop('_lines');text,mapping,notes=normalize_mapped(group,lookup)
        r.pop('_old_heading',None)
        candidate=r['role'] in {'prose','mixed_math_prose','algorithm_prose','biography'}
        r.update(paragraph_id=f'{key}_l{i:04d}',original_text='\n'.join(l['original_text'] for l in group),normalized_text=text,
            normalized_char_ids=mapping,source_line_ids=[l['line_id'] for l in group],source_pages=sorted({l['pdf_page'] for l in group}),
            line_evidence=[{k:l[k] for k in ['bbox','original_text','line_index','pdf_page','pdf_block_index','column','layout_band','line_id','char_ids']} for l in group],
            word_count=len(re.findall(r"[A-Za-z]+(?:[-’'][A-Za-z]+)*",text)),analysis_candidate=candidate,
            eligibility='candidate_not_officially_confirmed' if candidate else 'separate_scope_unconfirmed',
            normalization_notes=['Whitespace/NFKC; raw glyphs and coordinates retained']+notes,layout_locked=True)
        r['alternative_dehyphenated_text']=re.sub(r'(?<=[A-Za-z])-\s*\n\s*(?=[a-z])','',r['original_text']) if any('hyphen' in n for n in notes) else None
        r['alternative_note']='Optional reading alternative only; lexical compounds can be damaged, so canonical evidence retains the hyphen.' if r['alternative_dehyphenated_text'] else None
        paragraphs.append(r)
    return {'source_path':str(Path(path).resolve()),'source_hash':sha256_file(Path(path)),'source_kind':'report_embedded_body' if is_report else 'standalone_pdf',
        'protocol_version':'precheck-0.1.0','document_key':key,'layout_strategy':VERSION,'title':title,
        'pages':[{k:v for k,v in p.items() if k not in {'lines','horizontal_rules'}} for p in pages],
        'paragraphs':paragraphs,'source_lines':lines,'characters':chars,'column_detection_evidence':evidence,
        'analysis_candidate_count':sum(p['analysis_candidate'] for p in paragraphs),'analysis_word_count':sum(p['word_count'] for p in paragraphs if p['analysis_candidate'])}


