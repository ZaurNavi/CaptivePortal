# DEVICE-FINGERPRINT-SENSOR / INFRA CHANGE-A  
## Catalyst Transport Preparation — Execution Report

**Project:** CaptivPortal  
**Task:** DEVICE-FINGERPRINT-SENSOR / INFRA CHANGE-A  
**Scope:** Catalyst-side transport preparation for future passive Device Fingerprint Sensor  
**Date:** 2026-09-14  
**Result:** PASS / COMPLETE  
**Configuration saved:** YES (`write memory` → `[OK]`)  
**STOP boundary respected:** YES

---

## 1. Objective

Prepare Catalyst transport so that the second physical NIC of the OMV host can later carry:

- existing Storage_Data traffic via untagged/native VLAN40;
- future passive Device Fingerprint mirrored traffic via tagged RSPAN VLAN999.

At this stage OMV/KVM/CaptivPortal VM configuration was explicitly out of scope.

---

## 2. Baseline

### OMV

```text
Host: omv-hp
Primary IP: 192.168.0.220
```

NIC1:

```text
enp7s0f0
→ Linux bridge br0
→ Catalyst Gi1/0/3
→ access VLAN10
```

NIC1 was classified as critical and remained completely unchanged.

NIC2:

```text
enp7s0f1
IP: 192.168.2.220/24
→ Catalyst Gi1/0/48
→ access VLAN40 Storage_Data
```

File Server:

```text
IP: 192.168.2.200
MAC: 00:1d:7d:0a:63:74
→ Catalyst Gi1/0/47
→ access VLAN40
Protocol: NFSv4
Mount: /srv/remotemount/Data_1
```

Existing laboratory SPAN:

```text
Session 1
Type: Local SPAN
Source VLANs: 10,20
Direction: BOTH
Destination: Gi1/0/40
```

This laboratory SPAN was no longer required and was authorized for permanent removal.

---

## 3. Before-State Verification

Before any configuration change, the following was confirmed.

Gi1/0/48:

```cisco
interface GigabitEthernet1/0/48
 switchport access vlan 40
 switchport mode access
```

VLAN40:

```text
VLAN 40
Name: Storage_Data
Status: active
Ports: Gi1/0/47, Gi1/0/48
Remote SPAN VLAN: Disabled
```

Storage baseline:

```text
enp7s0f1 = 192.168.2.220/24
192.168.2.200 neighbor = REACHABLE
Ping = 4/4, 0% loss
NFSv4 mount = present
TCP/2049 = ESTABLISHED
stat /srv/remotemount/Data_1 = successful
```

Before-state gate: PASS.

---

## 4. Change Performed

### 4.1 Old Local SPAN removed

```cisco
no monitor session 1
```

Result:

```text
No SPAN configuration is present in the system.
```

Gi1/0/40 therefore ceased to be a SPAN destination.

Old laboratory SPAN was not restored.

### 4.2 RSPAN VLAN created

```cisco
vlan 999
 name RSPAN_DEVICE_FP
 remote-span
```

Verification:

```text
VLAN 999
Name: RSPAN_DEVICE_FP
Status: active
Remote SPAN VLAN: Enabled
```

`show vlan remote-span`:

```text
999
```

No SVI, IP address, gateway, DHCP or production role was configured for VLAN999.

### 4.3 Gi1/0/48 converted from access to trunk

Configured:

```cisco
interface GigabitEthernet1/0/48
 switchport trunk native vlan 40
 switchport trunk allowed vlan 40,999
 switchport mode trunk
```

Final operational state:

```text
Administrative Mode: trunk
Operational Mode: trunk
Encapsulation: 802.1Q
Native VLAN: 40 Storage_Data
Allowed VLANs: 40,999
```

Final running configuration:

```cisco
interface GigabitEthernet1/0/48
 switchport access vlan 40
 switchport trunk native vlan 40
 switchport trunk allowed vlan 40,999
 switchport mode trunk
```

The residual `switchport access vlan 40` line remains in the IOS configuration but is inactive while the interface operates in trunk mode.

Global command:

```text
vlan dot1q tag native
```

was not present.

Therefore VLAN40 continues to be carried as the untagged/native VLAN on Gi1/0/48, allowing OMV `enp7s0f1` to remain completely unchanged.

---

## 5. Storage Validation After access → trunk Migration

Immediately after switching Gi1/0/48 to trunk mode, the first short ping test showed:

```text
5 transmitted
3 received
40% packet loss
```

NFS remained mounted and readable during this transition.

A dedicated stability gate was then executed.

Final stability result:

```text
20 transmitted
20 received
0% packet loss
RTT avg ≈ 0.112 ms

Neighbor 192.168.2.200 = REACHABLE

NFSv4 mount = present
rw
clientaddr = 192.168.2.220

Directory read:
ls exit=0

TCP/2049:
ESTABLISHED
```

Catalyst STP showed Gi1/0/48 forwarding for both:

```text
VLAN0040 = designated forwarding
VLAN0999 = designated forwarding
```

The initial 2 lost packets were therefore treated as a transient migration/STP/MAC relearning event rather than an ongoing Storage failure.

Storage migration gate: PASS.

---

## 6. RSPAN Source Session Created

Initial syntax attempt:

```cisco
monitor session 1 source vlan 10,20 both
```

was rejected by this IOS parser at the `both` argument.

No production impact resulted.

The source VLANs were then configured using IOS-compatible separate commands:

```cisco
monitor session 1 source vlan 10
monitor session 1 source vlan 20
monitor session 1 destination remote vlan 999
```

Final verification:

```text
Session 1
---------
Type                     : Remote Source Session
Source VLANs             :
    Both                 : 10,20
Dest RSPAN VLAN          : 999
```

Therefore final mirror path is:

```text
VLAN10 + VLAN20
        ↓
Direction: BOTH
        ↓
RSPAN Session 1
        ↓
Remote VLAN999
        ↓
tagged on Gi1/0/48
```

---

## 7. Final Acceptance Evidence

### RSPAN

```text
Session 1
Type: Remote Source Session
Source VLANs BOTH: 10,20
Destination RSPAN VLAN: 999
```

### Gi1/0/48

```text
Mode: trunk
Operational mode: trunk
Native VLAN: 40
Allowed VLANs: 40,999
```

### VLAN999

```text
Name: RSPAN_DEVICE_FP
Status: active
Remote SPAN VLAN: Enabled
```

### Storage MAC mappings

```text
OMV NIC2
MAC 44:1e:a1:61:e8:d9
→ VLAN40
→ Gi1/0/48

File Server
MAC 00:1d:7d:0a:63:74
→ VLAN40
→ Gi1/0/47
```

### Final Storage verification

```text
192.168.2.220 → 192.168.2.200
20/20 replies
0% packet loss

NFSv4 mount:
WORKING

/srv/remotemount/Data_1:
READ WORKING

TCP/2049:
ESTABLISHED
```

### Gi1/0/47

Unchanged:

```cisco
interface GigabitEthernet1/0/47
 switchport access vlan 40
 switchport mode access
 spanning-tree portfast
```

### Critical NIC1 / Gi1/0/3

Unchanged:

```cisco
interface GigabitEthernet1/0/3
 switchport access vlan 10
 switchport mode access
```

### OMV

Unchanged:

```text
enp7s0f1 = 192.168.2.220/24
No VLAN40 subinterface created
No bridge changes
No route changes
No networking restart
```

### CaptivPortal VM

Unchanged:

```text
VM IP: 192.168.0.202
No second vNIC created
No KVM/libvirt modification
No guest network modification
```

### Old Local SPAN

Removed:

```text
Gi1/0/40 = NO LONGER SPAN DESTINATION
```

---

## 8. Saved Configuration

After all acceptance gates passed:

```cisco
write memory
```

Result:

```text
Building configuration...
[OK]
```

Catalyst running configuration was successfully persisted to startup configuration.

---

## 9. Final State

```text
DEVICE-FINGERPRINT-SENSOR / INFRA CHANGE-A

STATUS: PASS
STATE: COMPLETE

CATALYST TRANSPORT: READY

Gi1/0/48:
  TRUNK
  native VLAN40
  allowed VLAN40,999

Storage VLAN40:
  WORKING

OMV NIC2:
  192.168.2.220/24
  UNCHANGED

File Server:
  192.168.2.200
  NFSv4 WORKING

RSPAN VLAN999:
  ACTIVE
  remote-span ENABLED

RSPAN Session 1:
  SOURCE VLAN10,20
  DIRECTION BOTH
  DESTINATION remote VLAN999

Old Local SPAN Gi1/0/40:
  REMOVED

NIC1 / Gi1/0/3:
  UNCHANGED

OMV network configuration:
  UNCHANGED

CaptivPortal VM 192.168.0.202:
  UNCHANGED

Second VM vNIC:
  NOT CREATED

CONFIG SAVED:
  YES
```

## 10. STOP

`INFRA CHANGE-A` ends at the Catalyst transport boundary.

No OMV, Linux VLAN, bridge, KVM, libvirt, second vNIC or CaptivPortal VM changes were performed.

Next-stage work requires a separate authorized task.