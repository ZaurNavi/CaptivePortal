"""Fixed protected UNIX endpoint. No DB selector, host token, force or ENV."""
import argparse
import json
import os
from pathlib import Path
import socket
import stat

from . import contracts as c
from .live_policy import SOCKET,VALIDATORS,require
from .protocol import peer_scope,receive_response,send

MANUAL_BATCH_RESPONSE_SECONDS=10.0


def request_shape(value):
    require(type(value) is dict,'invalid_request')
    op=value.get('op')
    if op=='submit_batch':
        c.closed(value,{'op','items'})
        require(type(value['items']) is list and len(value['items'])==3,'invalid_request')
        for item in value['items']:
            c.closed(item,{'store_id','idempotency_key'})
            require(type(item['store_id']) is str and item['store_id'] in VALIDATORS,'invalid_request')
            c.identifier(item['idempotency_key'])
        require(len({item['store_id'] for item in value['items']})==3,'invalid_request')
    elif op=='status_by_key':
        c.closed(value,{'op','store_id','idempotency_key'})
        require(type(value['store_id']) is str and value['store_id'] in VALIDATORS,'invalid_request')
        c.identifier(value['idempotency_key'])
    elif op=='cancel':
        c.closed(value,{'op','job_id','attempt_id','controller_epoch'})
        c.identifier(value['job_id']);c.identifier(value['controller_epoch'])
        if value['attempt_id'] is not None:c.identifier(value['attempt_id'])
    elif op=='stop':
        c.closed(value,{'op','controller_epoch'});c.identifier(value['controller_epoch'])
    else:c.request(value)
    c.encode(value,c.MAX_FRAME)


def response_shape(reply,value):
    """Closed public reply; malformed response is UNKNOWN, not a rejection."""
    if type(reply) is dict and set(reply)=={'error'}:
        require(type(reply['error']) is str and reply['error'] in c.ERRORS,'coordinator_unavailable')
        return reply
    def job(item,store=None):
        c.closed(item,set(c.public_job(dict.fromkeys(c.JOB_KEYS))))
        c.identifier(item['job_id'])
        require(item['resource_domain']==c.DOMAIN and item['store_id'] in VALIDATORS
            and (store is None or item['store_id']==store)
            and item['state'] in c.OUTSTANDING|c.TERMINAL,'coordinator_unavailable')
    op=value['op']
    if op=='submit_batch':
        c.closed(reply,{'status','jobs'})
        require(reply['status']=='batch' and type(reply['jobs']) is list and len(reply['jobs'])==3)
        for item,request_item in zip(reply['jobs'],value['items']):
            c.closed(item,{'status','job'});require(item['status'] in {'queued','duplicate'})
            job(item['job'],request_item['store_id'])
        require(len({item['job']['job_id'] for item in reply['jobs']})==3)
    elif op=='status_by_key':
        if type(reply) is dict and reply.get('status')=='not_found':
            c.closed(reply,{'status','outcome'});require(reply['outcome']=='outcome_unresolved')
        else:
            c.closed(reply,{'status','job'});require(reply['status']=='found');job(reply['job'],value['store_id'])
    elif op=='submit':
        c.closed(reply,{'status','job'});require(reply['status'] in {'queued','duplicate'});job(reply['job'],value['store_id'])
    elif op=='status':
        c.closed(reply,{'status','job','last_attempt','last_verified_success'})
        require(reply['status']=='status');job(reply['job']);require(reply['job']['job_id']==value['job_id'])
    elif op=='cancel':
        c.closed(reply,{'status','job'});require(reply['status']=='cancel_requested');job(reply['job'])
    else:
        c.closed(reply,{'status','controller_epoch'});require(reply['status']=='stopped');c.identifier(reply['controller_epoch'])
    return reply


def request(value):
    request_shape(value)
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
            try:
                send(connection,value)
                reply=receive_response(connection,seconds=MANUAL_BATCH_RESPONSE_SECONDS if value['op']=='submit_batch' else 1.0)
                return response_shape(reply,value)
            except (c.CoordinatorError,OSError,ValueError,KeyError,TypeError):
                # Never turn a broken reply into definite invalid_request.
                raise c.CoordinatorError('coordinator_unavailable') from None
    finally:os.close(parent)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Attended three-store audit pilot')
    commands=parser.add_subparsers(dest='op',required=True)
    batch=commands.add_parser('submit-batch')
    for position in ('a','b','c'):
        batch.add_argument('--'+position+'-store',required=True)
        batch.add_argument('--'+position+'-key',required=True)
    status=commands.add_parser('status');status.add_argument('job_id')
    by_key=commands.add_parser('status-by-key');by_key.add_argument('--store',required=True);by_key.add_argument('--key',required=True)
    cancel=commands.add_parser('cancel');cancel.add_argument('job_id');cancel.add_argument('--attempt-id')
    cancel.add_argument('--controller-epoch',required=True)
    stop=commands.add_parser('stop');stop.add_argument('--controller-epoch',required=True)
    args=parser.parse_args(argv)
    if args.op=='submit-batch':
        value=dict(op='submit_batch',items=[dict(store_id=getattr(args,x+'_store'),idempotency_key=getattr(args,x+'_key'))
            for x in ('a','b','c')])
    elif args.op=='status':value=dict(op='status',job_id=args.job_id)
    elif args.op=='status-by-key':value=dict(op='status_by_key',store_id=args.store,idempotency_key=args.key)
    elif args.op=='cancel':value=dict(op='cancel',job_id=args.job_id,attempt_id=args.attempt_id,controller_epoch=args.controller_epoch)
    else:value=dict(op='stop',controller_epoch=args.controller_epoch)
    try:
        output=request(value)
        if value['op']=='submit_batch' and output.get('error')=='coordinator_unavailable':
            output=dict(error='coordinator_unavailable',outcome='ACK_OUTCOME_UNKNOWN')
        print(json.dumps(output,sort_keys=True));return 2 if 'error' in output else 0
    except c.CoordinatorError as error:
        output=dict(error=error.code)
        if value['op']=='submit_batch' and error.code=='coordinator_unavailable':output['outcome']='ACK_OUTCOME_UNKNOWN'
        print(json.dumps(output));return 2
    except OSError:
        output=dict(error='coordinator_unavailable')
        if value['op']=='submit_batch':output['outcome']='ACK_OUTCOME_UNKNOWN'
        print(json.dumps(output));return 2


if __name__=='__main__':raise SystemExit(main())
