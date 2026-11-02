"""Explicit private knowledge mount. No repository fallback or directory search."""
import hashlib,json
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _json(path,limit):
    if not path.is_file():raise ValueError('KNOWLEDGE_MISSING: '+str(path))
    if path.stat().st_size>limit:raise ValueError('KNOWLEDGE_LIMIT: resource too large')
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (UnicodeError,json.JSONDecodeError) as e:raise ValueError('KNOWLEDGE_INVALID_JSON: '+str(e)) from e

def load(config):
    if not config:raise ValueError('KNOWLEDGE_REQUIRED: supply --knowledge config.json; no RC1-equivalent prediction without licensed local knowledge')
    config=Path(config).resolve();c=_json(config,256*1024)
    if not isinstance(c,dict) or c.get('schema_version')!='portable-knowledge-1':raise ValueError('KNOWLEDGE_SCHEMA: expected portable-knowledge-1')
    root_value=c.get('root')
    if not isinstance(root_value,str) or not root_value:raise ValueError('KNOWLEDGE_REQUIRED: configure an explicit local root')
    root=Path(root_value)
    if not root.is_absolute():root=config.parent/root
    root=root.resolve()
    def member(key):
        value=c.get(key)
        if not isinstance(value,str) or not value or Path(value).is_absolute():raise ValueError('KNOWLEDGE_PATH: relative file name required')
        path=(root/value).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('KNOWLEDGE_PATH: missing or outside explicit root')
        return path
    cases_path=member('cases_file');rules_path=member('rules_file')
    hashes={}
    for label,path in [('cases',cases_path),('rules',rules_path)]:
        h=digest(path);expected=c.get(label+'_sha256')
        if not isinstance(expected,str) or h!=expected:raise ValueError('KNOWLEDGE_HASH: '+label+' identity mismatch')
        hashes[label]=h
    case_data=_json(cases_path,8*1024*1024)
    cases=case_data.get('cases') if isinstance(case_data,dict) else None
    if not isinstance(cases,list) or not cases:raise ValueError('KNOWLEDGE_CASES_REQUIRED: no silent substitute for the RC1 case library')
    if any(not isinstance(x,dict) or not isinstance(x.get('case_id'),str) for x in cases):raise ValueError('KNOWLEDGE_CASES: invalid case record')
    if len({x.get('case_id') for x in cases})!=len(cases):raise ValueError('KNOWLEDGE_CASES: duplicate case IDs')
    required={'case_id','family_id','text','label','section','text_type','context','observable_features','similarities_and_differences','unsupported_inferences','evidence'}
    if any(not required<=x.keys() or x['label'] not in {'highlighted','unmarked','partial','uncertain'} or not isinstance(x['evidence'],dict) or not x['evidence'].get('report_sha256') for x in cases):raise ValueError('KNOWLEDGE_CASES: incomplete source/label schema')
    for key in ['known_titles','known_sources']:
        values=c.get(key,{})
        if not isinstance(values,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in values.items()):raise ValueError('KNOWLEDGE_SCHEMA: invalid '+key)
    if rules_path.stat().st_size>512*1024:raise ValueError('KNOWLEDGE_LIMIT: rules resource too large')
    rules=rules_path.read_text(encoding='utf8')
    from .behavior import rule_cards
    cards=rule_cards(rules)
    if len(cards)!=7 or {r['rule_id'] for r in cards}!={f'R{i:02d}' for i in range(1,8)}:raise ValueError('KNOWLEDGE_RULES: original seven rule cards required')
    return {'cases':cases,'rules_text':rules,'known_titles':c.get('known_titles',{}),'known_sources':c.get('known_sources',{}),
       'provenance':{'configuration_sha256':digest(config),'cases_sha256':hashes['cases'],'rules_sha256':hashes['rules'],
        'case_count':len(cases),'rule_count':len(cards),'engineering_test_only':c.get('engineering_test_only') is True},
       'explicit_read_paths':[str(config),str(cases_path),str(rules_path)]}
