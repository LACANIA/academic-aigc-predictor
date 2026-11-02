"""Bounded static OOXML reader. No Word automation, extraction, or network IO."""
from collections import Counter
import hashlib
import base64
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile, ZIP_STORED, ZIP_DEFLATED

W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M='{http://schemas.openxmlformats.org/officeDocument/2006/math}'
REL='{http://schemas.openxmlformats.org/package/2006/relationships}'
MAX_ARCHIVE=64*1024*1024
MAX_MEMBER=32*1024*1024
MAX_TOTAL=128*1024*1024
MAX_XML=8*1024*1024
MAX_ENTRIES=4096
STATEMENTS=re.compile(r'acknow|funding|(?:AI|artificial intelligence)[ -]?(?:use|assist)|assisted preparation|availability|declarations|contributions|competing interests|conflict of interest',re.I)
HEADINGS={'abstract','introduction','discussion','conclusion','conclusions','references','bibliography',
 'keywords','acknowledgments','acknowledgements','funding','statements and declarations','declarations',
 'data availability','code availability','author contributions','conflict of interest','competing interests',
 'author biographies','biographies','appendix','appendices','ai-assisted preparation','ai use statement'}

def xml_parse(data):
    # Null removal also detects UTF16/32 DTD declarations; no external entities.
    if len(data)>MAX_XML:raise ValueError('DOCX_XML_LIMIT: XML resource too large')
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)',data.replace(b'\x00',b''),re.I):raise ValueError('DOCX_XML_DTD: declarations forbidden')
    try:root=ET.fromstring(data)
    except ET.ParseError as e:raise ValueError('DOCX_XML_INVALID: '+str(e)) from e
    stack=[(root,0)];count=0
    while stack:
        node,depth=stack.pop();count+=1
        if depth>128 or count>200000:raise ValueError('DOCX_XML_LIMIT: excessive nesting/elements')
        stack.extend((c,depth+1) for c in node)
    return root

def visible(node,math=True):
    if node.tag in {W+'del',W+'instrText',W+'delText',W+'moveFrom'}:return ''
    if node.tag==M+'oMath' and not math:return ''
    if node.tag in {W+'t',M+'t'}:return node.text or ''
    if node.tag==W+'tab':return '\t'
    if node.tag in {W+'br',W+'cr'}:return '\n'
    return ''.join(visible(c,math) for c in node)

def math_text(node):
    """Readable hints only; preserve XML as evidence, never assert equivalence."""
    if node is None:return ''
    def part(name):return math_text(node.find(M+name))
    if node.tag==M+'t':return node.text or ''
    if node.tag==M+'f':return '('+part('num')+')/('+part('den')+')'
    if node.tag==M+'sSup':return part('e')+'^('+part('sup')+')'
    if node.tag==M+'sSub':return part('e')+'_('+part('sub')+')'
    if node.tag==M+'sSubSup':return part('e')+'_('+part('sub')+')^('+part('sup')+')'
    if node.tag==M+'rad':return 'root['+(part('deg') or '2')+']('+part('e')+')'
    if node.tag in {M+'eqArr',M+'mr'}:return ' ; '.join(math_text(c) for c in node if not c.tag.endswith('Pr'))
    if node.tag==M+'m':return 'matrix['+' ; '.join(math_text(c) for c in node.findall(M+'mr'))+']'
    if node.tag.endswith('Pr'):return ''
    return ''.join(math_text(c) for c in node)

def normalized(text):return re.sub(r'\s+',' ',text).strip()

class Reader:
    def __init__(self,path):self.path=Path(path)

    def read(self):
        if self.path.suffix.lower()!='.docx':raise ValueError('DOCX_EXTENSION: only .docx supported')
        if not self.path.is_file():raise FileNotFoundError('DOCX missing: '+str(self.path))
        if self.path.stat().st_size>MAX_ARCHIVE:raise ValueError('DOCX_ARCHIVE_LIMIT: compressed file too large')
        try:
            with ZipFile(self.path) as z:return self._read(z)
        except (BadZipFile,RuntimeError,NotImplementedError,OSError) as e:raise ValueError('DOCX_PACKAGE_INVALID: '+str(e)) from e

    def _read(self,z):
        infos=z.infolist();names=[x.filename for x in infos]
        if len(infos)>MAX_ENTRIES or len(set(names))!=len(names):raise ValueError('DOCX_PACKAGE_LIMIT: too many/duplicate members')
        total=0
        for i in infos:
            path=PurePosixPath(i.filename)
            # ZipInfo normalizes backslashes on Windows. Inspect original header
            # names too, before relying on its normalized filename.
            if i.orig_filename!=i.filename or not i.filename or '\\' in i.orig_filename or ':' in i.filename or path.is_absolute() or '..' in path.parts:
                raise ValueError('DOCX_PATH: unsafe package member')
            if i.flag_bits&1 or (i.external_attr>>16)&0o170000==0o120000:raise ValueError('DOCX_PACKAGE_UNSUPPORTED: encrypted/symlink member')
            if i.compress_type not in {ZIP_STORED,ZIP_DEFLATED}:raise ValueError('DOCX_PACKAGE_UNSUPPORTED: compression')
            total+=i.file_size
            if i.file_size>MAX_MEMBER or total>MAX_TOTAL or i.file_size/max(i.compress_size,1)>1000:
                raise ValueError('DOCX_PACKAGE_LIMIT: resource/expansion limit')
            if 'vbaproject' in i.filename.lower():raise ValueError('DOCX_MACRO: macro package refused')
        for name in ['[Content_Types].xml','word/document.xml']:
            if name not in names:raise ValueError('DOCX_MISSING_PART: '+name)
        accessed=[]
        def get(name):
            info=z.getinfo(name)
            if info.file_size>MAX_XML:raise ValueError('DOCX_XML_LIMIT: '+name)
            data=z.read(name);accessed.append(name);return data,xml_parse(data)
        _,ct=get('[Content_Types].xml')
        if any('macroenabled' in str(v).lower() for n in ct.iter() for v in n.attrib.values()):raise ValueError('DOCX_MACRO: macro content type refused')
        data,root=get('word/document.xml');body=root.find(W+'body')
        if body is None:raise ValueError('DOCX_MISSING_BODY')
        warnings=[];styles={};style_levels={}
        if 'word/styles.xml' in names:
            _,sr=get('word/styles.xml')
            for s in sr.findall(W+'style'):
                sid=s.get(W+'styleId');name=s.find(W+'name');level=s.find(W+'pPr/'+W+'outlineLvl')
                styles[sid]=name.get(W+'val','') if name is not None else sid
                if level is not None:style_levels[sid]=int(level.get(W+'val','9'))
        if 'word/_rels/document.xml.rels' in names:
            _,rels=get('word/_rels/document.xml.rels')
            external=sum(r.get('TargetMode')=='External' for r in rels)
            if external:warnings.append(f'{external} external relationships recorded but never followed.')
        for n in ['word/footnotes.xml','word/endnotes.xml']:
            if n in names: warnings.append(n+' retained as separate note context after body; not paginated.')
        for feature,tag in [('tracked deletions',W+'del'),('tracked insertions',W+'ins'),('embedded objects',W+'object'),('alternate imported content',W+'altChunk')]:
            count=sum(1 for _ in root.iter(tag))
            if count:warnings.append(f'{count} {feature}; no execution; deletions excluded, insertions visible, embedded/imported content not rendered.')
        source_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        blocks=[];raw=[];tables=[];maths=[];index=0;section='Front matter';reference=False;biography=False
        def consume(p,table=None,part='word/document.xml'):
            nonlocal index,section,reference,biography
            index+=1;pid=f'w{index:04d}';original=visible(p).strip();plain=visible(p,False).strip()
            raw.append({'block_id':pid,'paragraph_index':index,'source_part':part,'xml':ET.tostring(p,encoding='unicode')})
            if not original:return None
            props=p.find(W+'pPr');st=p.find(W+'pPr/'+W+'pStyle');sid=st.get(W+'val','') if st is not None else ''
            style=styles.get(sid,sid);low=normalized(original).lower().rstrip(':');ew=[]
            ms=[]
            for node in p.iter(M+'oMath'):
                rec={'math_id':f'm{len(maths)+1:04d}','block_id':pid,'paragraph_index':index,
                  'source_part':part,'table_position':table,'original_text':visible(node),
                  'readable_text':math_text(node),'omml_xml':ET.tostring(node,encoding='unicode'),
                  'semantic_equivalence_verified':False,'warning':'OMML linear/structural hint may lose grouping, operators, accents and layout; XML retained.'}
                maths.append(rec);ms.append(rec['math_id'])
            if ms:ew.append('OMML representation is a reading hint, not certified mathematical equivalence.')
            if p.find('.//'+W+'drawing') is not None:ew.append('Drawing/image contents not OCRed or rendered; only available document text retained.')
            if part!='word/document.xml':kind='note_context'
            elif table:kind='table_context'
            elif not blocks:kind='title'
            elif re.search(r'heading|标题',style,re.I) or low in HEADINGS or sid in style_levels and style_levels[sid]<9:
                kind='heading';section=original
                if low in {'references','bibliography'}:reference=True;biography=False
                elif re.search(r'biograph',low):reference=False;biography=True
                else:reference=False;biography=False
            elif re.search(r'caption|题注',style,re.I) or re.match(r'^(?:Fig\.?|Figure|Table)\s+\d+',original) and len(original.split())<120:kind='caption'
            elif biography:kind='biography'
            elif reference:kind='references'
            elif low.startswith(('keywords:','keywords ','key words:')):kind='keywords'
            elif ms and not re.search(r'[A-Za-z]{3,}',plain):kind='formula'
            elif section=='Front matter':kind='metadata'
            elif not re.search(r'[A-Za-z]{3,}',original):kind='formula'
            elif STATEMENTS.search(section):kind='statement'
            elif section.lower()=='abstract':kind='abstract'
            elif props is not None and props.find(W+'numPr') is not None:kind='list_context'
            else:kind='prose'
            norm=normalized(original)
            blocks.append({'block_id':pid,'paragraph_id':pid,'paragraph_index':index,'source_paragraph_index':index,
              'source_file':self.path.name,'source_hash':source_hash,'source_part':part,'source_type':'docx_ooxml',
              'kind':kind,'chapter':section,'section':section,'original_text':original,'normalized_text':norm,'text':norm,
              'style':style,'table_position':table,'math_ids':ms,'pdf_pages':[],
              'extraction_warnings':ew,'analysis_scope':'body_candidate' if kind in {'abstract','prose'} else 'separate_eligibility_or_context'})
            return pid
        def walk(parent,table=None,part='word/document.xml'):
            for c in parent:
                if c.tag==W+'p':consume(c,table,part)
                elif c.tag==W+'tbl':walk_table(c,table,part)
                elif c.tag in {W+'sdt',W+'sdtContent',W+'customXml',W+'ins'}:walk(c,table,part)
                elif c.tag not in {W+'sectPr',W+'tblPr',W+'tblGrid',W+'tcPr',W+'trPr',W+'sdtPr'}:
                    warnings.append('Skipped unsupported body container '+c.tag+'; original document XML retained.')
        def walk_table(node,parent_table,part):
            table={'table_id':f'table{len(tables)+1}','parent_position':parent_table,'rows':[]};tables.append(table)
            # row/cell order and grid span preserved; no paragraph-as-table counting.
            for ri,row in enumerate(node.findall(W+'tr'),1):
                cells=[];col=1
                for cell in row.findall(W+'tc'):
                    span=cell.find(W+'tcPr/'+W+'gridSpan');width=int(span.get(W+'val','1')) if span is not None else 1
                    vm=cell.find(W+'tcPr/'+W+'vMerge');pos={'table_id':table['table_id'],'row':ri,'column':col,'grid_span':width,
                       'vertical_merge':vm.get(W+'val','continue') if vm is not None else None}
                    before=len(blocks);walk(cell,pos,part)
                    cells.append(dict(pos,block_ids=[b['block_id'] for b in blocks[before:]]));col+=width
                table['rows'].append({'row':ri,'cells':cells})
        walk(body)
        body_visited=index
        for name in ['word/footnotes.xml','word/endnotes.xml']:
            if name in names:
                _,notes=get(name)
                for note in notes:
                    if int(note.get(W+'id','0'))>=0:walk(note,part=name)
        if not blocks:raise ValueError('DOCX_NO_TEXT: no readable manuscript text')
        role_counts=dict(Counter(b['kind'] for b in blocks))
        return {'source_path':str(self.path.resolve()),'source_hash':source_hash,'source_bytes':self.path.stat().st_size,
          'title':next((b['text'] for b in blocks if b['kind']=='title'),None),'blocks':blocks,
          'tables':tables,'math_objects':maths,'raw_paragraphs':raw,
          'document_xml_base64':base64.b64encode(data).decode('ascii'),
          'diagnostics':{'body_paragraphs_visited':body_visited,'nonempty_records':len(blocks),'table_count':len(tables),
            'table_paragraph_count':sum(b['kind']=='table_context' for b in blocks),'OMML_equations':len(maths),
            'drawing_count':len(list(root.iter(W+'drawing'))),'role_counts':role_counts,
            'read_zip_members':accessed,'package_members':len(infos),'uncompressed_bytes':total},
          'warnings':warnings+['Static OOXML order is not rendered layout. No reliable PDF pagination, image OCR, remote link/template loading, macro execution or embedded-object evaluation.',
            'Per-object XML is namespace-normalized serialization; original document.xml is retained separately for byte evidence.']}
