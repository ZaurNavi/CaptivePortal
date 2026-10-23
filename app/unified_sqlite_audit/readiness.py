"""A passive loopback probe. Only a real response is a runner admission fence."""
from dataclasses import dataclass
import http.client
import os
from pathlib import Path
import time
import uuid

from .model import AuditError, enabled, identifier


@dataclass(frozen=True)
class ReadyProof:
    portal_run_id: str
    pid: int
    start: str
    boot: str
    port: int


class ReadyUnavailable(AuditError):
    """No completed local response yet; only this permits automatic retry."""
    def __init__(self):super().__init__('ready_unproven')


class ReadyRejected(AuditError):
    """A response/proof violates the boundary; do NOT retry it as warming up."""
    def __init__(self):super().__init__('ready_unproven')


def process_identity(pid):
    # stat's comm can contain spaces and parentheses; parse after its LAST ')'.
    fields = Path(f'/proc/{pid}/stat').read_text(encoding='ascii').rsplit(')',1)[1].split()
    return fields[19], Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()


def install(app, settings):
    if not enabled(settings):
        return None
    from flask import request, Response
    run_id = str(uuid.uuid4())
    pid = os.getpid()
    try:
        start, boot = process_identity(pid)
    except (OSError, IndexError, ValueError):
        # Unsupported process provenance never produces a successful readiness fence.
        start = boot = None

    @app.get('/__internal/audit-ready')
    def unified_audit_ready():
        original = request.environ.get('werkzeug.proxy_fix.orig', {})
        peer = original.get('REMOTE_ADDR', request.environ.get('REMOTE_ADDR'))
        forwarded = any(k.lower().startswith('x-forwarded-') or k.lower() in {'forwarded','x-real-ip'}
                        for k in request.headers.keys())
        if (peer not in {'127.0.0.1','::1'} or forwarded
                or request.host.split(':',1)[0] not in {'127.0.0.1','localhost'}):
            return Response(status=404)
        try:
            current = process_identity(pid)
        except (OSError, IndexError, ValueError):
            current = None
        if os.getpid() != pid or start is None or current != (start,boot):
            return Response(status=503)
        return Response(status=204, headers={'Cache-Control':'no-store',
            'X-Audit-Run':run_id, 'X-Audit-Pid':str(pid), 'X-Audit-Start':start, 'X-Audit-Boot':boot})

    from .model import catalog
    from .status import UnifiedSqliteAuditReadService
    app.extensions['unified_sqlite_audit_run_id']=run_id
    app.extensions['unified_sqlite_audit']=UnifiedSqliteAuditReadService(
        catalog(True,portal_run_id=run_id),portal_run_id=run_id)
    return run_id


def prepare_portal_state(app):
    """After ordinary owner composition, BEFORE listening. No worker or SQL."""
    run_id=app.extensions.get('unified_sqlite_audit_run_id')
    if run_id is None:return
    from .preflight import prepare
    from .status import OutcomeJournal, UnifiedSqliteAuditReadService
    try:initial,_,_=prepare(True,run_id)
    except Exception:
        from .model import catalog
        initial=catalog(True,portal_run_id=run_id)
    try:journal=OutcomeJournal('/run/captiveportal-unified-sqlite-audit')
    except (OSError,AuditError):journal=None
    app.extensions['unified_sqlite_audit']=UnifiedSqliteAuditReadService(
        initial,journal=journal,portal_run_id=run_id)


def _owns_listener(pid, port):
    # A different local process cannot attest readiness on behalf of the portal.
    inodes = set()
    for line in Path('/proc/net/tcp').read_text(encoding='ascii').splitlines()[1:]:
        fields = line.split()
        address, number = fields[1].split(':')
        if int(number,16) == port and address in {'0100007F','00000000'} and fields[3] == '0A':
            inodes.add('socket:['+fields[9]+']')
    if not inodes:return False
    for entry in Path(f'/proc/{pid}/fd').iterdir():
        try:
            if os.readlink(entry) in inodes:return True
        except FileNotFoundError:continue  # Unrelated FD can close concurrently.
    return False


def probe(port, *, timeout=2):
    """Single direct local HTTP attempt; never Requests/env proxies or a ready loop."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ReadyRejected()
    connection = http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
    try:
        connection.request('GET','/__internal/audit-ready',headers={'Connection':'close'})
        response = connection.getresponse()
        if (response.status != 204 or response.read(1) or
                any(name.lower().startswith('x-forwarded-') or name.lower() in
                    {'forwarded','x-real-ip','via'} for name,_ in response.getheaders())):
            raise ReadyRejected()
        try:
            run_id = response.getheader('X-Audit-Run')
            pid = int(response.getheader('X-Audit-Pid','0'))
            start,boot = response.getheader('X-Audit-Start'),response.getheader('X-Audit-Boot')
            if (not identifier(run_id) or pid <= 0 or process_identity(pid) != (start,boot)
                    or not _owns_listener(pid,port)):
                raise ReadyRejected()
            return ReadyProof(run_id,pid,start,boot,port)
        except (OSError, ValueError, IndexError):
            raise ReadyRejected() from None
    except (OSError, http.client.RemoteDisconnected):
        raise ReadyUnavailable() from None
    except http.client.HTTPException:
        raise ReadyRejected() from None
    finally:
        connection.close()


def confirm(proof):
    return isinstance(proof, ReadyProof) and probe(proof.port) == proof


def wait_ready(port, seconds, *, until_cancelled=False, cancelled=lambda:False, probe_fn=probe,
               clock=time.monotonic, sleep=time.sleep):
    """Explicit automatic liveness wait OR the preserved manual probe mode.

    Automatic wait has NO elapsed/attempt ceiling. Each network attempt is
    bounded, and its quiet pause checks cancellation. Only transport-not-ready
    is retried; rejected proofs/security errors terminate. Neither mode opens a
    source or writes journal transitions before a real 204.
    """
    if type(seconds) is not int or not 0 <= seconds <= 300:
        raise AuditError('ready_unproven')
    if type(until_cancelled) is not bool or until_cancelled and seconds!=0:
        raise ReadyRejected()
    if until_cancelled:
        while True:
            if cancelled():raise AuditError('cancelled')
            try:
                proof=probe_fn(port,timeout=2)
                if cancelled():raise AuditError('cancelled')
                return proof
            except ReadyUnavailable:pass
            # A one-second inexpensive pause, cancellable every 100 ms.
            # No clock comparison or fixed probe count can abandon a live boot.
            for _ in range(10):
                if cancelled():raise AuditError('cancelled')
                sleep(0.1)
    until=clock()+seconds
    for _ in range(1501):  # Also bounded if a broken clock stops advancing.
        if cancelled():raise AuditError('cancelled')
        remaining=until-clock()
        try:return probe_fn(port,timeout=min(2,max(0.001,remaining)) if seconds else 2)
        except ReadyRejected:raise
        except AuditError:
            if not seconds or remaining<=0:raise
        remaining=until-clock()
        if remaining<=0:raise AuditError('ready_unproven')
        sleep(min(0.2,remaining))
    raise AuditError('ready_unproven')
