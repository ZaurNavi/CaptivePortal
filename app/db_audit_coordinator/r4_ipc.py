"""Closed bounded Unix packet capability; current SCM credentials, not ENV.

No network/path selector, queue writes or arbitrary FD acceptance. Endpoints
are private socketpairs inherited by exactly one child after close_fds exec.
"""
import array
import hashlib
import os
import socket
import stat
import struct

from . import contracts as c
from .live_policy import require,integer

KINDS={'gate_ready':0,'owner_ready':0,'begin':0,'owner_done':0,'snapshot':2,
    't3_done':0,'release':0,'released':0,'cancel':0}


def claim_binding(job,profile,leaf,namespace):
    """One-use root/worker capability also binds qualified code + kernel view."""
    return hashlib.sha256(c.encode(dict(job={key:job[key] for key in (
        'job_id','store_id','attempt_id','claim_epoch','source_generation','auth_hash','worker_pid')},
        release_commit=profile.commit,release_tree=profile.tree,
        leaf=dict(relative=leaf.relative,identity=list(leaf.identity)),
        mount_namespace=list(namespace)))).hexdigest()


def pair():
    require(os.name=='posix' and hasattr(socket,'SO_PASSCRED'),'not_admitted')
    left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    try:
        for endpoint in (left,right):endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
        return left,right
    except Exception:left.close();right.close();raise


def snapshot_pair(descriptors):
    """Ordered RO regular image + RO O_DIRECTORY; no anonymous/O_PATH alias."""
    import fcntl
    require(type(descriptors) is tuple and len(descriptors)==2 and descriptors[0]!=descriptors[1],'unauthorized')
    infos=[]
    for fd in descriptors:
        integer(fd,0,2**20)
        flags=fcntl.fcntl(fd,fcntl.F_GETFL)
        require(flags&os.O_ACCMODE==os.O_RDONLY and not flags&os.O_PATH,'unauthorized')
        infos.append(os.fstat(fd))
    image,folder=infos
    require(stat.S_ISREG(image.st_mode) and image.st_nlink==1 and stat.S_ISDIR(folder.st_mode)
        and fcntl.fcntl(descriptors[1],fcntl.F_GETFL)&os.O_DIRECTORY
        and image.st_dev==folder.st_dev,'unauthorized')


def send(endpoint,kind,binding,payload,*,fds=(),seconds=1):
    c.digest(binding);require(kind in KINDS and type(payload) is dict,'unauthorized')
    require(type(fds) is tuple and len(fds)==KINDS[kind],'unauthorized')
    if fds:snapshot_pair(fds)
    raw=c.encode(dict(kind=kind,binding=binding,payload=payload),8192)
    ancillary=[] if not fds else [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',fds))]
    endpoint.settimeout(seconds)
    require(endpoint.sendmsg([raw],ancillary)==len(raw),'coordinator_unavailable')


def receive(endpoint,binding,uid,pid,*,seconds,allow_snapshot=False):
    c.digest(binding);integer(uid,0,2**32-1);integer(pid,1,2**31-1)
    descriptors=[]
    try:
        endpoint.settimeout(seconds)
        raw,ancillary,flags,_=endpoint.recvmsg(8193,socket.CMSG_SPACE(12)+socket.CMSG_SPACE(16),
            socket.MSG_CMSG_CLOEXEC)
        credentials=[]
        for level,kind,data in ancillary:
            require(level==socket.SOL_SOCKET,'unauthorized')
            if kind==socket.SCM_CREDENTIALS:
                require(len(data)==12,'unauthorized');credentials.append(struct.unpack('3i',data))
            elif kind==socket.SCM_RIGHTS:
                integers=array.array('i');integers.frombytes(data)
                descriptors.extend(integers)
            else:raise c.CoordinatorError('unauthorized')
        require(raw and len(raw)<=8192 and not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC),'unauthorized')
        require(len(credentials)==1 and credentials[0][:2]==(pid,uid),'unauthorized')
        value=c.decode(raw,8192);c.closed(value,{'kind','binding','payload'})
        require(value['binding']==binding and value['kind'] in KINDS and type(value['payload']) is dict
            and len(descriptors)==KINDS[value['kind']],'unauthorized')
        require(type(allow_snapshot) is bool and (value['kind']!='snapshot' or allow_snapshot),'unauthorized')
        if descriptors:
            snapshot_pair(tuple(descriptors))
            result=tuple(descriptors);descriptors=[]
        else:result=None
        return value['kind'],value['payload'],result
    except Exception:
        for fd in descriptors:os.close(fd)
        raise
