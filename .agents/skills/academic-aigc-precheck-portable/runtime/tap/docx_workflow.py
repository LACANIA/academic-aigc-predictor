"""Additive RC1-DOCX adapter; frozen RC1 prediction/geometry code is reused."""
import json
from pathlib import Path
import pymupdf
from .docx_source import Reader
from . import practical,practical_workflow as rc
from .behavior import rule_cards,history_context,align_history
from .contrastive import select_cases,case_card
from .precheck import canonical_hash
from .audit import overview_observation
from .knowledge import load

RELEASE='academic-aigc-precheck RC1-DOCX'

def history_title_check(title,old,path):
    if practical.tokens(old['title'] or '')==practical.tokens(title or ''):
        return {'status':'MATCH','method':'RC1_normalized_title'}
    # A report-body margin crop may truncate a title. Read only the registered
    # first body page's leading text, never guess from a filename or score.
    pages=[b['pdf_page'] for b in old.get('paragraphs',[]) if b.get('pdf_page')]
    if title and pages and min(pages)>=3:
        page=min(pages)
        with pymupdf.open(path) as pdf:
            text=pdf[page-1].get_text(sort=True)[:1600]
        needle=' '.join(practical.tokens(title));hay=' '.join(practical.tokens(text))
        if needle and hay.count(needle)==1:
            return {'status':'MATCH_WITH_LIMITATIONS','method':'unique_full_title_in_registered_first_body_page',
               'report_page':page,'old_parser_title':old['title'],
               'limitation':'Repair of identity text extraction only; not full version identity or label inheritance.'}
    raise ValueError('HISTORY_IDENTITY_MISMATCH: title/family association not established')

def prepare(root,pdf=None,tex=None,family=None,history=None,threshold=None,docx=None):
    if bool(pdf)==bool(docx):raise ValueError('Supply exactly one of --pdf or --docx')
    if docx and tex:raise ValueError('--tex requires --pdf; DOCX+TeX not supported')
    if pdf:return rc.prepare(root,pdf,tex,family,history,threshold)
    if threshold is not None and (isinstance(threshold,bool) or not 0<=threshold<=100):raise ValueError('Threshold must be between0 and100')
    d=Reader(docx).read();root=Path(root)
    known=next((f for t,f in load(root)['known_titles'].items() if practical.tokens(t)==practical.tokens(d['title'] or '')),None)
    if known and family and known!=family:raise ValueError('Target family conflicts with known title identity')
    family=known or family
    if not family:raise ValueError('Confirm the target family and supply --family before using cases')
    cases=load(root)['cases']
    p={'protocol_version':practical.VERSION,'release':RELEASE,'document_id':'docx_'+d['source_hash'][:12],
       'input_mode':'DOCX','mode':'new_paper','title':d['title'],'target_family':family,
       'known_development_source':bool(known),'source_hashes':{'docx':d['source_hash']},
       'version_status':'DOCX_ONLY_NO_PDF_CROSSCHECK','blocks':d['blocks'],
       'input_files':{'docx':Path(docx).name},'decision_threshold':threshold,
       'coverage':{'body_candidate_blocks':sum(b['analysis_scope']=='body_candidate' for b in d['blocks']),
         'body_candidate_lexical_tokens':sum(len(practical.tokens(b['text'])) for b in d['blocks'] if b['analysis_scope']=='body_candidate'),
         'body_pdf_match_recall':None,'denominator':'Local narrative candidates; not official eligible text, sentences or document words.'},
       'input_limitations':d['warnings']+['Math reading hints are not certified equivalence; body paragraphs, formulas, tables and statements retain distinct eligibility.'],
       'rule_cards':rule_cards(load(root)['rules_text']),
       'historical_cases':[case_card(c) for c in select_cases(cases,family,d['source_hash'],'new_paper')],
       'family_reference_policy':'Target family/hash excluded in new_paper. Only explicit user report allowed in history_diff.',
       'math_context':[ {k:v for k,v in m.items() if k!='omml_xml'} for m in d['math_objects']],
       'table_structure':d['tables']}
    private={'docx':d,'pdf':None,'tex':None,'version_audit':{'status':p['version_status'],'limitations':p['input_limitations']},'target_family':family}
    if history:
        if not Path(history).is_file():raise FileNotFoundError('Missing explicitly supplied history: '+str(history))
        old,labels=history_context(Path(history),'history',include_uncertainty=True)
        identity=history_title_check(p['title'],old,history)
        selected=[c for c in cases if c['evidence']['report_sha256']==old['source_hash']]
        if any(c['family_id']!=family for c in selected):raise ValueError('HISTORY_IDENTITY_MISMATCH: known report family differs')
        with pymupdf.open(history) as pdfdoc:
            observations=[o for i in range(min(2,len(pdfdoc))) if (o:=overview_observation(pdfdoc[i].get_text(),i+1))]
        if len(observations)!=1:raise ValueError('Historical official observation missing or ambiguous')
        p.update(mode='history_diff',history_reference_authorized=True,
          historical_baseline=dict(observations[0],report_sha256=old['source_hash']),
          historical_cases=[case_card(c) for c in selected],
          history_blocks=[{'old_id':b['paragraph_id'],'page':b['pdf_page'],'section':b['section'],'text':b['normalized_text'],
             'old_geometry_weak_label':labels.get(b['paragraph_id'])} for b in old['paragraphs']],
          historical_alignment=align_history([{'paragraph_id':b['paragraph_id'],'normalized_text':b['text']} for b in d['blocks'] if b['analysis_scope']=='body_candidate'],old,labels))
        p['input_files']['history']=Path(history).name
        p['input_limitations']+=['Title equality is family evidence only. Lexical best-match alignment and historical geometry never become new labels.']
        private['history']={'source_path':str(Path(history).resolve()),'old':old,'labels':labels,'identity_check':identity}
    p['packet_hash']=canonical_hash(p);private['packet']=p
    return private,p

def readable(packet):
    text=practical.readable(packet)
    if packet['input_mode']!='DOCX':return text
    # Existing paragraph IDs remain quote targets; formulas/tables are contextual evidence.
    text+='\n\n## OMML reading hints (not certified equivalence)\n'
    for m in packet['math_context']:text+='\n'+m['math_id']+' | '+m['block_id']+' | '+m['readable_text']+'\n'
    text+='\nDOCX locations are paragraph indices; empty PDF pages mean unavailable, never page zero.\n'
    return text

def report(packet,result):
    text=rc.report(packet,result)
    if result.get('engineering_replay'):
        text='# 旧预测输出工程回放\n\n本报告仅重渲染已冻结的旧预测；没有新的宿主预测，也不评价新输入适配的检测准确性。\n\n'+text
    if packet['input_mode']!='DOCX':return text
    blocks={b['paragraph_id']:b for b in packet['blocks']}
    for r in result.get('likely_highlights',[]):
        b=blocks[r['paragraph_id']]
        text=text.replace('来源：'+b['source_file']+'；PDF页[]。',
          '来源：'+b['source_file']+'；OOXML段落 '+str(b['paragraph_index'])+'（'+b['block_id']+'），'+b['source_part']+'；无可靠PDF页码。',1)
    return text+'\n候选版本：RC1-DOCX；仅扩展输入，沿用 practical-whole-document-0.1.0。\n'
