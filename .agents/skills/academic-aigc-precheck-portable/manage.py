"""Local install/verify/uninstall. Never overwrite an existing Skill."""
import argparse,hashlib,json,shutil,sys,tempfile
from pathlib import Path,PurePosixPath
from zipfile import ZipFile
NAME='academic-aigc-precheck-portable'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(root,name):
    if not name or '\\' in name or ':' in name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:raise ValueError('Unsafe package path')
    p=(root/name).resolve()
    if not p.is_relative_to(root):raise ValueError('Path outside installation')
    return p
def verify_archive(bundle):
    if Path(bundle).stat().st_size>16*1024*1024:raise ValueError('Archive resource limit')
    with ZipFile(bundle) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)>100:raise ValueError('Duplicate/excessive archive members')
        if sum(i.file_size for i in z.infolist())>32*1024*1024:raise ValueError('Archive expansion limit')
        if any(i.orig_filename!=i.filename or i.file_size>8*1024*1024 or i.file_size/max(i.compress_size,1)>1000 or i.flag_bits&1 or (i.external_attr>>16)&0o170000==0o120000 for i in z.infolist()):raise ValueError('Invalid member resource/type')
        for n in names:checked(Path.cwd().resolve(),n)
        if 'MANIFEST.json' not in names:raise ValueError('Missing package manifest')
        m=json.loads(z.read('MANIFEST.json'))
        if m.get('release')!='RC1-DOCX-PORTABLE-0.1.0':raise ValueError('Wrong release')
        if set(names)!=set(m['files'])|{'MANIFEST.json'}:raise ValueError('Whitelist mismatch')
        data={n:z.read(n) for n in names}
        if any(hashlib.sha256(data[n]).hexdigest()!=h for n,h in m['files'].items()):raise ValueError('Package hash mismatch')
    return data
def install(bundle,dest):
    dest=Path(dest).resolve()
    if dest.name!=NAME:raise ValueError('Destination must end in '+NAME)
    if dest.exists():raise ValueError('Destination exists; never overwrite a Skill')
    data=verify_archive(bundle);dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.tap-install-',dir=dest.parent))
    try:
        for n,value in data.items():
            p=checked(stage,n);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
        footprint={'name':NAME,'bundle_sha256':sha(bundle),'files':{n:hashlib.sha256(v).hexdigest() for n,v in data.items()}}
        (stage/'.portable-install.json').write_text(json.dumps(footprint,indent=2),encoding='utf8')
        stage.rename(dest)
    except Exception:
        # Only this newly created staging path is eligible for cleanup.
        if stage.exists() and stage.resolve().parent==dest.parent:shutil.rmtree(stage)
        raise
    return {'installed':str(dest),'bundle_sha256':sha(bundle),'files':len(data)}
def verify(dest):
    dest=Path(dest).resolve()
    if dest.name!=NAME:raise ValueError('Unexpected installation name')
    marker=dest/'.portable-install.json'
    if not marker.is_file():raise ValueError('Not a managed installation')
    m=json.loads(marker.read_text(encoding='utf8'))
    expected=set(m['files'])|{'.portable-install.json'}
    actual={str(p.relative_to(dest)).replace('\\','/') for p in dest.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('Unexpected/missing install files; do not delete automatically')
    if any(sha(checked(dest,n))!=h for n,h in m['files'].items()):raise ValueError('Modified installation; refuse automatic removal')
    return m
def uninstall(dest):
    dest=Path(dest).resolve();m=verify(dest)
    for n in m['files']:checked(dest,n).unlink()
    (dest/'.portable-install.json').unlink()
    # Remove only verified empty subdirectories inside this exact managed root.
    for p in sorted((p for p in dest.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not p.resolve().is_relative_to(dest):raise ValueError('Unsafe directory')
        p.rmdir()
    dest.rmdir();return {'uninstalled':str(dest),'private_data_deleted':False}
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('install');a.add_argument('--bundle',required=True);a.add_argument('--dest',required=True)
    for n in ['verify','uninstall']:s.add_parser(n).add_argument('--dest',required=True)
    a=s.add_parser('check-bundle');a.add_argument('--bundle',required=True)
    a=p.parse_args()
    if a.command=='install':result=install(a.bundle,a.dest)
    elif a.command=='uninstall':result=uninstall(a.dest)
    elif a.command=='verify':result={'verified':str(Path(a.dest).resolve()),'files':len(verify(a.dest)['files'])}
    else:result={'verified_members':len(verify_archive(a.bundle)),'sha256':sha(a.bundle)}
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(2)
