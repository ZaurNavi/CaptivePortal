"""Disposable, test-only certificates and loopback Omada-shaped HTTP fixtures.

Never contains a production certificate/key/credential or changes /etc/hosts.
The DNS mapping is pytest-only; runtime transport does not override DNS/SNI/Host.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import threading
from types import SimpleNamespace

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def make_anchor(directory, *, stem="anchor", name="Omada", state="valid", eku=True, key=None,
                self_issued=True, signer=None, ca=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    key = key or rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local TLS fixture")])
    now = datetime.utcnow()
    before = now + timedelta(days=1) if state == "future" else now - timedelta(days=2)
    after = now - timedelta(days=1) if state == "expired" else now + timedelta(days=2)
    issuer = subject if self_issued else x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "other issuer")])
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(before).not_valid_after(after)
               .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
               .add_extension(x509.ExtendedKeyUsage([
                   ExtendedKeyUsageOID.SERVER_AUTH if eku else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False))
    certificate = builder.sign(signer or key, hashes.SHA256())
    cert_path, key_path = directory / (stem + ".pem"), directory / (stem + ".key")
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    cert_path.chmod(0o444)
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    key_path.chmod(0o600)
    return SimpleNamespace(path=cert_path, key=key_path,
                           sha=hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).hexdigest())


def tls_settings(anchor, **overrides):
    values = {"omada_url": "https://Omada:8043", "omada_id": "controller-id",
              "client_id": "test-client", "client_secret": "DISPOSABLE_CLIENT_SECRET",
              "verify_ssl": True, "omada_tls_trust_anchor_path": str(anchor.path),
              "omada_tls_trust_anchor_sha256": anchor.sha}
    values.update(overrides)
    return values


def api_payload(path):
    if "/authorize/token" in path:
        result = {"accessToken": "DISPOSABLE_ACCESS_TOKEN"}
    elif path.endswith(("/auth", "/unauth", "/reconnect")):
        result = {}
    elif "/clients/" in path:
        result = {"mac": "AA-BB-CC-DD-EE-FF", "active": True, "authStatus": 2}
    else:
        result = {"data": [], "totalRows": 0}
    return {"errorCode": 0, "msg": "Success.", "result": result}


@contextmanager
def omada_server(anchor=None, responder=None):
    records, sni = [], []

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            records.append({"method": self.command, "path": self.path,
                            "headers": dict(self.headers), "body": body})
            status, headers, payload = (responder(self.path) if responder else
                                         (200, {}, api_payload(self.path)))
            raw = json.dumps(payload).encode()
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, *args):
            pass  # never print even synthetic authorization headers

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    if anchor is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(anchor.path), str(anchor.key))
        context.set_servername_callback(lambda connection, name, ctx: sni.append(name))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(port=server.server_address[1], records=records, sni=sni)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        assert not thread.is_alive()
