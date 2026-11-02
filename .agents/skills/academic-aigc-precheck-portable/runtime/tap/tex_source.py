"""Small read-only LaTeX text reader. No TeX execution or dynamic expansion."""
from collections import Counter
import hashlib
from pathlib import Path
import re

MATH={'equation','equation*','align','align*','alignat','alignat*','gather','gather*','multline','multline*','displaymath','math'}
PROOF={'theorem','lemma','proof','proposition','corollary','definition','remark'}
FLOATS={'figure','figure*','table','table*'}
LAYOUT={'centering','small','footnotesize','scriptsize','normalsize','noindent','newpage','clearpage','relax','fi','hfill','vfill','par','maketitle','EOD','balance'}
SKIP_ARGS={'label':1,'vspace':1,'hspace':1,'setlength':2,'addtolength':2,'renewcommand':2,'newcommand':2,'providecommand':2,'refstepcounter':1,'bibliographystyle':1}
FORMAT={'textbf','textit','emph','textrm','textsf','texttt','textnormal','mbox','uppercase','MakeUppercase','underline'}
META={'history','doi','author','address','tfootnote','corresp','markboth','keywords','titlepgskip'}


def strip_comments(text):
    return re.sub(r'(?m)(?<!\\)%[^\n]*',lambda m:' '*len(m.group()),text)


def group(text,pos,left='{',right='}'):
    while pos<len(text) and text[pos].isspace():pos+=1
    if pos>=len(text) or text[pos]!=left:return None,pos
    start=pos+1;depth=1;pos+=1
    while pos<len(text):
        if text[pos]=='\\' and pos+1<len(text) and text[pos+1] in '{}[]%':pos+=2;continue
        if text[pos]==left:depth+=1
        if text[pos]==right:
            depth-=1
            if depth==0:return text[start:pos],pos+1
        pos+=1
    raise ValueError('Unclosed LaTeX group')


def environment(text,pos,name):
    pattern=re.compile(r'\\(begin|end)\{'+re.escape(name)+r'\}')
    first=pattern.match(text,pos);depth=1;cursor=first.end()
    for m in pattern.finditer(text,cursor):
        depth+=1 if m[1]=='begin' else -1
        if not depth:return text[cursor:m.start()],m.end()
    raise ValueError('Unclosed environment: '+name)


def render(text):
    """Return readable text plus prose-only text and unsupported macro names."""
    out=[];prose=[];warnings=[];i=0
    while i<len(text):
        if text.startswith('$$',i) or text.startswith(r'\[',i) or text.startswith(r'\(',i) or text[i]=='$':
            opening='$$' if text.startswith('$$',i) else r'\[' if text.startswith(r'\[',i) else r'\(' if text.startswith(r'\(',i) else '$'
            closing={r'\[':r'\]',r'\(':r'\)'}.get(opening,opening);end=text.find(closing,i+len(opening))
            if end<0:out.append('[UNRESOLVED_MATH '+text[i:]+']');warnings.append('unclosed_math');break
            raw=text[i:end+len(closing)];out.append(raw);prose.append(' ');i=end+len(closing);continue
        if text[i]=='\\':
            m=re.match(r'\\([A-Za-z@]+)\*?',text[i:])
            if not m:
                value=text[i+1:i+2];value=' ' if value in {'\\',',',';',':','!',' '} else value
                out.append(value);prose.append(value);i+=2;continue
            cmd=m[1];i+=m.end()
            while i<len(text) and text[i]=='[':_,i=group(text,i,'[',']')
            if cmd in {'cite','citet','citep','ref','eqref','autoref','pageref'}:
                arg,i=group(text,i);out.append(f"[{'CITE' if cmd.startswith('cite') else 'REF'}:{arg}]");prose.append(' ');continue
            if cmd in SKIP_ARGS:
                for _ in range(SKIP_ARGS[cmd]):
                    arg,end=group(text,i)
                    if arg is None:
                        token=re.match(r'\s*\\[A-Za-z@]+',text[i:]);i+=token.end() if token else 0
                    else:i=end
                continue
            if cmd in {'url','href'}:
                arg,i=group(text,i)
                if cmd=='href':arg,i=group(text,i)
                value=arg or '';out.append(value);prose.append(value);continue
            if cmd in FORMAT or cmd=='footnote':
                arg,end=group(text,i)
                if arg is not None:
                    a,b,w=render(arg);out.append(a);prose.append(b);warnings+=w;i=end
                else:warnings.append(cmd)
                continue
            if cmd in LAYOUT:out.append(' ');prose.append(' ');continue
            if cmd in {'begin','end'}:
                _,i=group(text,i);out.append(' ');prose.append(' ');continue
            arg,end=group(text,i)
            raw='\\'+cmd+('{'+arg+'}' if arg is not None else '')
            out.append('[UNRESOLVED '+raw+']');prose.append(' ');warnings.append(cmd)
            if arg is not None:i=end
            continue
        if text[i] in '{}':i+=1;continue
        value=' ' if text[i]=='~' else text[i];out.append(value);prose.append(value);i+=1
    clean=lambda s:re.sub(r'\s+',' ',''.join(s)).strip().replace('``','"').replace("''",'"').replace('--','–')
    return clean(out),clean(prose),sorted(set(warnings))


class Reader:
    def __init__(self,main,root=None):
        self.main=Path(main).resolve();self.root=Path(root).resolve() if root else self.main.parent
        if not self.main.is_relative_to(self.root):raise ValueError('Main source outside allowed project root')
        self.files=[];self.dependencies=[];self.blocks=[];self.warnings=[];self.active=set();self.env=Counter();self.section='Front matter';self.chapter='Front matter';self.title=None

    def resolve(self,parent,name):
        if any(c in name for c in ['\\','|','\x00','\n']):raise ValueError('Dynamic/command input path refused')
        path=(Path(parent).parent/name).resolve()
        if not path.suffix:path=path.with_suffix('.tex')
        if not path.is_relative_to(self.root) or path.suffix.lower() not in {'.tex','.bbl'}:raise ValueError('Dependency outside allowed source project/type')
        return path

    def block(self,kind,raw,path,start,end):
        if not raw.strip():return
        start+=raw[:len(raw)-len(raw.lstrip())].count('\n')
        text,prose,unknown=render(raw)
        if kind=='formula':text,prose,unknown=raw.strip(),'',[]
        if not text:return
        self.blocks.append({'paragraph_id':f't{len(self.blocks)+1:04d}','kind':kind,'section':self.section,'chapter':self.chapter,
            'text':text,'prose_text':prose if kind not in {'formula','table_context','figure_context','references','missing_dependency','biography','metadata','heading'} else '',
            'raw_tex':raw,'source_file':str(path),'source_line_start':start,'source_line_end':end,'unknown_macros':unknown})
        if unknown:self.warnings.append({'file':str(path),'line':start,'unknown_macros':unknown})

    def file(self,path,depth=0,body_only=False):
        path=Path(path).resolve()
        if depth>8 or len(self.files)>=32 or path in self.active:raise ValueError('Cyclic/excessive TeX include')
        if path.stat().st_size>3_000_000:raise ValueError('Source file too large for bounded reader')
        data=path.read_bytes();text=strip_comments(data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'));self.active.add(path)
        self.env.update(re.findall(r'\\begin\{([^}]+)\}',text))
        self.files.append({'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
        if body_only:
            m=re.search(r'\\begin\{document\}',text)
            if not m:raise ValueError('Main source has no document environment')
            text='\n'*text[:m.end()].count('\n')+text[m.end():]
        i=0;buffer=[];begin_line=1;role='prose';proof=[]
        line=lambda pos:text.count('\n',0,pos)+1
        def flush(pos):
            nonlocal buffer
            self.block(proof[-1] if proof and role=='prose' else role,''.join(buffer),path,begin_line,line(pos));buffer=[]
        while i<len(text):
            if re.match(r'\n[ \t]*\n',text[i:]):flush(i);i+=len(re.match(r'\n[ \t]*\n',text[i:])[0]);begin_line=line(i);continue
            if text[i]=='\\':
                m=re.match(r'\\([A-Za-z@]+)\*?',text[i:])
                if m:
                    cmd=m[1];end=i+m.end()
                    if cmd=='end' and text[end:].startswith('{document}'):flush(i);break
                    if cmd in {'input','include'}:
                        flush(i);arg,nextpos=group(text,end)
                        if arg is None:raise ValueError('Only literal braced input/include is supported')
                        target=self.resolve(path,arg);exists=target.is_file();self.dependencies.append({'from':str(path),'line':line(i),'path':str(target),'exists':exists})
                        if exists:self.file(target,depth+1)
                        else:self.block('missing_dependency',f'[MISSING_LOCAL_INPUT {target.name}]',path,line(i),line(nextpos))
                        i=nextpos;begin_line=line(i);continue
                    if cmd in {'section','subsection','subsubsection','paragraph'}:
                        flush(i);title,nextpos=group(text,end);name,_,_=render(title or '')
                        self.section=name
                        if cmd=='section':self.chapter=name
                        self.block('heading',title or '',path,line(i),line(nextpos));i=nextpos;begin_line=line(i);continue
                    if cmd=='title':
                        flush(i);title,i=group(text,end);self.title=render(title or '')[0];begin_line=line(i);continue
                    if cmd in META or cmd in {'bibliographystyle'}:
                        flush(i);pos=end
                        if pos<len(text) and text[pos]=='[':_,pos=group(text,pos,'[',']')
                        _,pos2=group(text,pos)
                        if cmd=='markboth':_,pos2=group(text,pos2)
                        if cmd=='titlepgskip' and pos2==pos:
                            pos2=text.find('\n',pos)
                            if pos2<0:pos2=len(text)
                        i=pos2;begin_line=line(i);continue
                    if cmd in {'ifdim','ifnum'}:
                        flush(i);match=re.search(r'\\fi\b',text[end:])
                        if not match:raise ValueError('Unclosed conditional; no execution attempted')
                        self.warnings.append({'file':str(path),'line':line(i),'note':'Conditional layout skipped without evaluation'})
                        i=end+match.end();begin_line=line(i);continue
                    if cmd=='begin':
                        name,pos=group(text,end)
                        if name=='minipage':
                            flush(i);_,i=group(text,pos);begin_line=line(i);continue
                        if name in {'abstract','abstract*'}:
                            flush(i);self.chapter=self.section='Abstract';role='abstract';i=pos;begin_line=line(i);continue
                        if name in MATH or name in FLOATS or name in {'keywords','thebibliography','IEEEbiography'}:
                            flush(i);content,nextpos=environment(text,i,name);kind='formula' if name in MATH else 'references' if name=='thebibliography' else 'biography' if name=='IEEEbiography' else 'metadata' if name=='keywords' else 'figure_context' if name.startswith('figure') else 'table_context'
                            if kind in {'figure_context','table_context'}:
                                cap=re.search(r'\\caption(?:\[[^]]*\])?\s*',content)
                                if cap:
                                    value,_=group(content,cap.end());capline=line(i)+content[:cap.start()].count('\n');self.block('caption',value or '',path,capline,capline+(value or '').count('\n'))
                                if 'Algorithm ' in content:kind='algorithm'
                            if kind=='formula':self.block(kind,'\\begin{'+name+'}'+content+'\\end{'+name+'}',path,line(i),line(nextpos))
                            else:self.block(kind,content,path,line(i),line(nextpos))
                            i=nextpos;begin_line=line(i);continue
                        if name in PROOF:flush(i);proof.append(name);i=pos;begin_line=line(i);continue
                    if cmd=='end':
                        name,pos=group(text,end)
                        if name in {'abstract','abstract*'}:flush(i);role='prose';i=pos;begin_line=line(i);continue
                        if name in PROOF:flush(i);proof.pop();i=pos;begin_line=line(i);continue
                    if cmd=='item':flush(i);i=end;begin_line=line(i);continue
                    if cmd=='appendix':flush(i);self.chapter=self.section='Appendix';i=end;begin_line=line(i);continue
                    if cmd in {'write','immediate','directlua','openout','read','catcode','special'}:
                        self.warnings.append({'file':str(path),'line':line(i),'note':'Potentially executable TeX command retained as data, never executed','command':cmd})
            buffer.append(text[i]);i+=1
        flush(i);self.active.remove(path)

    def read(self):
        self.file(self.main,body_only=True)
        return {'format':'tex-text-0.1.0','title':self.title,'source_files':self.files,'dependencies':self.dependencies,'blocks':self.blocks,
                'environment_counts':dict(self.env),'warnings':self.warnings,'execution':'No TeX compiler, macro execution, shell, image loading or network.'}
