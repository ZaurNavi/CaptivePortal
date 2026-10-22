# Device Fingerprint Sensor — Network Infrastructure Passport

**Project:** CaptivPortal  
**Purpose:** Current verified baseline for future passive Device Fingerprint Sensor / RSPAN design  
**Date:** 2026-09-14  
**State:** READ-ONLY VERIFIED

## 1. OMV Host

```text
Hostname: omv-hp
OS: OMV7 / Debian 12
Kernel: 6.12.95+deb12-amd64
```

## 2. NIC1 — Primary Network

```text
Physical NIC: enp7s0f0
MAC: 44:1e:a1:61:e8:d8
Speed: 1000 Mb/s Full
Bridge: br0
Bridge MAC: a2:dc:57:31:19:0d
OMV IP: 192.168.0.220/24
Gateway: 192.168.0.1

Catalyst: WS-C2960S-48LPS-L
Port: Gi1/0/3
Mode: access
VLAN: 10 Home
```

Policy:

```text
NIC1 / Gi1/0/3 = DO NOT TOUCH
```

## 3. NIC2 — Storage Network

```text
Physical NIC: enp7s0f1
MAC: 44:1e:a1:61:e8:d9
IP: 192.168.2.220/24
Subnet: 192.168.2.0/24
Gateway: none
Speed: 1000 Mb/s Full
Bridge: none
Bond: none
VLAN subinterfaces: none

Catalyst port: Gi1/0/48
Mode: access
VLAN: 40 Storage_Data
PortFast: no
Port-security: disabled
Storm-control: none
STP: forwarding
```

## 4. File Server

```text
IP: 192.168.2.200
MAC: 00:1d:7d:0a:63:74
Protocol: NFSv4
Export: /Data_1
OMV mount: /srv/remotemount/Data_1

Catalyst port: Gi1/0/47
Mode: access
VLAN: 40 Storage_Data
Speed: 1000 Mb/s Full
PortFast: yes
```

## 5. Storage VLAN

```text
VLAN ID: 40
Name: Storage_Data
Subnet: 192.168.2.0/24
Current delivery: untagged/access
Catalyst SVI: none
RSPAN role: disabled
```

Path:

```text
OMV enp7s0f1
→ Gi1/0/48
→ VLAN40
→ Gi1/0/47
→ File Server 192.168.2.200
```

## 6. Catalyst

```text
Model: WS-C2960S-48LPS-L
IOS: 15.2(2)E9
```

Configured VLANs:

```text
1,10,20,30,40,50,105,205
```

Potential future RSPAN candidate:

```text
VLAN 999
```

Not created.

## 7. Current SPAN / RSPAN

```text
SPAN Session 1
Type: Local
Source VLANs: 10,20
Direction: Both
Destination: Gi1/0/40
```

```text
Current RSPAN VLANs: none
```

Planning state:

```text
Existing source session: 1
Additional source-session slot: 1
```

## 8. CaptivPortal VM

```text
VM: Ubunt
IP: 192.168.0.202
Current vNIC count: 1

vNIC #1:
  Model: virtio
  MAC: 52:54:00:0d:2f:54
  Bridge: br0
  Runtime: vnet1
```

A second independent `virtio` vNIC can technically be added later without changing vNIC #1.

## 9. Target Sensor Concept

```text
NIC1 / enp7s0f0 / Gi1/0/3
→ unchanged
→ br0
→ CaptivPortal vNIC #1 / 192.168.0.202

NIC2 / enp7s0f1 / Gi1/0/48
→ future trunk
   ├─ native/untagged VLAN40
   │    → existing Storage_Data / NFS
   │
   └─ tagged RSPAN VLAN
        → isolated monitoring bridge
        → CaptivPortal vNIC #2
        → passive Device Fingerprint Sensor
```

## 10. Architectural Verdict

```text
NIC2 = existing Storage network + tagged RSPAN
TECHNICALLY FEASIBLE
```

Conditions:

1. Preserve VLAN40 as existing untagged/native Storage network.
2. Carry RSPAN as a separate tagged VLAN.
3. Do not convert Gi1/0/48 into a local SPAN destination.
4. Keep mirror L2 isolated from br0.
5. No default-route/management role on sensor interface.
6. Measure combined NFS + mirror bandwidth on the shared 1 Gb/s link.
7. Treat access→trunk conversion as a controlled change with rollback.
8. Preserve CaptivPortal vNIC #1 unchanged.

## 11. Baseline Status

```text
READ-ONLY PRECHECK: COMPLETE
NETWORK MODIFICATIONS: NONE
VM MODIFICATIONS: NONE
SPAN/RSPAN MODIFICATIONS: NONE
STORAGE INTERRUPTION: NONE
```
