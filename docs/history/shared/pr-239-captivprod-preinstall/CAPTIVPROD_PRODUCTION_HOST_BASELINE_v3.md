# CAPTIVPROD_PRODUCTION_HOST_BASELINE

**Project:** CaptivPortal  
**Role:** CaptivPortal Production Deployment Lead  
**Task:** TASK-DEPLOY-NEW-PROD-01 — NEW PRODUCTION PREFLIGHT  
**Host:** `captiv-prod`  
**IP:** `192.168.0.99`  
**Collected:** 2026-09-30  
**Scope:** Read-only host / runtime / Omada / network / deployment preflight  
**Changes made:** `NONE`

---

# 1. Executive summary

`captiv-prod` is a clean greenfield host for a new parallel CaptivPortal deployment.

The new Omada Controller is installed and running on the same physical host. No previous CaptivPortal installation, CaptivPortal systemd units, fingerprint services, or traffic-projection services were found.

The historical TCP `8088` collision has been architecturally resolved.

```text
Omada Controller keeps vendor/default *:8088
CaptivPortal backend is reserved on 127.0.0.1:8090
Public frontend terminates at Nginx :443
```

The historical CaptivPortal backend bind `127.0.0.1:8088` is not reused on this host.

Ports `80/tcp` and `443/tcp` are currently free. Nginx, Apache and Certbot are not installed.

The host has sufficient idle CPU/RAM for initial single-AP testing, with a large unused LVM capacity reserve. Final coexistence acceptance still requires post-deployment idle and single-AP resource measurements.

---

# 2. Host identity

```text
HOSTNAME = captiv-prod
HARDWARE_VENDOR = HP
HARDWARE_MODEL = HP 290 G1 MT
ARCHITECTURE = x86_64
```

Operating system:

```text
Ubuntu Server 22.04.5 LTS
Jammy Jellyfish
Kernel: 5.15.0-194-generic
```

Current administrative account used during preflight:

```text
user = sysadmin
uid  = 1000
gid  = 1000
sudo = available
```

---

# 3. Time / timezone / NTP

Observed host time configuration:

```text
Host timezone = Etc/UTC
RTC            = UTC
NTP service    = active
Clock sync     = yes
```

Important deployment note:

```text
Omada Site timezone = Asia/Baku
Host timezone       = Etc/UTC
```

This is a confirmed difference, not yet classified as a defect.

Do not change host timezone during preflight.

The final deployment design must confirm whether CaptivPortal relies on:

```text
UTC host time
+
explicit Site/application timezone
```

or requires host timezone alignment.

---

# 4. CPU

```text
CPU model = Intel Core i3-7100 @ 3.90 GHz
Sockets   = 1
Cores     = 2
Threads   = 4
VT-x      = available
```

Observed pre-CaptivPortal system load:

```text
load average = 0.12 / 0.07 / 0.02
```

This is the baseline before CaptivPortal installation.

---

# 5. Memory

Observed:

```text
RAM total     = 7.5 GiB
RAM used      = ~1.5 GiB
RAM available = ~5.8 GiB
Swap          = 4.0 GiB
Swap used     = 0
```

Swap:

```text
/swap.img
type = file
size = 4 GiB
```

Largest observed resident processes during original preflight:

```text
Omada Java / jsvc       ~1.09 GiB RSS
Omada bundled MongoDB   ~181 MiB RSS
System MongoDB          ~150 MiB RSS
```

Current accepted state after MongoDB isolation test:

```text
System MongoDB process = not running
```

---

# 6. Storage

Physical disk:

```text
/dev/sda
Model = ST1000DM010-2EP1
Size  = 931.51 GiB
GPT
```

Partitions:

```text
/dev/sda1   ~1 GiB      EFI
/dev/sda2    2 GiB      /boot
/dev/sda3  ~928.5 GiB   LVM PV
```

LVM:

```text
VG = ubuntu-vg
VG size = ~928.46 GiB
LV = ubuntu-lv
LV size = 100 GiB
VG free = ~828.46 GiB
```

Root filesystem:

```text
filesystem = ext4
size       = ~98 GiB usable
used       = ~9.5 GiB
available  = ~84 GiB
usage      = 11%
inode use  = 2%
```

Large unused LVM capacity exists, but no resize or new LV was performed during preflight.

Mounts of deployment relevance:

```text
/         ext4
/boot     ext4
/boot/efi vfat
```

---

# 7. Network

Primary interface:

```text
interface = enp2s0
IPv4      = 192.168.0.99/24
gateway   = 192.168.0.1
DNS       = 192.168.0.1
MTU       = 1500
```

IPv6:

```text
link-local only on enp2s0
```

Routing:

```text
default via 192.168.0.1 dev enp2s0
192.168.0.0/24 directly connected
```

No custom policy-routing rules were observed.

Netplan source:

```text
/etc/netplan/50-cloud-init.yaml
```

Important note:

The file is cloud-init generated and explicitly warns that direct changes may not persist. Any future network change must account for cloud-init ownership.

---

# 8. NIC hardware

```text
Controller = Realtek RTL8111/8168/8411 PCIe Gigabit Ethernet
PCI ID     = 10ec:8168
Revision   = 15
Driver     = r8169
Firmware   = rtl8168h-2_0.0.2
Bus        = 0000:02:00.0
```

Link state:

```text
Speed            = 1000 Mb/s
Duplex           = Full
Auto-negotiation = on
Link detected    = yes
Promiscuous mode = off
```

Fingerprint/SPAN sensor NIC deployment is intentionally outside this first Portal deployment phase.

---

# 9. Network reachability

Verified from `captiv-prod`:

```text
Gateway 192.168.0.1 = PASS
DNS resolution       = PASS
Internet HTTPS       = PASS
GitHub HTTPS         = PASS
Local Omada HTTPS    = PASS
```

Omada HTTPS response was successfully received from:

```text
https://192.168.0.99:8043
```

---

# 10. Listening socket inventory

Observed listening sockets relevant to deployment:

## TCP

```text
127.0.0.53:53      systemd-resolved
127.0.0.1:27017    NOT LISTENING (system mongod.service disabled/inactive)
127.0.0.1:27217    Omada bundled MongoDB
0.0.0.0:22         sshd
[::]:22             sshd

*:8043              Omada / jsvc
*:8088              Omada / jsvc
*:8843              Omada / jsvc

*:29811             Omada / jsvc
*:29812             Omada / jsvc
*:29813             Omada / jsvc
*:29814             Omada / jsvc
*:29815             Omada / jsvc
*:29816             Omada / jsvc
```

## UDP

```text
127.0.0.53:53       systemd-resolved
*:19810              Omada / jsvc
*:27001              Omada / jsvc
*:29810              Omada / jsvc
*:57691              Omada / jsvc
```

---

# 11. Critical port ownership

```text
PORT_8088_OWNER = Omada Controller / jsvc
BIND             = wildcard (*:8088)
STATUS           = OCCUPIED
```

```text
PORT_8043_OWNER = Omada Controller / jsvc
BIND             = wildcard
STATUS           = OCCUPIED
```

```text
PORT_8843_OWNER = Omada Controller / jsvc
BIND             = wildcard
STATUS           = OCCUPIED
```

```text
PORT_80_OWNER = NONE
STATUS        = FREE
```

```text
PORT_443_OWNER = NONE
STATUS         = FREE
```

This confirms a real backend port collision with historical CaptivPortal use of `127.0.0.1:8088`.

---

# 12. CaptivPortal backend port decision

The following ports were verified free at preflight time:

```text
5000
5001
8000
8080
8081
8090
9000
```

Architecture decision `CAPTIVPROD-DEPLOYMENT-DECISION-01` selected:

```text
CAPTIVPORTAL_BACKEND_BIND = 127.0.0.1:8090
PUBLIC_FRONTEND           = Nginx HTTPS :443
BACKEND_PUBLIC            = NO
```

Omada remains on its vendor/default ports, including `*:8088`.

The backend host/port must be deployment-configurable through an approved persistent configuration mechanism.

If the approved candidate still hardcodes `127.0.0.1:8088`, local source patching is forbidden and DeployLead must return:

```text
CAPTIVPORTAL_BACKEND_PORT_CONFIG_BLOCKER
```

for a bounded TechLead/Coder change.

---

# 13. Omada Controller

Installed package:

```text
omadac = 5.14.32.3
```

Service:

```text
service = tpeap.service
state   = active (running)
enabled = yes
```

Service model:

```text
SysV init script:
  /etc/init.d/tpeap

systemd wrapper:
  generated by systemd-sysv-generator

Type:
  forking

Restart:
  no
```

Ordering includes:

```text
After=network-online.target
Wants=network-online.target
```

Omada installation root:

```text
/opt/tplink/EAPController
```

Top-level directories:

```text
bin
data
lib
logs
properties
work
```

Omada runtime account:

```text
user  = omada
uid   = 115
group = omada
gid   = 120
shell = /usr/sbin/nologin
home  = /opt/tplink/EAPController/data
```

Observed service memory:

```text
tpeap.service cgroup ≈ 1.4 GiB
```

---

# 14. Omada storage

Observed:

```text
/opt/tplink/EAPController/data  ≈ 323 MiB
/opt/tplink/EAPController/logs ≈ 2.9 MiB
/opt/tplink/EAPController/work ≈ 4 KiB
```

Data breakdown:

```text
data/db        ≈ 322 MiB
data/html      ≈ 1008 KiB
data/keystore  ≈ 12 KiB
data/autobackup minimal
data/pdf        minimal
```

Largest log observed:

```text
mongod.log ≈ 2.95 MiB
```

---

# 15. Java

```text
OpenJDK version = 1.8.0_504
Java major      = 8
64-bit Server VM
```

Omada Java home:

```text
/usr/lib/jvm/java-8-openjdk-amd64/jre/
```

---

# 16. MongoDB topology

Two independent MongoDB instances are running.

## 16.1 System MongoDB

```text
binary   = /usr/bin/mongod
version  = 7.0.43
service  = mongod.service
enabled  = no
active   = no
bind when started = 127.0.0.1
port when started = 27017
config   = /etc/mongod.conf
data     = /var/lib/mongodb
log      = /var/log/mongodb/mongod.log
```

Storage retained:

```text
/var/lib/mongodb ≈ 305 MiB
/var/log/mongodb ≈ 432 KiB
```

Observed DB names before disable:

```text
admin
config
local
```

No application DB and no active TCP clients were observed on `27017`.

A controlled isolation test was completed:

```text
mongod.service stopped
Omada Controller remained running
Omada HTTPS :8043 remained HTTP 200
Omada bundled MongoDB :27217 remained LISTEN
system MongoDB :27017 disappeared
```

Accepted production state:

```text
mongod.service = disabled
mongod.service = inactive
127.0.0.1:27017 = NOT LISTENING
127.0.0.1:27217 = LISTENING
Omada Controller = running
```

Decision:

```text
Do not remove MongoDB packages.
Do not remove /usr/bin/mongod.
Do not modify Omada bundled MongoDB.
Keep system mongod.service disabled/inactive.
```

Status:

```text
MONGODB RUNTIME COLLISION = RESOLVED
PRODUCTION ACTION REQUIRED = NONE
```

## 16.2 Omada bundled MongoDB

```text
binary = /opt/tplink/EAPController/bin/mongod
version = 7.0.43
bind = 127.0.0.1
port = 27217
runtime user = omada
```

Observed application DB names:

```text
omada
omada_data
```

This is the MongoDB instance used by Omada Controller.

---

# 17. Web stack

At preflight time:

```text
Nginx   = NOT INSTALLED
Apache  = NOT INSTALLED
Certbot = NOT INSTALLED
```

Ports:

```text
80/tcp  = FREE
443/tcp = FREE
```

Therefore the test/public HTTPS reverse-proxy boundary is not yet built.

---

# 18. Firewall / packet filtering

Observed:

```text
UFW = inactive
nftables ruleset = empty
```

iptables policies:

```text
INPUT   ACCEPT
FORWARD ACCEPT
OUTPUT  ACCEPT
```

No host firewall restriction was observed during preflight.

This is an observed baseline only; it is not an authorization to keep the final production firewall unrestricted.

---

# 19. AppArmor / SELinux

```text
AppArmor = loaded
profiles = 39
mode     = enforce
```

No currently running process was observed with an AppArmor profile assigned in the reported status.

```text
SELinux = not present
```

---

# 20. Python / runtime baseline

System Python:

```text
Python = 3.10.12
path   = /usr/bin/python3
```

Python SQLite:

```text
sqlite3 Python module = available
SQLite runtime        = 3.37.2
```

Python SSL:

```text
ssl module = available
OpenSSL    = 3.0.2
```

Python packaging state:

```text
venv       = available
setuptools = 59.6.0
pip        = NOT AVAILABLE
ensurepip  = NOT AVAILABLE
wheel      = NOT AVAILABLE
```

SQLite CLI:

```text
sqlite3 command = NOT INSTALLED
```

Git:

```text
git = 2.34.1
```

curl:

```text
curl = 7.81.0
```

systemd:

```text
systemd = 249
```

The runtime is not yet prepared for CaptivPortal installation. Exact package requirements must be derived from the approved deployment candidate rather than installed speculatively.

---

# 21. Existing CaptivPortal state

Direct check:

```text
/opt/CaptivePortal = NOT PRESENT
```

No matching CaptivPortal-related systemd units were found.

No matching traces were found in the checked locations for:

```text
captive
captivportal
fingerprint
traffic-projection
```

This supports:

```text
NEW CAPTIVPORTAL HOST STATE = GREENFIELD
```

---

# 22. Current service enablement

```text
ssh    = enabled
mongod = disabled / inactive
tpeap  = enabled
nginx  = not installed
apache = not installed
```

Failed systemd units:

```text
0
```

---

# 23. File descriptor / process limits baseline

Interactive shell limits observed:

```text
ulimit -n = 1024
ulimit -u = 29880
```

System-wide file limit:

```text
/proc/sys/fs/file-max = 9223372036854775807
```

Important:

The shell `ulimit -n=1024` is not automatically the future CaptivPortal systemd service limit. The final service unit must be evaluated separately if the application requires a higher `LimitNOFILE`.

---

# 24. New Omada deployment identity

From the accepted project handoff:

```text
OMADA_URL = https://192.168.0.99:8043

OMADA_VERSION = 5.14.32.3

OMADA_ID =
539865138296e6460dde1e4810eed2ca

OPENAPI_CLIENT_ID =
b121eeea3488478f84e2ad0c8e5bb851
```

Secret exists and is intentionally not included in this baseline.

OAuth `client_credentials` against the new Controller was previously Owner-verified as working.

---

# 25. New Site identity

Accepted deployment identity:

```text
SITE_NAME = Zefer_Parki
SITE_ID   = 6abbf89529d5e6781c7b9cc6
REGION    = Azerbaijan
TIMEZONE  = Asia/Baku
SCENARIO  = Home
```

Important:

```text
Site name = Zefer_Parki
Scenario  = Home
```

`Home` is not the Site name.

---

# 26. Port-binding architecture decision

Architecture decision:

```text
CAPTIVPROD-DEPLOYMENT-DECISION-01
CAPTIVPORTAL BACKEND PORT OWNERSHIP
```

Final ownership:

```text
OMADA_PORT_POLICY            = KEEP_VENDOR_DEFAULTS
OMADA_8088_CHANGE            = NO
CAPTIVPORTAL_BACKEND_BIND    = 127.0.0.1:8090
PUBLIC_FRONTEND              = Nginx HTTPS :443
BACKEND_PUBLIC               = NO
BACKEND_PORT_CONFIGURATION   = REQUIRED
LOCAL_SOURCE_PATCH           = FORBIDDEN
```

Status:

```text
PORT_BINDING_CONFLICT_8088 =
ARCHITECTURALLY RESOLVED
```

Verification target after installation:

```text
*:8088           -> Omada
127.0.0.1:8090   -> CaptivPortal
```

Forbidden without separate approval:

```text
0.0.0.0:8090
*:8090
```

If the approved CaptivPortal candidate cannot select backend host/port through accepted configuration:

```text
CAPTIVPORTAL_BACKEND_PORT_CONFIG_BLOCKER
CODE_CHANGE_REQUIRED = YES
CHANGES_MADE = NONE
```

DeployLead must not modify production source locally.

---


# 26A. Fixed production port principle

```text
1. Omada Controller remains on vendor/default ports.
2. CaptivPortal backend host/port are deployment parameters.
3. CaptivPortal backend binds to loopback only.
4. Public client traffic terminates at Nginx HTTPS.
5. Backend port changes must not alter application semantics.
6. Backend bind configuration must survive service restart and host reboot.
```

Target runtime:

```text
client
  ↓ HTTPS
Nginx :443
  ↓
127.0.0.1:8090
  ↓
CaptivPortal
```

Omada runtime ports are frozen for this deployment task.

# 27. Items that are NOT blockers by themselves

The following are known installation requirements or observations, not automatic deployment failures:

```text
Nginx not installed
Certbot not installed
pip not installed
sqlite3 CLI not installed
wheel not installed
host timezone = UTC
system MongoDB package installed but service disabled/inactive by accepted production decision
tpeap Restart=no
```

Each must be handled or explicitly accepted by the final deployment plan.

---

# 28. Items intentionally deferred

```text
Device Fingerprint physical sensor
second NIC / SPAN topology
fingerprint-sensor.service
fingerprint-suricata.service
fingerprint evidence physical capture deployment
mass AP migration
old CaptivPortal historical DB migration
old production changes
```

These are not required for the first new Portal acceptance.

---

# 29. Remaining gates before installation

The host preflight itself is substantially complete.

Before installation starts, deployment still requires:

1. `APPROVED_DEPLOYMENT_COMMIT`
2. `APPROVED_DEPLOYMENT_TREE`
3. review of current deployment documentation from that exact candidate
4. global search in that exact candidate for old Site ID:

```text
6a64f17630da7c70d232187a
```

5. classification of every match:

```text
RUNTIME
TEST
DOC
HISTORICAL
```

6. confirm that the approved candidate supports the accepted backend bind `127.0.0.1:8090` through deployment configuration
7. exact application/data/log/config/secret paths
8. exact required OS/Python packages
9. exact systemd service definition
10. exact Nginx/test hostname/TLS plan
11. exact persistent secret source
12. exact webhook endpoint/mapping configuration
13. Owner/TechLead-approved deployment path

---

# 30. Preflight status

```text
TASK =
TASK-DEPLOY-NEW-PROD-01

HOST =
192.168.0.99

HOSTNAME =
captiv-prod

CHANGES_MADE =
NONE

HOST_PREFLIGHT_DATA_COLLECTION =
PASS

GREENFIELD_STATE =
PASS

NETWORK_REACHABILITY =
PASS

OMADA_RUNTIME =
PASS

PORT_INVENTORY =
PASS

RESOURCE_BASELINE =
PASS

WEB_STACK_READY =
NO — not installed/configured yet

CAPTIVPORTAL_RUNTIME_READY =
NO — dependencies/candidate not installed yet

PORT_BINDING_DECISION =
RESOLVED — Omada keeps *:8088; CaptivPortal reserved on 127.0.0.1:8090

INSTALLATION_AUTHORIZED =
NO

PREFLIGHT_STATUS =
BLOCKED FOR APPROVED CANDIDATE / CONFIGURATION VERIFICATION
```

Meaning of this status:

The host itself does not show a fatal infrastructure failure. The backend-port architecture is now resolved. Deployment is intentionally not started because the exact approved CaptivPortal commit/tree is not yet pinned and must be checked for deployment-configurable backend host/port support.

---

# 31. Safety state

Old production remains outside this preflight:

```text
OLD OMADA =
192.168.0.222
UNTOUCHED

OLD CAPTIVPORTAL =
192.168.0.202
UNTOUCHED
```

The greenfield parallel-deployment safety principle remains intact.

---

# 32. Next operational step

Do not install CaptivPortal yet.

Next required project input:

```text
APPROVED_DEPLOYMENT_COMMIT
APPROVED_DEPLOYMENT_TREE
```

After they are provided, DeployLead should inspect the exact candidate for:

```text
deployment documentation
requirements/dependencies
backend host/port configuration for 127.0.0.1:8090
old Site ID runtime references
systemd/runtime expectations
DB paths
log paths
secret/config pipeline
Nginx/reverse-proxy expectations
enabled modules
```

Only then should the exact deployment plan be issued.
