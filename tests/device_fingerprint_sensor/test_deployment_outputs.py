"""Deployable Suricata output contract; no Linux service or capture is started."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deploy" / "device-fingerprint"
APPROVED_OUTPUTS = """  - console:
      enabled: no
  - eve-log:
      enabled: yes
      filetype: unix_dgram
      filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock
      ethernet: yes
      types:
        - tls:
            extended: no
            custom: [ja4, client_alpns, client_handshake]
        - quic:
            extended: no
        - stats:
            totals: yes
            threads: no
            deltas: no"""


def test_deployable_suricata_has_only_unchanged_sensor_datagram_eve():
    config = (DEPLOYMENT / "suricata.yaml").read_text(encoding="ascii")
    outputs = config.split("\noutputs:\n", 1)[1].split("\nlogging:\n", 1)[0]
    output_lines = [line for line in outputs.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    assert "\n".join(output_lines) == APPROVED_OUTPUTS
    assert "filetype: regular" not in config
    assert "diag-eve.json" not in config
    assert config.count("  - eve-log:") == 1
    assert "\ndefault-log-dir: /run/fingerprint-suricata\n" in config
    assert "interface: enp8s0" in config
    assert 'bpf-filter: "net 192.168.8.0/22"' in config


def test_suricata_has_separate_writable_runtime_directory_without_run_workarounds():
    service = (DEPLOYMENT / "fingerprint-suricata.service").read_text(encoding="ascii")
    assert "\nRuntimeDirectory=fingerprint-suricata\n" in service
    assert "\nRuntimeDirectoryMode=0750\n" in service
    assert "ReadOnlyPaths=" not in service
    assert "ReadWritePaths=" not in service
    assert "BindPaths=" not in service
    assert "ExecStart=/usr/bin/suricata -c /etc/captive-portal/device-fingerprint/suricata.yaml --af-packet=enp8s0 --runmode=workers" in service
    assert "ExecStartPre=/usr/bin/test -e /sys/class/net/enp8s0" in service
    assert "until test -S /run/captive-portal/fingerprint-sensor/suricata-eve.sock" in service
    assert "AmbientCapabilities=CAP_NET_RAW" in service
    assert "CapabilityBoundingSet=CAP_NET_RAW" in service
    assert "User=suricata" in service
    assert "ExecStartPre=/usr/bin/suricata -T -c /etc/captive-portal/device-fingerprint/suricata.yaml" in service
