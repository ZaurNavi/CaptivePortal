Temporary Pending Session Probe/Cleaner

This temporary service is intended to run for 2–3 days while the productionPendingClientSessionCleaner is under development.

Safety model

A reconnect is possible only when all conditions are true:

SSID == Zefer_Parki
wireless == true
active == true
authStatus == 1
uptime >= 120
not blocked
complete inventory
no duplicate MAC
no recent capport.portal_opened
no active AuthWorker inferred from auth telemetry
no recent auth.* activity
fresh exact-client preflight still matches
per-MAC cooldown expired

The probe processes every eligible distinct MAC in a scan. There is no globalaction limit. The same MAC cannot receive another logical reconnect for 900seconds.

If /opt/CaptivePortal/logs/auth_telemetry.log is missing or unreadable, theprobe fails closed and performs no reconnects.

The probe refuses to start when the project settingPENDING_SESSION_CLEANER_ENABLED=true.

Files

Script:
  /opt/CaptivePortal/tools/pending_session_probe.py

Service:
  /etc/systemd/system/pending-session-probe.service

Optional environment:
  /etc/default/pending-session-probe

Data journal:
  /opt/CaptivePortal/logs/pending_session_probe.log

Persistent state:
  /opt/CaptivePortal/data/pending_session_probe_state.json

Installation

Copy the files:

cd /opt/CaptivePortal
sudo mkdir -p tools logs data

sudo cp pending_session_probe.py \
  /opt/CaptivePortal/tools/pending_session_probe.py

sudo cp pending_session_probe_README.md \
  /opt/CaptivePortal/tools/pending_session_probe_README.md

sudo cp pending-session-probe.service \
  /etc/systemd/system/pending-session-probe.service

sudo cp pending-session-probe.env.example \
  /etc/default/pending-session-probe

Permissions:

sudo chown admin:admin \
  /opt/CaptivePortal/tools/pending_session_probe.py \
  /opt/CaptivePortal/tools/pending_session_probe_README.md

sudo chmod 750 /opt/CaptivePortal/tools/pending_session_probe.py
sudo chmod 640 /opt/CaptivePortal/tools/pending_session_probe_README.md

sudo chown root:root \
  /etc/systemd/system/pending-session-probe.service \
  /etc/default/pending-session-probe

sudo chmod 644 /etc/systemd/system/pending-session-probe.service
sudo chmod 640 /etc/default/pending-session-probe

sudo chown admin:telemetry /opt/CaptivePortal/logs
sudo chmod 2750 /opt/CaptivePortal/logs
sudo chown admin:telemetry /opt/CaptivePortal/data
sudo chmod 2750 /opt/CaptivePortal/data

Credentials and environment

The unit loads variables in this order:

/etc/default/captive-portal
/opt/CaptivePortal/.env
/etc/default/pending-session-probe

The last file has priority. The probe imports the normal projectget_settings() function, so it expects the same Omada URL, Omada ID,Open API client credentials, TLS setting and CAPPORT_SITE_ID as the mainapplication.

Do not put real credentials in Git. When the main service receives itscredentials through another systemd mechanism, copy the same variable namesand values into /etc/default/pending-session-probe with mode 0640.

Preflight

Compile:

cd /opt/CaptivePortal
source venv/bin/activate
python -m py_compile tools/pending_session_probe.py

Run one active scan manually:

python tools/pending_session_probe.py --once

This is not a dry-run. Eligible clients may receive reconnect.

Start the service

sudo systemctl daemon-reload
sudo systemctl enable --now pending-session-probe.service
sudo systemctl status pending-session-probe.service --no-pager

Operational output:

sudo journalctl -u pending-session-probe.service -f

Data events:

tail -f /opt/CaptivePortal/logs/pending_session_probe.log

Recent scan summaries:

grep '"event":"pending_probe.scan.completed"' \
  /opt/CaptivePortal/logs/pending_session_probe.log |
tail -n 20

Automatic rejoin findings:

grep '"event":"pending_probe.client_rejoined"' \
  /opt/CaptivePortal/logs/pending_session_probe.log |
tail -n 50

Stop before production Cleaner activation

This is mandatory:

sudo systemctl disable --now pending-session-probe.service
sudo systemctl status pending-session-probe.service --no-pager

Confirm no process remains:

pgrep -af pending_session_probe.py || true

Only after that may PENDING_SESSION_CLEANER_ENABLED=true be applied.

Uninstall

sudo systemctl disable --now pending-session-probe.service
sudo rm -f /etc/systemd/system/pending-session-probe.service
sudo systemctl daemon-reload

The JSONL journal and persistent state are intentionally preserved for analysis.
