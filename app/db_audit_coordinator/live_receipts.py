"""Direct LOCAL kernel receipts. No host/hypervisor telemetry or remote I/O."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
try:
    import resource
except ImportError:  # Pure policy/parser tests remain importable on Windows.
    resource = None
import stat
import time

from . import contracts as c
from .cgroup_v2 import meminfo, pressure, vmstat, counters, EVENTS
from .live_policy import integer, path, require

CGROUP2_SUPER_MAGIC=0x63677270


def filesystem_magic(fd):
    buffer=ctypes.create_string_buffer(256)
    function=ctypes.CDLL(None,use_errno=True).fstatfs
    require(function(fd,ctypes.byref(buffer))==0)
    return ctypes.c_long.from_buffer(buffer).value


def identity(info):
    return info.st_dev,info.st_ino


def directory(value, *, uid=0, expected=None, search_only=False):
    path(value); target=Path(value)
    for parent in (target,*target.parents):
        info=parent.lstat()
        sticky=info.st_uid==0 and info.st_mode & stat.S_ISVTX
        require(stat.S_ISDIR(info.st_mode) and info.st_uid in {0,uid}
            and (not info.st_mode & 0o022 or sticky), 'unsafe_path')
    before=target.lstat()
    access=os.O_PATH if search_only else os.O_RDONLY
    fd=os.open(target,access|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        require(identity(before)==identity(os.fstat(fd)) and (expected is None or identity(before)==tuple(expected)), 'unsafe_path')
        return fd
    except Exception:
        os.close(fd); raise


def read_at(fd, name, *, maximum=65536, optional=False, trusted_uid=None):
    require(type(name) is str and '/' not in name and name not in {'','.','..'})
    opened=None
    try:
        before=os.stat(name,dir_fd=fd,follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode), 'unsafe_path')
        if trusted_uid is not None:
            require(before.st_uid==trusted_uid and not before.st_mode & 0o022,'unsafe_path')
        opened=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
        require(identity(before)==identity(os.fstat(opened)), 'unsafe_path')
        raw=bytearray()
        while len(raw)<=maximum:
            block=os.read(opened,min(16384,maximum+1-len(raw)))
            if not block: break
            raw.extend(block)
        require(len(raw)<=maximum and identity(os.stat(name,dir_fd=fd,follow_symlinks=False))==identity(before), 'unsafe_path')
        return bytes(raw).decode('ascii')
    except FileNotFoundError:
        if optional: return None
        raise c.CoordinatorError('not_admitted') from None
    finally:
        if opened is not None: os.close(opened)


def proc_text(pid, name):
    integer(pid,1,2**31-1)
    location='/proc/'+str(pid)
    fd=directory(location,uid=os.stat(location,follow_symlinks=False).st_uid)
    try:return read_at(fd,name)
    finally:os.close(fd)


def start_ticks(pid):
    raw=proc_text(pid,'stat')
    require(raw.split(' ',1)[0]==str(pid))
    fields=raw.rsplit(') ',1)[1].split()
    require(len(fields)>=22)
    return integer(int(fields[19]),1)


def membership(pid):
    lines=proc_text(pid,'cgroup').splitlines()
    require(len(lines)==1 and lines[0].startswith('0::'))
    value=lines[0][3:]; path(value); return value


@dataclass(frozen=True)
class Node:
    location: str
    identity: tuple[int,int]
    maximum: int | None
    current: int | None
    swap_max: int | None
    swap_current: int | None
    events: tuple[tuple[str,int], ...] | None
    psi: tuple | None
    populated: int | None
    procs: tuple[int,...]
    root_controls: str


def parse_node(location, node_identity, values, *, root=False):
    """Pure native-layout parser; root absence is NOT a fabricated limit."""
    path(location)
    require(type(root) is bool and (not root or location=='/'))
    require(type(node_identity) is tuple and len(node_identity)==2)
    integer(node_identity[0]);integer(node_identity[1],1)
    def number(value):
        require(type(value) is str and value.strip().isascii() and value.strip().isdecimal())
        return integer(int(value.strip()))
    def limit(value): return None if value is not None and value.strip()=='max' else number(value)
    fields=('memory.max','memory.current','memory.swap.max','memory.swap.current','memory.events','memory.pressure')
    absent=[values.get(key) is None for key in fields]
    if root and all(absent):
        return Node(location,node_identity,None,None,None,None,None,None,None,(),'ROOT_CONTROL_NOT_EXPOSED')
    require(not any(absent))
    maximum=limit(values['memory.max']); current=number(values['memory.current'])
    swap_max=limit(values['memory.swap.max']); swap_current=number(values['memory.swap.current'])
    require((maximum is None or current<=maximum) and (swap_max is None or swap_current<=swap_max))
    events=tuple(sorted(counters(values['memory.events'],EVENTS,{'oom_group_kill'}).items()))
    psi=tuple(sorted(pressure(values['memory.pressure']).items()))
    group=counters(values['cgroup.events'],{'populated','frozen'})
    require(group['populated'] in {0,1} and group['frozen']==0)
    procs=tuple(number(value) for value in values['cgroup.procs'].splitlines())
    require(len(procs)<=128 and len(procs)==len(set(procs)) and all(value>0 for value in procs))
    require(group['populated']==1 or not procs)
    return Node(location,node_identity,maximum,current,swap_max,swap_current,events,psi,
        group['populated'],procs,'EXPORTED')


@dataclass(frozen=True)
class LocalSample:
    captured_ns: int
    nodes: tuple[Node,...]
    guest_available: int
    guest_vm_counters: tuple[int,...]
    guest_pressure: tuple
    rss: int
    address_headroom: int | None
    scope: str = 'guest_vm_only'

    def check(self, previous=None):
        require(self.scope=='guest_vm_only' and bool(self.nodes))
        leaf=self.nodes[-1]
        require(leaf.root_controls=='EXPORTED' and leaf.maximum is not None and leaf.maximum>0
            and leaf.swap_max==0 and leaf.swap_current==0)
        require(all(value==0 for _,value in leaf.events))
        require(all(not values[0] for _,values in self.guest_pressure))
        for node in self.nodes:
            if node.root_controls=='ROOT_CONTROL_NOT_EXPOSED':
                require(node.location=='/'); continue
            require(node.swap_current==0 and node.psi is not None and all(not values[0] for _,values in node.psi))
        if previous is not None:
            require(self.captured_ns>=previous.captured_ns and len(self.nodes)==len(previous.nodes))
            for old,new in zip(previous.nodes,self.nodes):
                require((old.location,old.identity,old.maximum,old.swap_max,old.root_controls)==
                    (new.location,new.identity,new.maximum,new.swap_max,new.root_controls), 'unsafe_path')
                require(old.events==new.events and old.psi==new.psi)
            require(self.guest_vm_counters==previous.guest_vm_counters and self.guest_pressure==previous.guest_pressure)

    def admit(self, policy, image, wal):
        self.check(); integer(image,1); integer(wal)
        require(image<=policy.image_max_bytes and wal<=policy.wal_max_bytes)
        budget=image+wal+policy.backup_overhead_bytes+policy.validator_overhead_bytes+policy.margin_bytes
        require(budget<policy.memory_max_bytes and budget+policy.guest_reserve_bytes<self.guest_available)
        for node in self.nodes:
            if node.maximum is not None:
                require(node.current is not None and budget<node.maximum-node.current)
        if self.address_headroom is not None: require(budget<self.address_headroom)
        return budget


def guest_sample(nodes):
    require(resource is not None and os.name=='posix')
    proc=directory('/proc')
    try:
        available=meminfo(read_at(proc,'meminfo'))
        stats=vmstat(read_at(proc,'vmstat'))
    finally:os.close(proc)
    pressure_fd=directory('/proc/pressure')
    try:psi=tuple(sorted(pressure(read_at(pressure_fd,'memory')).items()))
    finally:os.close(pressure_fd)
    statm=proc_text(os.getpid(),'statm').split()
    require(len(statm)>=2)
    pages=os.sysconf('SC_PAGE_SIZE'); vms=integer(int(statm[0]))*pages; rss=integer(int(statm[1]))*pages
    candidates=[]
    for kind in (resource.RLIMIT_AS,resource.RLIMIT_DATA):
        cap,_=resource.getrlimit(kind)
        if cap!=resource.RLIM_INFINITY:
            # VMS is a conservative upper bound for DATA usage as well.
            require(cap>=vms); candidates.append(cap-vms)
    return LocalSample(time.monotonic_ns(),tuple(nodes),available,stats,psi,rss,min(candidates) if candidates else None)
