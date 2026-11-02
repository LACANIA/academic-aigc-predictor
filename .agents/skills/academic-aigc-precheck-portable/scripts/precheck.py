"""Portable local CLI: bundled modules only; the host supplies actual judgments."""
import argparse,base64,hashlib,importlib.metadata,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
SKILL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/'runtime'))
VERSION='RC1-DOCX-PORTABLE-0.2.0'

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    kb=sub.add_parser('knowledge')
    from tap.knowledge_builder import configure_parser
    configure_parser(kb)
    a=sub.add_parser('prepare');g=a.add_mutually_exclusive_group(required=True);g.add_argument('--pdf');g.add_argument('--docx')
    a.add_argument('--tex');a.add_argument('--history');a.add_argument('--family',required=True);a.add_argument('--knowledge',required=True)
    a.add_argument('--threshold',type=float);a.add_argument('--engineering-test',action='store_true');a.add_argument('--output',required=True)
    a=sub.add_parser('finish');a.add_argument('--packet',required=True);a.add_argument('--prediction',required=True);a.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='knowledge':
        from tap.knowledge_builder import run
        print(json.dumps(run(args),ensure_ascii=False,indent=2));return 0
    import tap.docx_workflow as workflow
    from tap import practical
    from tap.precheck import canonical_hash
    from tap.knowledge import load
    if args.command=='doctor':
        modules={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='tap' or n.startswith('tap.')) and getattr(m,'__file__',None)}
        if not all(Path(p).is_relative_to(SKILL/'runtime') for p in modules.values()):raise ValueError('IMPORT_ISOLATION: non-bundled tap module')
        import pymupdf
        print(json.dumps({'version':VERSION,'skill_root':str(SKILL),'cwd':os.getcwd(),'python':sys.executable,'sys_path':sys.path,
          'runtime_modules':modules,'dependencies':{'PyMuPDF':{'version':importlib.metadata.version('PyMuPDF'),'file':pymupdf.__file__}},
          'knowledge':'Explicit --knowledge required for prepare; no repository fallback.','model_client':False},ensure_ascii=False,indent=2));return 0
    out=Path(args.output)
    if out.exists():raise ValueError('OUTPUT_EXISTS: use a new directory; no overwrite')
    if args.command=='prepare':
        knowledge=load(args.knowledge)
        private,packet=workflow.prepare(args.knowledge,pdf=args.pdf,tex=args.tex,family=args.family,history=args.history,threshold=args.threshold,docx=args.docx)
        if packet is not None:
            packet.pop('packet_hash');packet.update(portable_release=VERSION,knowledge_provenance=knowledge['provenance'],
               engineering_test_only=args.engineering_test or knowledge['provenance']['engineering_test_only'])
            packet['packet_hash']=canonical_hash(packet);private['packet']=packet
        out.mkdir(parents=True)
        def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
        save('prepared.json',private);save('version-audit.json',private['version_audit'])
        if packet is None:print('MATERIAL_MISMATCH: joint input stopped');return 2
        save('model_input.json',packet);(out/'whole_document.md').write_text(workflow.readable(packet),encoding='utf8')
        save('access-scope.json',{'explicit_inputs':{k:v for k,v in {'pdf':args.pdf,'docx':args.docx,'tex':args.tex,'history':args.history}.items() if v},
           'knowledge_paths':knowledge['explicit_read_paths'],'runtime_root':str(SKILL/'runtime'),
           'limits':'Recorded application scope, not an OS audit of every Python/file access; TeX dependencies bounded by Reader.'})
        if private.get('docx'):
            (out/'source-document.xml').write_bytes(base64.b64decode(private['docx']['document_xml_base64']))
            save('source-structure.json',{k:private['docx'][k] for k in ['diagnostics','tables','math_objects','raw_paragraphs']})
        print(json.dumps({'input_mode':packet['input_mode'],'mode':packet['mode'],'packet_hash':packet['packet_hash'],
           'version_status':packet['version_status'],'engineering_test_only':packet['engineering_test_only']}))
    else:
        packet=json.loads(Path(args.packet).read_text(encoding='utf8'));prediction=json.loads(Path(args.prediction).read_text(encoding='utf8'))
        if packet.get('engineering_test_only') and prediction.get('engineering_test_only') is not True:raise ValueError('ENGINEERING_TEST_ONLY: fixture output must declare its status')
        text=workflow.report(packet,prediction)
        if packet.get('engineering_test_only') or prediction.get('engineering_test_only'):
            text='# ENGINEERING_TEST_ONLY\n\n格式测试材料，模拟数值并非真实宿主预测或正式检测结果。\n\n'+text
        out.mkdir(parents=True);(out/'PRECHECK_REPORT.md').write_text(text,encoding='utf8')
        print('Validated report:',out/'PRECHECK_REPORT.md')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,ImportError) as e:
        print('Precheck stopped: '+str(e)+'; verify Python>=3.11, PyMuPDF>=1.24,<2 and explicit knowledge configuration.',file=sys.stderr);sys.exit(2)
