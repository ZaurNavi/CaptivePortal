"""One-use trusted bootstrap -> sandboxed source-owner BACKUP ONLY.

No general source selector, queue writer, T3, heavy-lock FD or ENV configuration.
The root bootstrap consumes a sealed private parent capability before dropping
all privilege. The resulting owner sees only three read-only source bindings
and its write-only private staging directory, no host root/proc/source alias.
"""
import os
import select
from pathlib import Path
import socket
import sqlite3
import stat
import sys
import time

from . import contracts as c
from .child_bootstrap import readonly_document,verify_parent
from .live_policy import require,integer,state,R4_METHOD,R4_STORES
from .live_profile import PilotProfile
from .live_receipts import identity,directory
from .r4_sandbox import drop_owner,RAM_ROOT,TMPFS_MAGIC
from . import r4_ipc

KEYS={'profile','queue','job_id','binding','root','namespace','leaf','parent_pid','parent_start',
    'deadline_ns','channel_fd','source_identities'}


def import_roots():
    """Root bootstrap cannot use os.access(W_OK): root can write root files.

    Check protected ownership/modes before entering the closed owner chroot.
    Dependencies must have already been independently qualified by SysAdmin.
    """
    for entry in sys.path:
        target=Path(entry or os.getcwd()).resolve()
        parent=target if target.is_dir() else target.parent
        fd=directory(str(parent),uid=0);os.close(fd)
        if target.exists():
            info=target.stat();require(info.st_uid==0 and not info.st_mode&0o022,'unsafe_path')


def run(auth_fd):
    require(os.name=='posix' and os.geteuid()==0,'unauthorized')
    document=readonly_document(auth_fd,sealed=True);os.close(auth_fd);c.closed(document,KEYS)
    profile=PilotProfile.parse(document['profile']);queue=state(document['queue'])
    job=next((item for item in queue['jobs'] if item['job_id']==document['job_id']),None)
    require(job is not None and job['state']=='running' and job['method_version']==R4_METHOD
        and job['claim_epoch']==queue['controller_epoch'] and job['store_id'] in R4_STORES,'unauthorized')
    require(profile.r4 is not None and profile.r4.enabled,'unauthorized')
    policy=profile.store(job['store_id']);c.digest(document['binding'])
    require((policy.uid,policy.gid)==(profile.r4.owner_uid,profile.r4.owner_gid),'unauthorized')
    verify_parent(document['parent_pid'],document['parent_start'])
    root=RAM_ROOT+'/'+job['claim_epoch']+'/'+job['attempt_id']
    require(document['root']==root and list(identity(os.stat('/proc/self/ns/mnt')))==document['namespace'],'unauthorized')
    require(Path(__file__).resolve().parents[2]==Path(profile.release_root)
        and Path.cwd()==Path(profile.release_root)
        and Path(sys.executable).resolve()==Path(profile.python).resolve(),'unauthorized')
    profile.artifact()
    import_roots()
    integer(document['channel_fd'],3,2**20);integer(document['deadline_ns'],1)
    channel=socket.socket(fileno=document['channel_fd'])
    # Regular self receipts cannot fchdir out of chroot. No /proc directory,
    # original source FD, mount namespace FD or parent root FD is inherited.
    receipts={name:os.open('/proc/self/'+name,os.O_RDONLY|os.O_CLOEXEC) for name in ('status','cgroup')}
    require(channel.family==socket.AF_UNIX and channel.type&socket.SOCK_SEQPACKET,'unauthorized')
    def left():
        remaining=(document['deadline_ns']-time.monotonic_ns())/1e9
        require(remaining>0,'not_admitted');return remaining
    for item in os.listdir('/proc/self/fd'):
        fd=int(item)
        if fd>2 and fd not in {*receipts.values(),channel.fileno()}:
            try:os.close(fd)
            except OSError:pass
    os.chroot(root+'/owner-root');os.chdir('/')
    drop_owner(policy.uid,policy.gid)
    def receipt(name):
        fd=receipts[name];os.lseek(fd,0,os.SEEK_SET);return os.read(fd,16384).decode('ascii')
    status=receipt('status');caps=[line.split()[1] for line in status.splitlines()
        if line.startswith(('CapInh:','CapPrm:','CapEff:','CapBnd:','CapAmb:'))]
    require(len(caps)==5 and all(int(value,16)==0 for value in caps) and 'NoNewPrivs:\t1' in status,'unauthorized')
    require(receipt('cgroup').strip()=='0::'+document['leaf'] and not Path('/proc').exists(),'unauthorized')
    for fd in receipts.values():os.close(fd)
    r4_ipc.send(channel,'owner_ready',document['binding'],dict(pid=os.getpid()),seconds=min(left(),1))
    kind,payload,fd=r4_ipc.receive(channel,document['binding'],0,document['parent_pid'],seconds=left())
    require(kind=='begin' and payload=={} and fd is None,'unauthorized')
    source=destination=None;complete=False;steps=0
    try:
        def guard():
            left()
            if select.select([channel],[],[],0)[0]:
                kind,payload,fd=r4_ipc.receive(channel,document['binding'],0,document['parent_pid'],seconds=min(left(),1))
                require(kind=='cancel' and payload=={} and fd is None,'unauthorized')
                raise c.CoordinatorError('canceled')
            for kind,expected in document['source_identities'].items():
                suffix={'main':'','wal':'-wal','shm':'-shm'}[kind]
                info=os.stat('/source/input.sqlite3'+suffix,follow_symlinks=False)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink==1
                    and list(identity(info))==expected,'unsafe_path')
                require(not os.access('/source/input.sqlite3'+suffix,os.W_OK,effective_ids=True),'unsafe_path')
        guard()
        require(not os.access('/source',os.W_OK,effective_ids=True),'unsafe_path')
        source=sqlite3.connect('file:/source/input.sqlite3?mode=ro',uri=True,timeout=0,isolation_level=None)
        source.execute('PRAGMA query_only=ON');source.execute('PRAGMA busy_timeout=0')
        require(source.execute('PRAGMA user_version').fetchone()[0]==policy.schema_version,'not_admitted')
        size=source.execute('PRAGMA page_size').fetchone()[0];count=source.execute('PRAGMA page_count').fetchone()[0]
        integer(size,512,65536);integer(count,1)
        require(size*count<=policy.image_max_bytes,'not_admitted')
        destination=sqlite3.connect('/stage/snapshot.sqlite3',isolation_level=None,timeout=0)
        def progress(code,remaining,total):
            nonlocal complete,steps
            guard();steps+=1
            require(steps<=100000 and code in {0,101} and 0<=remaining<=total
                and 0<total*size<=policy.image_max_bytes,'not_admitted')
            complete=code==101 and remaining==0
        source.backup(destination,pages=128,progress=progress,sleep=0)
        require(complete,'not_admitted');guard()
        destination.close();destination=None;source.close();source=None
        r4_ipc.send(channel,'owner_done',document['binding'],dict(complete=True,page_size=size),seconds=min(left(),1))
        return 0
    finally:
        if destination is not None:destination.close()
        if source is not None:source.close()
        channel.close()


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=1 or not args[0].isascii() or not args[0].isdecimal():return 2
    try:return run(int(args[0]))
    except Exception:return 3  # Never emit raw source, nonce, credential or traceback.


if __name__=='__main__':raise SystemExit(main())
