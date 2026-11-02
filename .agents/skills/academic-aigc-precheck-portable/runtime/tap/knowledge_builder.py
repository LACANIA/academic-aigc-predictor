"""Local, reviewed reference construction. No model training, uploads or directory search."""
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
import difflib,hashlib,json,os,re,tempfile,datetime
import pymupdf
from .precheck import preprocess_pdf,canonical_hash
from .practical import tokens,crosscheck
from .docx_source import Reader as DocxReader
from .tex_source import Reader as TexReader
from .highlights import extract_page_text,detect_regions,PROFILE
from .knowledge import load,digest

VERSION='local-knowledge-0.1.0'
SKILL=Path(__file__).resolve().parents[2]
PUBLIC_RULES=SKILL/'references/turnitin-behavior-rules.md'
LABELS={'highlighted','unmarked','partial','uncertain'}
MAX_SOURCE_BYTES=64*1024*1024

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(path,limit=32*1024*1024):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>limit:raise ValueError('KB_RESOURCE: missing or oversized '+str(p))
    try:return json.loads(p.read_text(encoding='utf-8-sig'))
    except (UnicodeError,json.JSONDecodeError) as e:raise ValueError('KB_JSON: '+str(e)) from e

def save(path,value,replace=False):
    p=Path(path)
    if p.is_symlink():raise ValueError('KB_PATH: symlink output refused')
    if p.exists() and not replace:raise ValueError('KB_EXISTS: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,ensure_ascii=False,indent=2).encode('utf8')
    fd,temp=tempfile.mkstemp(prefix='.kb-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.replace(temp,p)
    finally:
        if Path(temp).exists():Path(temp).unlink()

def member(root,name):
    if not isinstance(name,str) or not name or Path(name).is_absolute() or '\\' in name or ':' in name:raise ValueError('KB_PATH: relative member required')
    path=(root/name).resolve()
    if not path.is_relative_to(root):raise ValueError('KB_PATH: outside workspace')
    return path

def workspace(path):
    root=Path(path).resolve()
    if root.is_relative_to(SKILL):raise ValueError('KB_PATH: knowledge must be outside the Skill installation')
    state=read(root/'workspace.json',256*1024)
    if not isinstance(state,dict) or state.get('schema_version')!=VERSION or not {'rules_file','rules_sha256','imports','reviews','engineering_test_only'}<=state.keys() or not isinstance(state['imports'],dict) or not isinstance(state['reviews'],dict):raise ValueError('KB_SCHEMA: unsupported or incomplete workspace')
    if digest(member(root,state['rules_file']))!=state['rules_sha256']:raise ValueError('KB_HASH: rules changed; do not silently replace evidence')
    return root,state

@contextmanager
def lock(root):
    p=root/'.write.lock'
    try:fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as e:raise ValueError('KB_BUSY: another writer or stale lock; inspect before retrying') from e
    os.close(fd)
    try:yield
    finally:p.unlink()

def initialize(path,engineering=False):
    root=Path(path).resolve()
    if root.is_relative_to(SKILL) or root.exists():raise ValueError('KB_EXISTS_OR_PATH: choose a new private directory outside the Skill')
    if not PUBLIC_RULES.is_file():raise ValueError('KB_RULES: bundled public rules missing')
    from .behavior import rule_cards
    if len(rule_cards(PUBLIC_RULES.read_text(encoding='utf8')))!=7:raise ValueError('KB_RULES: invalid seven-rule resource')
    root.mkdir(parents=True)
    (root/'rules.md').write_bytes(PUBLIC_RULES.read_bytes())
    (root/'.gitignore').write_text('*\n',encoding='utf8')
    save(root/'cases.json',{'schema_version':'local-cases-1','cases':[]})
    state={'schema_version':VERSION,'created_utc':now(),'rules_file':'rules.md','rules_sha256':digest(root/'rules.md'),'imports':{},'reviews':{},'engineering_test_only':engineering}
    save(root/'workspace.json',state)
    save(root/'knowledge.json',{'schema_version':'portable-knowledge-1','root':'.','cases_file':'cases.json','rules_file':'rules.md',
        'cases_sha256':digest(root/'cases.json'),'rules_sha256':state['rules_sha256'],'known_titles':{},'known_sources':{},'engineering_test_only':engineering})
    return {'workspace':str(root),'configuration':str(root/'knowledge.json'),'ready_for_prepare':False,'reason':'Import and review real report evidence, then build; no synthetic substitute.'}

def file_input(path,suffixes):
    p=Path(path).resolve()
    if p.suffix.lower() not in suffixes or not p.is_file() or p.stat().st_size>MAX_SOURCE_BYTES:raise ValueError('KB_INPUT: missing, unsupported or oversized explicit file')
    return p

def source_units(path,tex):
    if path.suffix.lower()=='.docx':
        if tex:raise ValueError('KB_INPUT: TeX requires a PDF')
        d=DocxReader(path).read()
        return d['title'],[{'unit_id':b['paragraph_id'],'text':b['text'],'section':b['section'],'location':{'paragraph_index':b.get('paragraph_index'),'block_id':b.get('block_id')}} for b in d['blocks'] if b['analysis_scope']=='body_candidate'],{'status':'DOCX','warnings':d['warnings']}
    d=preprocess_pdf(path,'source')
    if d['source_kind']!='standalone_pdf':raise ValueError('KB_INPUT: paper must not be a detector report')
    units=[{'unit_id':p['paragraph_id'],'text':p['normalized_text'],'section':p['section'],'location':{'pages':p.get('source_pages',[p['pdf_page']]),'lines':p['line_evidence']}} for p in d['paragraphs'] if p['analysis_candidate']]
    audit={'status':'PDF_ONLY','warnings':['PDF reading order and formula extraction remain approximate.']}
    if tex:
        t=TexReader(tex).read();audit=crosscheck(t,d)
        if audit['status']=='MATERIAL_MISMATCH':raise ValueError('KB_VERSION: PDF and TeX do not match')
    return d['title'],units,audit

def occurrences(needle,haystack):
    # Token boundaries, not a fuzzy semantic or substring match.
    query=' '+' '.join(needle)+' ';hay=' '+' '.join(haystack)+' '
    indexes=[];start=0
    while (pos:=hay.find(query,start))>=0:
        indexes.append(hay[:pos+1].count(' ')-1);start=pos+1
    return indexes

def version_screen(title,units,report):
    if not title:raise ValueError('KB_VERSION_UNVERIFIED: source title unavailable')
    from .docx_workflow import history_title_check
    identity=history_title_check(title,report,report['source_path'])
    a=[w for u in units for w in tokens(u['text'])]
    prose=[p for p in report['paragraphs'] if p['analysis_candidate']]
    b=[w for p in prose for w in tokens(p['normalized_text'])]
    if min(len(a),len(b))<30 or max(len(a),len(b))>60000:raise ValueError('KB_VERSION_UNVERIFIED: insufficient or excessive prose for the fixed version screen')
    matched=sum(m.size for m in difflib.SequenceMatcher(None,a,b,autojunk=False).get_matching_blocks())
    numeric_a=Counter(w for w in a if re.fullmatch(r'\d+(?:\.\d+)?',w))
    numeric_b=Counter(w for w in b if re.fullmatch(r'\d+(?:\.\d+)?',w))
    if numeric_a!=numeric_b:raise ValueError('KB_VERSION_UNVERIFIED: prose numeric tokens differ; resolve extraction/version differences before importing')
    screen={'status':'MATCH_SCREEN_ONLY','title_identity':identity,'source_prose_tokens':len(a),'report_prose_tokens':len(b),
        'source_recall':matched/len(a),'report_recall':matched/len(b),'minimum_recall':.98,
        'limitation':'Fixed lexical .98 screen is not full mathematical/version certification; reviewer must confirm same version. Candidate quotes additionally require unique exact token matches.'}
    if min(screen['source_recall'],screen['report_recall'])<.98:raise ValueError('KB_VERSION_MISMATCH: fixed bidirectional prose screen failed; use the matching manuscript/report version')
    return screen,a,prose

def checked_import(root,state,import_id):
    if not isinstance(import_id,str) or import_id not in state['imports']:raise ValueError('KB_IMPORT: unknown import ID')
    entry=state['imports'][import_id];path=member(root,entry['file'])
    if digest(path)!=entry['sha256']:raise ValueError('KB_HASH: import snapshot changed')
    data=read(path)
    for name,h in data['artifact_hashes'].items():
        if digest(member(path.parent,name))!=h:raise ValueError('KB_HASH: imported evidence changed')
    return data

def import_pair(path,paper,report,family,tex=None,render=False):
    root,state=workspace(path)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',family):raise ValueError('KB_FAMILY: use an opaque family ID')
    paper=file_input(paper,{'.pdf','.docx'});report=file_input(report,{'.pdf'});tex=file_input(tex,{'.tex'}) if tex else None
    if paper==report or digest(paper)==digest(report):raise ValueError('KB_INPUT: manuscript and report cannot be the same file')
    key=canonical_hash({'paper':digest(paper),'report':digest(report),'tex':digest(tex) if tex else None,'family':family})[:20]
    import_id='pair_'+key
    if import_id in state['imports']:raise ValueError('KB_DUPLICATE: this exact pair/family is already imported')
    title,units,source_audit=source_units(paper,tex)
    old=preprocess_pdf(report,'report')
    if old['source_kind']!='report_embedded_body':raise ValueError('KB_REPORT: unsupported report body template; no OCR or labels inferred')
    screen,source_words,prose=version_screen(title,units,old)
    offset=0;source_locations=[]
    for u in units:
        source_locations.append((offset,offset+len(tokens(u['text'])),u));offset+=len(tokens(u['text']))
    pages={};accepted_count=0;geometry_evidence={}
    with pymupdf.open(report) as pdf:
        if len(pdf)>200:raise ValueError('KB_LIMIT: report exceeds 200 pages')
        for number in sorted({l.get('pdf_page',p['pdf_page']) for p in prose for l in p['line_evidence']}):
            page=pdf[number-1];_,_,chars=extract_page_text(page,number)
            accepted,rejected,unresolved,_=detect_regions(page,number,chars)
            accepted_count+=len(accepted)
            pages[number]=chars
            geometry_evidence[str(number)]={'accepted':accepted,'rejected':rejected,'unresolved':unresolved}
        report_words=[w for p in prose for w in tokens(p['normalized_text'])]
        candidates=[]
        for i,p in enumerate(prose):
            text=p['normalized_text'];query=tokens(text)
            if len(query)<12:continue
            matches=occurrences(query,source_words);report_matches=occurrences(query,report_words)
            unique=len(matches)==len(report_matches)==1
            hits={}
            for line in p['line_evidence']:
                number=line.get('pdf_page',p['pdf_page']);rect=line['bbox']
                for c in pages[number]:
                    x=(c['bbox'][0]+c['bbox'][2])/2;y=(c['bbox'][1]+c['bbox'][3])/2
                    if c['text'].strip() and rect[0]<=x<=rect[2] and rect[1]<=y<=rect[3]:hits[c['character_id']]=c
            chars=list(hits.values());h=sum(c['geometrically_highlighted'] for c in chars)
            ambiguous=sum(c['geometry_ambiguous'] or c['unresolved_region_overlap'] for c in chars)
            label='geometry_uncertain' if not chars or ambiguous or not accepted_count else 'unmarked' if not h else 'highlighted' if h==len(chars) else 'partial'
            evidence_id='e_'+canonical_hash({'paragraph':p['paragraph_id'],'pages':p.get('source_pages',[p['pdf_page']])})[:16]
            geometry_evidence[evidence_id]={'characters':chars,'line_evidence':p['line_evidence']}
            matched=[u for start,end,u in source_locations if unique and start<matches[0]+len(query) and end>matches[0]]
            candidates.append({'candidate_id':'c_'+canonical_hash({'import':import_id,'paragraph':p['paragraph_id']})[:16],
                'text':text,'original_report_text':p['original_text'],'section':p['section'],'text_type':p['role'],
                'report_pages':p.get('source_pages',[p['pdf_page']]),'source_matches':[{'unit_id':u['unit_id'],'location':u['location']} for u in matched],
                'source_match_status':'unique_exact_tokens' if unique else 'unmatched_or_ambiguous','geometry_state':label,
                'character_count':len(chars),'highlighted_character_count':h,'ambiguous_character_count':ambiguous,
                'highlight_coverage':h/len(chars) if chars else None,'evidence_id':evidence_id,
                'eligibility_status':'local_prose_candidate_not_officially_confirmed',
                'context':{'before':[q['normalized_text'] for q in prose[max(0,i-2):i]],'after':[q['normalized_text'] for q in prose[i+1:i+3]]},
                'review_status':'pending','warning':'Geometry is a candidate observation. Unmarked does not establish Human or official eligibility. Labels are never inferred from language style.'})
        if not candidates:raise ValueError('KB_NO_CANDIDATES: no >=12-token prose candidates')
        with lock(root):
            # Re-read under lock so another import is not silently lost.
            _,state=workspace(root)
            if import_id in state['imports']:raise ValueError('KB_DUPLICATE: pair already imported')
            folder=root/'imports'/import_id
            if folder.exists():raise ValueError('KB_EXISTS: incomplete prior import; retain and inspect it')
            folder.mkdir(parents=True)
            save(folder/'geometry.json',geometry_evidence)
            artifacts={'geometry.json':digest(folder/'geometry.json')}
            if render:
                for number in sorted({n for c in candidates for n in c['report_pages']}):
                    page=pdf[number-1]
                    for c in candidates:
                        if number in c['report_pages']:
                            for l in geometry_evidence[c['evidence_id']]['line_evidence']:
                                if l.get('pdf_page',c['report_pages'][0])==number:page.draw_rect(pymupdf.Rect(l['bbox']),color=(1,0,0),width=.5)
                    name=f'report-page-{number:03d}.png';page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(folder/name);artifacts[name]=digest(folder/name)
            data={'schema_version':VERSION,'import_id':import_id,'created_utc':now(),'family_id':family,'title':title,
                'source_files':{'paper':{'path':str(paper),'sha256':digest(paper)},'report':{'path':str(report),'sha256':digest(report)},**({'tex':{'path':str(tex),'sha256':digest(tex)}} if tex else {})},
                'version_screen':screen,'source_audit':source_audit,'geometry_profile':PROFILE,'accepted_vector_regions':accepted_count,
                'geometry_limitation':'Only the bundled cyan vector profile is screened. Raster/other-color reports require separate manual evidence; no percentage-based threshold tuning.',
                'candidates':candidates,'artifact_hashes':artifacts,'engineering_test_only':state['engineering_test_only']}
            save(folder/'import.json',data)
            template={'import_id':import_id,'import_sha256':digest(folder/'import.json'),'reviewer':'','same_version_confirmed':False,
                'review_method':'pdf_visual_check','decisions':[{'candidate_id':c['candidate_id'],'action':'skip','confirmed_label':None,'note':'','geometry_override_reason':'','evidence_pages':c['report_pages']} for c in candidates]}
            save(folder/'review.template.json',template)
            lines=['# 本地知识候选复核','',f'Import: {import_id}',f'来源：{paper}',f'报告：{report}',
                '自动版本筛查仅为辅助证据。逐项查看报告页面；未实际核查时保持 skip，不得虚构人工确认。完整分数不进入案例卡片。','']
            for c in candidates:lines.extend([f"## {c['candidate_id']} | {c['section']} | report pages {c['report_pages']}",c['text'],
                f"候选几何状态：{c['geometry_state']}；source match: {c['source_match_status']}；H chars: {c['highlighted_character_count']}/{c['character_count']}。",''])
            (folder/'REVIEW.md').write_text('\n\n'.join(lines),encoding='utf8')
            state['imports'][import_id]={'file':(folder/'import.json').relative_to(root).as_posix(),'sha256':digest(folder/'import.json')}
            save(root/'workspace.json',state,replace=True)
    return {'import_id':import_id,'candidate_count':len(candidates),'geometry_states':dict(Counter(c['geometry_state'] for c in candidates)),
        'source_unique_matches':sum(c['source_match_status']=='unique_exact_tokens' for c in candidates),'review_template':str(folder/'review.template.json'),'review_document':str(folder/'REVIEW.md'),'cases_added':0}

def review(path,decisions):
    root,state=workspace(path);d=read(decisions,8*1024*1024)
    if not isinstance(d,dict):raise ValueError('KB_REVIEW: object required')
    with lock(root):
        _,state=workspace(root);data=checked_import(root,state,d.get('import_id'))
        if d.get('import_sha256')!=state['imports'][data['import_id']]['sha256']:raise ValueError('KB_HASH: decisions do not bind the import')
        if not isinstance(d.get('reviewer'),str) or not d['reviewer'].strip() or d.get('same_version_confirmed') is not True or d.get('review_method') not in {'pdf_visual_check','manual_pdf_coordinates'}:raise ValueError('KB_REVIEW: identify reviewer, actual PDF check and same-version confirmation')
        by_id={c['candidate_id']:c for c in data['candidates']};seen=set();accepted=[]
        if not isinstance(d.get('decisions'),list):raise ValueError('KB_REVIEW: decisions array required')
        for row in d['decisions']:
            if not isinstance(row,dict) or row.get('candidate_id') not in by_id or row['candidate_id'] in seen:raise ValueError('KB_REVIEW: unknown or duplicate candidate')
            seen.add(row['candidate_id']);c=by_id[row['candidate_id']]
            if row.get('action') not in {'accept','reject','skip'}:raise ValueError('KB_REVIEW: action must be accept/reject/skip')
            if row['action']=='accept':
                if c['source_match_status']!='unique_exact_tokens':raise ValueError('KB_MATCH: cannot accept ambiguous/unmatched source text')
                if row.get('confirmed_label') not in LABELS or not isinstance(row.get('note'),str) or len(row['note'].strip())<8:raise ValueError('KB_REVIEW: actual label and specific evidence note required')
                if row['confirmed_label']!='uncertain' and row['confirmed_label']!=c['geometry_state'] and (not isinstance(row.get('geometry_override_reason'),str) or len(row['geometry_override_reason'].strip())<20):raise ValueError('KB_REVIEW: changing a geometric candidate label requires a specific geometry_override_reason from actual page inspection')
                if not isinstance(row.get('evidence_pages'),list) or set(row['evidence_pages'])!=set(c['report_pages']):raise ValueError('KB_REVIEW: evidence page binding mismatch')
                accepted.append(row['candidate_id'])
        if not seen:raise ValueError('KB_REVIEW: no candidate decisions')
        record={'created_utc':now(),'decisions':d,'accepted_candidate_ids':accepted,
            'unlisted_candidate_policy':'pending; never implicitly unmarked or accepted','limits':'Reviewer attestation is recorded, not an independently proven human visual review.'}
        review_id=canonical_hash(record)[:20];name='imports/'+data['import_id']+'/reviews/'+review_id+'.json';save(member(root,name),record)
        state['reviews'][data['import_id']]={'file':name,'sha256':digest(member(root,name))};save(root/'workspace.json',state,replace=True)
    return {'review_id':review_id,'accepted':len(accepted),'not_accepted':len(data['candidates'])-len(accepted),'cases_added':0,'next':'knowledge build'}

def expected_cases(root,state):
    cases={};titles={};sources={};conflicts={};deduplicated=0
    for import_id in sorted(state['imports']):
        data=checked_import(root,state,import_id)
        if import_id not in state['reviews']:continue
        entry=state['reviews'][import_id];review_path=member(root,entry['file'])
        if digest(review_path)!=entry['sha256']:raise ValueError('KB_HASH: review changed')
        r=read(review_path);d=r['decisions']
        if d['import_sha256']!=state['imports'][import_id]['sha256']:raise ValueError('KB_HASH: review/import mismatch')
        for source in data['source_files'].values():
            if not Path(source['path']).is_file() or digest(source['path'])!=source['sha256']:raise ValueError('KB_HASH: source/report changed or missing; preserve original evidence')
        for key,register in [(data['title'],titles),(data['source_files']['paper']['sha256'],sources)]:
            if key in register and register[key]!=data['family_id']:raise ValueError('KB_FAMILY: known identity assigned conflicting families')
            register[key]=data['family_id']
        by_id={c['candidate_id']:c for c in data['candidates']}
        for row in d['decisions']:
            if row['action']!='accept':continue
            c=by_id[row['candidate_id']];label=row['confirmed_label'];report_sha=data['source_files']['report']['sha256']
            signature={'family':data['family_id'],'report':report_sha,'text':tokens(c['text']),'label':label}
            case_id='local_'+canonical_hash(signature)[:24]
            if case_id in cases:deduplicated+=1;continue
            conflicts.setdefault(canonical_hash({'family':data['family_id'],'text':tokens(c['text'])}),set()).add(label)
            cases[case_id]={'case_id':case_id,'family_id':data['family_id'],'document_sha256':data['source_files']['paper']['sha256'],
                'text':c['text'],'label':label,'section':c['section'],'text_type':c['text_type'],'context':c['context'],
                'observable_features':{'english_token_count':len(tokens(c['text'])),'geometry_coverage':c['highlight_coverage'],'geometry_state':c['geometry_state']},
                'similarities_and_differences':'Compare both label directions and context; no style feature determines a label.',
                'unsupported_inferences':'Not AI authorship, official denominator membership, a calibrated probability or a permanent label in a different version.',
                'evidence':{'report_sha256':report_sha,'report_pages':c['report_pages'],'import_id':import_id,'candidate_id':c['candidate_id'],
                    'import_sha256':state['imports'][import_id]['sha256'],'review_sha256':entry['sha256'],'reviewer':d['reviewer'],
                    'review_method':d['review_method'],'review_note':row['note'],'geometry_evidence_id':c['evidence_id'],
                    'geometry_override_reason':row.get('geometry_override_reason',''),
                    'geometry_state':c['geometry_state'],'confirmed_label':label,'eligibility_status':c['eligibility_status']}}
    return list(cases.values()),titles,sources,{'deduplicated':deduplicated,'cross_report_conflicting_texts':sum(len(v)>1 for v in conflicts.values())}

def build(path):
    root,state=workspace(path)
    with lock(root):
        _,state=workspace(root);cases,titles,sources,stats=expected_cases(root,state)
        if not cases:raise ValueError('KB_NO_REVIEWED_CASES: import and actually review at least one real case; no empty/synthetic fallback')
        result={'schema_version':'local-cases-1','builder_version':VERSION,'cases':cases}
        generation=canonical_hash(result);folder=root/'generations'/generation
        if not folder.exists():save(folder/'cases.json',result)
        elif read(folder/'cases.json')!=result:raise ValueError('KB_HASH: generation content changed')
        config={'schema_version':'portable-knowledge-1','root':'.','cases_file':(folder/'cases.json').relative_to(root).as_posix(),'rules_file':state['rules_file'],
            'cases_sha256':digest(folder/'cases.json'),'rules_sha256':state['rules_sha256'],'known_titles':titles,'known_sources':sources,'engineering_test_only':state['engineering_test_only']}
        save(root/'knowledge.json',config,replace=True)
        knowledge=load(root/'knowledge.json')
    return {'configuration':str(root/'knowledge.json'),'case_count':len(cases),'label_counts':dict(Counter(c['label'] for c in cases)),
        'family_count':len(set(c['family_id'] for c in cases)),'rule_count':knowledge['provenance']['rule_count'],'generation':generation,
        'ready_for_prepare':True,'statistics':stats,'limits':'Local references built, not model weights or accuracy calibration. Family filtering may leave zero references for a later target.'}

def verify(path):
    root,state=workspace(path);cases,titles,sources,stats=expected_cases(root,state)
    config=read(root/'knowledge.json',256*1024);actual=read(member(root,config['cases_file']))
    if config.get('schema_version')!='portable-knowledge-1' or config.get('root')!='.' or config.get('rules_file')!=state['rules_file']:raise ValueError('KB_SCHEMA: active configuration no longer belongs to this workspace')
    if digest(member(root,config['cases_file']))!=config['cases_sha256'] or config['rules_sha256']!=state['rules_sha256']:raise ValueError('KB_HASH: active configuration resources changed')
    built={c['case_id']:c for c in actual['cases']};expected={c['case_id']:c for c in cases}
    current=built==expected and config.get('known_titles')==titles and config.get('known_sources')==sources
    if built and current:load(root/'knowledge.json')
    return {'workspace':str(root),'import_count':len(state['imports']),'review_count':len(state['reviews']),'reviewed_case_count':len(cases),
        'built_case_count':len(built),'generation_current':current,'ready_for_prepare':bool(built) and current,'statistics':stats,
        'next':'prepare with knowledge.json' if built and current else 'import/review/build as needed; empty or stale knowledge is not ready'}

def configure_parser(parser):
    sub=parser.add_subparsers(dest='kb_command',required=True)
    a=sub.add_parser('init');a.add_argument('--output',required=True);a.add_argument('--engineering-test',action='store_true')
    a=sub.add_parser('import');a.add_argument('--workspace',required=True);a.add_argument('--paper',required=True);a.add_argument('--report',required=True);a.add_argument('--family',required=True);a.add_argument('--tex');a.add_argument('--render',action='store_true')
    a=sub.add_parser('review');a.add_argument('--workspace',required=True);a.add_argument('--decisions',required=True)
    for name in ['build','verify']:sub.add_parser(name).add_argument('--workspace',required=True)

def run(args):
    if args.kb_command=='init':return initialize(args.output,args.engineering_test)
    if args.kb_command=='import':return import_pair(args.workspace,args.paper,args.report,args.family,args.tex,args.render)
    if args.kb_command=='review':return review(args.workspace,args.decisions)
    return build(args.workspace) if args.kb_command=='build' else verify(args.workspace)
