"""Systemd-delegated per-attempt leaf, placement, local receipts and release.

Never falls back to system.slice or a different mount. No provisioning outside
the verified delegated subtree. Only the supervisor creates/caps/places/kills;
worker only observes. All installation, execution and mutations are OFF until a
separately qualified daemon profile is supplied by the later SysAdmin cutover.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import time

from . import contracts as c
from .live_policy import path, require, integer
from .live_receipts import (CGROUP2_SUPER_MAGIC,directory,filesystem_magic,identity,
    read_at,parse_node,membership,start_ticks,guest_sample)

MEMORY=('memory.max','memory.current','memory.swap.max','memory.swap.current','memory.events','memory.pressure')


def mountpoint():
    proc=directory('/proc/'+str(os.getpid()),uid=os.geteuid())
    try: raw=read_at(proc,'mountinfo')
    finally: os.close(proc)
    found=[]
    for line in raw.splitlines():
        before,sep,after=line.partition(' - ')
        require(bool(sep)); left=before.split(); right=after.split()
        if right[0]=='cgroup': raise c.CoordinatorError('not_admitted')
        if right[0]=='cgroup2':
            require(len(left)>=6 and left[3]=='/' and left[4]=='/sys/fs/cgroup' and 'rw' in left[5].split(','))
            found.append(left[4])
    require(found==['/sys/fs/cgroup'])
    return found[0]


class Leaf:
    def __init__(self, mount, relative, expected, *, uid=0):
        require(mount=='/sys/fs/cgroup'); path(relative)
        require(relative!='/' and len(relative.split('/'))<=17)
        self.mount,self.relative,self.uid=mount,relative,uid
        self.path=mount+relative; self.fd=directory(self.path,uid=uid,expected=expected)
        self.identity=identity(os.fstat(self.fd))
        require(filesystem_magic(self.fd)==CGROUP2_SUPER_MAGIC)

    def check(self):
        require(identity(os.stat(self.path,follow_symlinks=False))==self.identity, 'unsafe_path')
        require(filesystem_magic(self.fd)==CGROUP2_SUPER_MAGIC)

    def write(self, name, value):
        require(name in {'memory.max','memory.swap.max','pids.max','cgroup.procs','cgroup.kill'})
        self.check(); before=os.stat(name,dir_fd=self.fd,follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==self.uid and not before.st_mode & 0o022)
        fd=os.open(name,os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.fd)
        try:
            require(identity(os.fstat(fd))==identity(before))
            raw=value.encode('ascii'); require(os.write(fd,raw)==len(raw))
        finally:os.close(fd)
        self.check()

    def samples(self):
        self.check()
        components=self.relative.strip('/').split('/')
        names=['/']+['/'+'/'.join(components[:n]) for n in range(1,len(components)+1)]
        nodes=[]
        for location in names:
            fd=directory(self.mount+('' if location=='/' else location),uid=self.uid)
            try:
                require(filesystem_magic(fd)==CGROUP2_SUPER_MAGIC)
                stamp=identity(os.fstat(fd))
                values={key:read_at(fd,key,optional=location=='/',trusted_uid=self.uid) for key in MEMORY}
                for key in ('cgroup.events','cgroup.procs'):
                    values[key]=read_at(fd,key,optional=location=='/',trusted_uid=self.uid)
                controls=read_at(fd,'cgroup.controllers',trusted_uid=self.uid)
                subtree=read_at(fd,'cgroup.subtree_control',trusted_uid=self.uid)
                if location!=self.relative: require('memory' in subtree.split())
                require('memory' in controls.split() or location==self.relative)
                nodes.append(parse_node(location,stamp,values,root=location=='/'))
                require(stamp==identity(os.fstat(fd)))
            finally:os.close(fd)
        require(nodes[-1].identity==self.identity)
        self.check(); return tuple(nodes)

    def contained(self,pid,cap,start=None):
        self.check()
        require(membership(pid)==self.relative and (start is None or start_ticks(pid)==start))
        node=self.samples()[-1]
        require(node.maximum==cap and node.swap_max==0 and node.procs==(pid,) and node.populated==1)

    def empty(self):
        self.check()
        # Any nested subgroup, even empty, requires separate reconciliation.
        for name in os.listdir(self.fd):
            require(not stat.S_ISDIR(os.stat(name,dir_fd=self.fd,follow_symlinks=False).st_mode))
        node=self.samples()[-1]
        require(node.populated==0 and node.procs==())
        return self.identity,time.monotonic_ns()

    def released(self,process,pidfd,recorded_start):
        require(process.returncode is not None and process.wait(timeout=0)==process.returncode)
        # pidfd is opened while blocked child is alive, never looked up by PID
        # after reap. POLLIN means this exact process has exited, not PID reuse.
        import select
        poller=select.poll(); poller.register(pidfd,select.POLLIN)
        require(bool(poller.poll(0)))
        first=self.empty(); second=self.empty()
        require(first[0]==second[0] and first[1]<second[1])
        # Dead exact process + empty no-descendant leaf proves process-owned
        # snapshot memory gone, even if cached pages remain charged.
        return True

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None


def create_leaf(delegated, expected, job, cap, *, uid=0, worker_gid=None, tasks=1):
    path(delegated); require(delegated!='/' and not delegated.endswith('/system.slice'))
    mount=mountpoint(); parent=directory(mount+delegated,uid=uid,expected=expected)
    try:
        require(filesystem_magic(parent)==CGROUP2_SUPER_MAGIC)
        require(read_at(parent,'cgroup.procs',trusted_uid=uid).strip()=='')
        require('memory' in read_at(parent,'cgroup.controllers',trusted_uid=uid).split()
            and 'memory' in read_at(parent,'cgroup.subtree_control',trusted_uid=uid).split())
        own=membership(os.getpid()); require(own.startswith(delegated+'/') and own!=delegated)
        for key in ('job_id','claim_epoch','attempt_id'):c.identifier(job[key])
        name='job-'+job['job_id']+'-'+job['attempt_id']
        require(len(name)<128)
        os.mkdir(name,0o750,dir_fd=parent)
        if worker_gid is not None:
            os.chown(name,uid,integer(worker_gid,1,2**32-1),dir_fd=parent,follow_symlinks=False)
        info=os.stat(name,dir_fd=parent,follow_symlinks=False)
        leaf=Leaf(mount,delegated+'/'+name,identity(info),uid=uid)
        try:
            leaf.write('memory.max',str(integer(cap,1)))
            leaf.write('memory.swap.max','0');leaf.write('pids.max',str(integer(tasks,1,32)))
            # Required whole-group abort primitive; no random PID kill fallback.
            require(stat.S_ISREG(os.stat('cgroup.kill',dir_fd=leaf.fd,follow_symlinks=False).st_mode))
            return leaf
        except Exception:
            leaf.close();raise
    finally:os.close(parent)
