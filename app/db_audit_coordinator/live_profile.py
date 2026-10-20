"""Root-owned local installation policy, not a host-budget approval protocol."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys

from . import contracts as c
from .live_policy import PROFILE,ROOT,SOCKET,StorePolicy,integer,path,require,R4_METHOD,R4_STORES
from .live_receipts import directory,identity

LEGACY=(
    '/home/admin/CaptivePortal-Deploy/qio-evidence-fast-start-3fda7af',
    '/home/admin/CaptivePortal-Deploy/qio-ram-audit-58db905',
)


@dataclass(frozen=True)
class R4Installation:
    method: str
    enabled: bool
    owner_uid: int
    owner_gid: int
    ram_root: str
    ram_device: int
    ram_inode: int
    task_limit: int
    nr_inodes: int

    def __post_init__(self):
        require(self.method==R4_METHOD and type(self.enabled) is bool)
        require(self.ram_root=='/run/captive-portal/db-audit/ram-jobs')
        integer(self.owner_uid,1,2**32-1);integer(self.owner_gid,1,2**32-1)
        integer(self.ram_device);integer(self.ram_inode,1)
        integer(self.task_limit,8,32);integer(self.nr_inodes,32,256)

    @classmethod
    def parse(cls,value):
        c.closed(value,cls.__dataclass_fields__);return cls(**value)


@dataclass(frozen=True)
class PilotProfile:
    schema: str
    enabled: bool
    root: str
    socket: str
    release_root: str
    commit: str
    tree: str
    python: str
    python_sha256: str
    blobs: tuple[tuple[str,str],...]
    delegated: str
    delegated_device: int
    delegated_inode: int
    worker_uid: int
    worker_gid: int
    worker_groups: tuple[int,...]
    operator_uids: tuple[int,...]
    operator_gid: int
    stores: tuple[StorePolicy,...]
    r4: R4Installation | None = None

    def __post_init__(self):
        require(self.schema=='db_audit_coordinator.pilot.v1' and type(self.enabled) is bool)
        for value in (self.root,self.socket,self.release_root,self.python,self.delegated): path(value)
        require(self.delegated!='/' and self.delegated.count('/')>=2)
        for digest in (self.commit,self.tree):
            require(type(digest) is str and len(digest)==40 and all(ch in '0123456789abcdef' for ch in digest))
        c.digest(self.python_sha256); integer(self.delegated_device); integer(self.delegated_inode,1)
        for value in (self.worker_uid,self.worker_gid,self.operator_gid):integer(value,1,2**32-1)
        require(type(self.worker_groups) is tuple and len(self.worker_groups)<=8 and len(set(self.worker_groups))==len(self.worker_groups))
        for value in self.worker_groups:integer(value,1,2**32-1)
        require(type(self.operator_uids) is tuple and 1<=len(self.operator_uids)<=8
            and len(set(self.operator_uids))==len(self.operator_uids))
        for uid in self.operator_uids:integer(uid,1,2**32-1);require(uid!=self.worker_uid)
        require(type(self.blobs) is tuple and 1<=len(self.blobs)<=4096)
        names=[]
        for name,digest in self.blobs:
            require(type(name) is str and name.startswith('app/') and '..' not in Path(name).parts and name.endswith('.py'))
            c.digest(digest);names.append(name)
        require(names==sorted(set(names)))
        require(type(self.stores) is tuple and len(self.stores)==3 and all(type(item) is StorePolicy for item in self.stores))
        require({item.store_id for item in self.stores}=={'network_service_intelligence','public_traffic','traffic_projection'})
        for item in self.stores: require(item.uid!=self.worker_uid)
        require(self.r4 is None or type(self.r4) is R4Installation)
        if self.r4 is not None:
            require(self.r4.owner_uid!=self.worker_uid
                and all((item.uid,item.gid)==(self.r4.owner_uid,self.r4.owner_gid) for item in self.stores))

    @classmethod
    def parse(cls,value):
        # Historical root profiles remain readable with no implicit R4 grant.
        keys=set(cls.__dataclass_fields__)
        c.closed(value,keys if 'r4' in value else keys-{'r4'});data=dict(value)
        data['r4']=None if value.get('r4') is None else R4Installation.parse(value['r4'])
        for key in ('worker_groups','operator_uids'):
            require(type(data[key]) is list and len(data[key])<=8);data[key]=tuple(data[key])
        require(type(data['blobs']) is list and len(data['blobs'])<=4096)
        require(all(type(item) is list and len(item)==2 for item in data['blobs']))
        data['blobs']=tuple(tuple(item) for item in data['blobs'])
        require(type(data['stores']) is list and len(data['stores'])==3)
        data['stores']=tuple(StorePolicy.parse(item) for item in data['stores'])
        return cls(**data)

    def store(self,store_id):
        value=next((item for item in self.stores if item.store_id==store_id),None)
        require(value is not None);return value

    def metadata(self,store_id):
        metadata=self.store(store_id).metadata()
        if self.r4 is not None and self.r4.enabled:
            require(store_id in R4_STORES)
            return R4_METHOD,metadata[1],metadata[2]
        return metadata

    def artifact(self):
        """Bounded code-byte checks, not DB/source geometry or an audit."""
        fd=directory(self.release_root,uid=0)
        try:
            require(os.fstat(fd).st_uid==0 and not os.fstat(fd).st_mode & 0o022)
            for name,digest in self.blobs:
                target=Path(self.release_root)/name
                parent=directory(str(target.parent),uid=0);os.close(parent)
                info=target.lstat()
                require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode & 0o022)
                opened=os.open(target,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    require(identity(info)==identity(os.fstat(opened)) and info.st_size<=2*1024**2)
                    data=bytearray()
                    while len(data)<=2*1024**2:
                        block=os.read(opened,65536)
                        if not block:break
                        data.extend(block)
                    require(hashlib.sha256(data).hexdigest()==digest)
                finally:os.close(opened)
            actual=[]
            for parent,dirs,files in os.walk(Path(self.release_root)/'app',followlinks=False):
                require(not any((Path(parent)/name).is_symlink() for name in dirs))
                require('__pycache__' not in dirs and not any(name.endswith(('.pyc','.pyo')) for name in files))
                for name in files:
                    if name.endswith('.py'):actual.append(str((Path(parent)/name).relative_to(self.release_root)))
            require(sorted(actual)==[name for name,_ in self.blobs])
            # No hooks/config writes; immutable release has no optional index lock.
            env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','GIT_CONFIG_NOSYSTEM':'1'}
            def git(*args):
                return subprocess.run(['/usr/bin/git','--no-optional-locks','-c','safe.directory='+self.release_root,
                    '-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-c','core.untrackedCache=false',
                    *args],cwd=self.release_root,env=env,capture_output=True,check=True,timeout=5).stdout.decode().strip()
            git_dir=Path(git('rev-parse','--absolute-git-dir'))
            common=Path(git('rev-parse','--git-common-dir'))
            if not common.is_absolute():common=Path(self.release_root)/common
            for location in (git_dir.resolve(),common.resolve()):
                meta=directory(str(location),uid=0);os.close(meta)
            require(git('rev-parse','HEAD')==self.commit and git('rev-parse','HEAD^{tree}')==self.tree)
            require(git('status','--porcelain','--untracked-files=no')=='')
            python=Path(self.python)
            # The policy names the qualified canonical binary, not a mutable
            # alternative symlink/venv dispatcher controlled by the operator.
            require(python.resolve()==python)
            parent=directory(str(python.parent),uid=0);os.close(parent)
            info=python.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode & 0o022)
            with python.open('rb') as stream:
                digest=hashlib.sha256()
                while block:=stream.read(65536):digest.update(block)
            require(digest.hexdigest()==self.python_sha256)
        finally:os.close(fd)

    def installed(self):
        require(os.name=='posix' and os.geteuid()==0 and self.enabled)
        require(self.root==ROOT and self.socket==SOCKET)
        require(Path(__file__).resolve().parents[2]==Path(self.release_root) and Path.cwd()==Path(self.release_root)
            and Path(sys.executable).resolve()==Path(self.python),'not_admitted')
        self.artifact()
        if self.r4 is not None and self.r4.enabled:
            fd=directory(self.r4.ram_root,uid=0,expected=(self.r4.ram_device,self.r4.ram_inode))
            try:require(os.fstat(fd).st_uid==0 and stat.S_IMODE(os.fstat(fd).st_mode)==0o711)
            finally:os.close(fd)
        # Code verifies the two KNOWN quarantines, but the complete old-launch
        # inventory and attended external host gate are operator obligations.
        for value in LEGACY:
            info=Path(value).lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o700)


def load_profile():
    """Only the fixed pre-installed root policy; no CLI path/env override."""
    location=Path(PROFILE);fd=directory(str(location.parent),uid=0)
    try:
        before=location.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and before.st_nlink==1 and not before.st_mode & 0o022)
        opened=os.open(location,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            require(identity(before)==identity(os.fstat(opened)))
            raw=os.read(opened,c.MAX_BYTES+1);require(len(raw)<=c.MAX_BYTES)
        finally:os.close(opened)
    finally:os.close(fd)
    profile=PilotProfile.parse(c.decode(raw))
    profile.installed()
    return profile
