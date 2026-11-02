"""Synthetic local-library integration checks; no private papers or real labels."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import copy,hashlib,json,subprocess,sys
import pytest,pymupdf

BASE=Path(__file__).resolve().parents[1]
SKILL=BASE/'.agents/skills/academic-aigc-precheck-portable'
if not SKILL.exists():SKILL=BASE/'academic-aigc-precheck-portable'
sys.path.insert(0,str(SKILL/'runtime'))
from tap import knowledge_builder as kb
from tap.knowledge import load
from tap.contrastive import case_card,select_cases

TITLE='Local Knowledge Engineering Fixture for Input Verification'
H='The engineering fixture describes a local sequence of observations for checking source identity and coordinate mapping. Its sentences are invented only for testing the software and do not represent an actual detector outcome.'
U='The second paragraph records an independent sequence of checks with explicit inputs and preserved evidence. Every example in this document is synthetic and cannot establish accuracy on an academic manuscript.'
M='The final procedure stores the original text together with local source locations and review decisions. No external detection service or additional language model is contacted during this engineering exercise.'

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def read(path):return json.loads(path.read_text(encoding='utf8'))

def fixture(root,mode='highlighted',title=TITLE,stem='pair'):
    root.mkdir(parents=True,exist_ok=True);paper=root/(stem+'.pdf');report=root/(stem+'-report.pdf')
    d=pymupdf.open();p=d.new_page();p.insert_text((60,100),title,fontsize=15)
    for y,heading,text in [(140,'Abstract',H),(260,'1 Introduction',U),(380,'2 Method',M)]:
        p.insert_text((60,y),heading,fontsize=12,fontname='hebo');p.insert_textbox(pymupdf.Rect(60,y+15,530,y+100),text,fontsize=10)
    d.save(paper);r=pymupdf.open();c=r.new_page();c.insert_text((60,100),'ENGINEERING_TEST_ONLY\nSubmission ID fixture')
    c=r.new_page();c.insert_text((60,100),'ENGINEERING_TEST_ONLY\nAI Writing Overview\n20% detected as AI')
    r.insert_pdf(d);p=r[2];p.insert_text((60,30),'AI Writing Submission - ENGINEERING_TEST_ONLY')
    lines=[l for b in p.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] if 150<l['bbox'][1]<240]
    chosen=lines if mode=='highlighted' else lines[:1] if mode=='partial' else []
    for line in chosen:
        a=pymupdf.Rect(line['bbox']);a.x0-=.1;a.x1+=.1;a.y0-=.1;a.y1+=.1
        p.draw_rect(a,color=None,fill=kb.PROFILE['rgb'],fill_opacity=.4)
    r.save(report);d.close();r.close()
    return paper,report

def setup_pair(tmp_path,mode='highlighted'):
    root=tmp_path/'private';kb.initialize(root,True);paper,report=fixture(tmp_path/'inputs',mode)
    info=kb.import_pair(root,paper,report,'fixture_family')
    return root,paper,report,info

def decisions(root,info,labels=None):
    template=read(Path(info['review_template']));template.update(reviewer='ENGINEERING_TEST_ONLY',same_version_confirmed=True)
    imported=read(root/'imports'/info['import_id']/'import.json');by_id={c['candidate_id']:c for c in imported['candidates']}
    for row in template['decisions']:
        c=by_id[row['candidate_id']]
        if c['source_match_status']=='unique_exact_tokens':
            row.update(action='accept',confirmed_label=(labels or {}).get(c['candidate_id'],c['geometry_state'] if c['geometry_state'] in kb.LABELS else 'uncertain'),note='ENGINEERING_TEST_ONLY: fixture evidence, no real human or model prediction.')
    path=root/(info['import_id']+'-decisions.json');write(path,template);return path

def test_init_copies_rules_and_empty_library_not_ready(tmp_path):
    root=tmp_path/'kb';r=kb.initialize(root,True)
    assert not r['ready_for_prepare'] and not kb.verify(root)['ready_for_prepare']
    assert (root/'rules.md').read_bytes()==kb.PUBLIC_RULES.read_bytes()
    with pytest.raises(ValueError,match='CASES_REQUIRED'):load(root/'knowledge.json')

def test_existing_workspace_and_install_location_refused(tmp_path):
    kb.initialize(tmp_path/'kb',True)
    with pytest.raises(ValueError,match='EXISTS'):kb.initialize(tmp_path/'kb',True)
    with pytest.raises(ValueError,match='EXISTS_OR_PATH'):kb.initialize(SKILL/'private-test',True)

def test_import_pending_geometry_source_and_score_separation(tmp_path):
    root,paper,report,info=setup_pair(tmp_path)
    data=read(root/'imports'/info['import_id']/'import.json')
    assert info['cases_added']==0 and info['source_unique_matches']==len(data['candidates'])
    assert set(c['geometry_state'] for c in data['candidates'])=={'highlighted','unmarked'}
    assert all(c['review_status']=='pending' for c in data['candidates'])
    assert not read(root/'cases.json')['cases']
    assert '20% detected as AI' not in json.dumps(data)

def test_no_compatible_blue_never_becomes_automatic_unmarked(tmp_path):
    root,_,_,info=setup_pair(tmp_path,'none')
    assert set(info['geometry_states'])=={'geometry_uncertain'}

def test_partial_highlight_remains_partial(tmp_path):
    root,_,_,info=setup_pair(tmp_path,'partial')
    assert 'partial' in info['geometry_states']
    kb.review(root,decisions(root,info));kb.build(root)
    assert 'partial' in {c['label'] for c in load(root/'knowledge.json')['cases']}

def test_repeated_import_refused(tmp_path):
    root,paper,report,_=setup_pair(tmp_path)
    with pytest.raises(ValueError,match='DUPLICATE'):kb.import_pair(root,paper,report,'fixture_family')

def test_wrong_title_and_wrong_version_refused(tmp_path):
    root=tmp_path/'kb';kb.initialize(root,True);paper,_=fixture(tmp_path/'a')
    _,report=fixture(tmp_path/'b',title='Different Scientific Input for an Unrelated Engineering Fixture')
    with pytest.raises(ValueError,match='IDENTITY_MISMATCH'):kb.import_pair(root,paper,report,'fixture_family')
    wrong=tmp_path/'wrong.pdf';d=pymupdf.open(paper);d[0].add_redact_annot(pymupdf.Rect(50,270,550,365));d[0].apply_redactions();d.save(wrong);d.close()
    _,report=fixture(tmp_path/'c')
    with pytest.raises(ValueError,match='VERSION_MISMATCH'):kb.import_pair(root,wrong,report,'fixture_family')

def test_report_as_source_and_same_file_refused(tmp_path):
    root,paper,report,info=setup_pair(tmp_path)
    with pytest.raises(ValueError,match='same file'):kb.import_pair(root,paper,paper,'x')
    other,other_report=fixture(tmp_path/'b',stem='other')
    with pytest.raises(ValueError,match='must not be a detector report'):kb.import_pair(root,report,other_report,'x')

def test_actual_review_attestation_required(tmp_path):
    root,_,_,info=setup_pair(tmp_path);p=Path(info['review_template'])
    with pytest.raises(ValueError,match='identify reviewer'):kb.review(root,p)
    with pytest.raises(ValueError,match='NO_REVIEWED_CASES'):kb.build(root)

@pytest.mark.parametrize('change',['quote','geometry','review_hash','pages','duplicate','note','label'])
def test_tampering_and_invalid_review_refused(tmp_path,change):
    root,_,_,info=setup_pair(tmp_path);path=decisions(root,info);d=read(path)
    if change=='quote':
        imported=root/'imports'/info['import_id']/'import.json';v=read(imported);v['candidates'][0]['text']='Invented quote';write(imported,v)
    elif change=='geometry':
        (root/'imports'/info['import_id']/'geometry.json').write_text('{}',encoding='utf8')
    elif change=='review_hash':d['import_sha256']='0'*64
    elif change=='pages':d['decisions'][0]['evidence_pages']=[999]
    elif change=='duplicate':d['decisions'].append(copy.deepcopy(d['decisions'][0]))
    elif change=='note':d['decisions'][0]['note']=''
    else:d['decisions'][0]['confirmed_label']='Human'
    write(path,d)
    with pytest.raises(ValueError):kb.review(root,path)

def test_build_load_family_filter_and_case_schema(tmp_path):
    root,paper,report,info=setup_pair(tmp_path);kb.review(root,decisions(root,info));r=kb.build(root)
    assert r['ready_for_prepare'] and r['rule_count']==7 and kb.verify(root)['generation_current']
    k=load(root/'knowledge.json');assert len(k['cases'])==r['case_count']
    assert not select_cases(k['cases'],'fixture_family','other','new_paper')
    for c in k['cases']:
        card=case_card(c);assert 'report_sha256' not in card and 'source_path' not in card and 'observed_score' not in card
        assert c['evidence']['report_sha256']==kb.digest(report)
    again=kb.build(root);assert again['generation']==r['generation']

def test_source_change_and_configuration_tamper_detected(tmp_path):
    root,paper,_,info=setup_pair(tmp_path);kb.review(root,decisions(root,info));kb.build(root)
    old=paper.read_bytes();paper.write_bytes(old+b'changed')
    with pytest.raises(ValueError,match='source/report changed'):kb.verify(root)
    paper.write_bytes(old);c=read(root/'knowledge.json');c['cases_sha256']='0'*64;write(root/'knowledge.json',c)
    with pytest.raises(ValueError,match='configuration'):kb.verify(root)

def test_changed_rules_and_path_escape_rejected(tmp_path):
    root=tmp_path/'kb';kb.initialize(root,True);(root/'rules.md').write_text('changed',encoding='utf8')
    with pytest.raises(ValueError,match='rules changed'):kb.verify(root)
    for name in ['../outside','/outside','x\\y','C:/outside']:
        with pytest.raises(ValueError,match='KB_PATH'):kb.member(root.resolve(),name)

def test_write_lock_prevents_mutation(tmp_path):
    root,_,_,info=setup_pair(tmp_path);(root/'.write.lock').write_text('active',encoding='utf8')
    with pytest.raises(ValueError,match='KB_BUSY'):kb.review(root,decisions(root,info))

def test_conflicting_cross_report_labels_not_collapsed(tmp_path):
    root,_,_,info=setup_pair(tmp_path);kb.review(root,decisions(root,info));first=kb.build(root)
    paper,report=fixture(tmp_path/'second','none',stem='second')
    second=kb.import_pair(root,paper,report,'fixture_family');dpath=decisions(root,second);d=read(dpath)
    for row in d['decisions']:row.update(confirmed_label='unmarked',geometry_override_reason='ENGINEERING_TEST_ONLY: known synthetic page has no highlight fill at all.')
    write(dpath,d);kb.review(root,dpath);result=kb.build(root)
    assert result['case_count']>first['case_count'] and result['statistics']['cross_report_conflicting_texts']>=1

def test_pdf_docx_and_tex_pair_inputs(tmp_path):
    root=tmp_path/'kb';kb.initialize(root,True);paper,report=fixture(tmp_path/'inputs')
    W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def p(text,style=''):return '<w:p>'+('<w:pPr><w:pStyle w:val="'+style+'"/></w:pPr>' if style else '')+'<w:r><w:t>'+text+'</w:t></w:r></w:p>'
    body=p(TITLE,'Title')+p('Abstract')+p(H)+p('Introduction','Heading1')+p(U)+p('Method','Heading1')+p(M)
    docx=tmp_path/'paper.docx'
    with ZipFile(docx,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr('word/document.xml','<w:document xmlns:w="'+W+'"><w:body>'+body+'</w:body></w:document>')
    result=kb.import_pair(root,docx,report,'fixture_family');assert result['source_unique_matches']>=1
    tex=tmp_path/'main.tex';tex.write_text('\\begin{document}\n\\title{'+TITLE+'}\n\\begin{abstract}\n'+H+'\n\\end{abstract}\n\\section{Introduction}\n'+U+'\n\\section{Method}\n'+M+'\n\\end{document}',encoding='utf8')
    assert kb.import_pair(root,paper,report,'fixture_family',tex)['candidate_count']>=1

def test_render_and_cli_status(tmp_path):
    root=tmp_path/'kb';kb.initialize(root,True);paper,report=fixture(tmp_path/'inputs')
    info=kb.import_pair(root,paper,report,'fixture_family',render=True)
    assert list((root/'imports'/info['import_id']).glob('report-page-*.png'))
    r=subprocess.run([sys.executable,'-X','utf8',str(SKILL/'scripts/precheck.py'),'knowledge','verify','--workspace',str(root)],capture_output=True,text=True,encoding='utf8')
    assert r.returncode==0 and json.loads(r.stdout)['ready_for_prepare'] is False

def test_partial_cannot_silently_become_full_highlight(tmp_path):
    root,_,_,info=setup_pair(tmp_path,'partial');path=decisions(root,info);d=read(path)
    data=read(root/'imports'/info['import_id']/'import.json');partial=next(c['candidate_id'] for c in data['candidates'] if c['geometry_state']=='partial')
    next(r for r in d['decisions'] if r['candidate_id']==partial)['confirmed_label']='highlighted';write(path,d)
    with pytest.raises(ValueError,match='geometry_override_reason'):kb.review(root,path)

def test_small_numeric_version_difference_is_not_hidden_by_recall(tmp_path):
    paper,report=fixture(tmp_path/'inputs')
    units=[{'text':H+' The fixed measurement is 123.45.'}]
    old={'title':TITLE,'source_path':str(report),'paragraphs':[{'analysis_candidate':True,'normalized_text':H+' The fixed measurement is 123.46.'}]}
    with pytest.raises(ValueError,match='numeric tokens differ'):kb.version_screen(TITLE,units,old)

def test_stale_generation_after_new_review_is_explicit(tmp_path):
    root,_,_,info=setup_pair(tmp_path);path=decisions(root,info);kb.review(root,path);kb.build(root)
    d=read(path);d['decisions'][0]['action']='reject';write(path,d);kb.review(root,path)
    assert not kb.verify(root)['generation_current'] and not kb.verify(root)['ready_for_prepare']

def test_invalid_workspace_schema_is_clear_error(tmp_path):
    root=tmp_path/'kb';kb.initialize(root,True);write(root/'workspace.json',[])
    with pytest.raises(ValueError,match='KB_SCHEMA'):kb.verify(root)
