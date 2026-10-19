"""Fixed protected UNIX endpoint. No DB selector, host token, force or ENV."""
import argparse
import json
import os
from pathlib import Path
import socket
import stat

from . import contracts as c
from .live_policy import SOCKET,require
from .protocol import peer_scope,receive,send


def request(value):
    require(os.name=='posix','not_admitted')
    from .live_receipts import directory,identity
    location=Path(SOCKET);parent=directory(str(location.parent),uid=0)
    try:
        info=location.lstat()
        require(stat.S_ISSOCK(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o660,'unsafe_path')
        stamp=identity(info)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(2);connection.connect(SOCKET)
            peer_scope(connection,{0})
            require(identity(location.lstat())==stamp,'unsafe_path')
            send(connection,value);return receive(connection)
    finally:os.close(parent)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Attended three-store audit pilot')
    commands=parser.add_subparsers(dest='op',required=True)
    batch=commands.add_parser('submit-batch')
    for position in ('a','b','c'):
        batch.add_argument('--'+position+'-store',required=True)
        batch.add_argument('--'+position+'-key',required=True)
    status=commands.add_parser('status');status.add_argument('job_id')
    cancel=commands.add_parser('cancel');cancel.add_argument('job_id');cancel.add_argument('--attempt-id')
    cancel.add_argument('--controller-epoch',required=True)
    stop=commands.add_parser('stop');stop.add_argument('--controller-epoch',required=True)
    args=parser.parse_args(argv)
    if args.op=='submit-batch':
        value=dict(op='submit_batch',items=[dict(store_id=getattr(args,x+'_store'),idempotency_key=getattr(args,x+'_key'))
            for x in ('a','b','c')])
    elif args.op=='status':value=dict(op='status',job_id=args.job_id)
    elif args.op=='cancel':value=dict(op='cancel',job_id=args.job_id,attempt_id=args.attempt_id,controller_epoch=args.controller_epoch)
    else:value=dict(op='stop',controller_epoch=args.controller_epoch)
    try:
        output=request(value)
        print(json.dumps(output,sort_keys=True));return 2 if 'error' in output else 0
    except c.CoordinatorError as error:
        print(json.dumps(dict(error=error.code)));return 2


if __name__=='__main__':raise SystemExit(main())
