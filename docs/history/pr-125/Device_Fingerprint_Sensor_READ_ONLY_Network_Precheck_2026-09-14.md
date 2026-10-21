# Device Fingerprint Sensor — READ-ONLY Network Precheck Report

**Project:** CaptivPortal  
**Area:** Infrastructure / Future Device Fingerprint Sensor  
**Host:** OMV7 `omv-hp`  
**Date:** 2026-09-14  
**Status:** READ-ONLY PRECHECK COMPLETE  
**Configuration changes:** NONE

## 1. Scope

Цель precheck — зафиксировать фактическую текущую сетевую схему OMV7, Catalyst, storage-сети и CaptivPortal VM перед будущим Device Fingerprint Sensor / RSPAN.

Не выполнялось:
- изменение switchport mode;
- создание VLAN/RSPAN/SPAN;
- изменение bridge/IP/routes;
- networking restart;
- изменение CaptivPortal VM;
- создание второго vNIC;
- отключение файлового сервера.

## A. OMV NIC1 facts — Primary Network

```text
Physical NIC: enp7s0f0
Physical MAC: 44:1e:a1:61:e8:d8
Link: UP
Speed: 1000 Mb/s
Duplex: Full
Autonegotiation: On
Master: br0

Bridge: br0
Bridge MAC: a2:dc:57:31:19:0d
OMV IP: 192.168.0.220/24
Default gateway: 192.168.0.1
Network: 192.168.0.0/24

Catalyst port: Gi1/0/3
Switch mode: static access
Access VLAN: 10 (Home)
```

Current switch configuration:

```cisco
interface GigabitEthernet1/0/3
 switchport access vlan 10
 switchport mode access
```

Decision:

```text
NIC1 / Gi1/0/3 = DO NOT TOUCH
```

## B. OMV NIC2 facts — Storage Network

```text
Interface: enp7s0f1
MAC: 44:1e:a1:61:e8:d9
IP: 192.168.2.220/24
Network: 192.168.2.0/24
Link: UP
Speed: 1000 Mb/s
Duplex: Full
Autonegotiation: On
Bridge: none
Bond: none
VLAN subinterfaces: none
Default gateway through NIC2: none
```

Route:

```text
192.168.2.0/24 dev enp7s0f1 proto kernel scope link src 192.168.2.220
```

## C. File-server Network / VLAN facts

```text
File Server IP: 192.168.2.200
File Server MAC: 00:1d:7d:0a:63:74
Protocol: NFSv4
Export: 192.168.2.200:/Data_1
OMV mount: /srv/remotemount/Data_1
```

Observed active NFS session:

```text
192.168.2.220:970 -> 192.168.2.200:2049 ESTABLISHED
```

VLAN:

```text
Subnet: 192.168.2.0/24
VLAN ID: 40
Name: Storage_Data
Delivery: untagged/access
Gateway for OMV <-> File Server: not required
Catalyst SVI Vlan40: not present
```

Physical path:

```text
OMV enp7s0f1
→ Catalyst Gi1/0/48
→ VLAN40 Storage_Data
→ Catalyst Gi1/0/47
→ File Server 192.168.2.200
```

## D. Catalyst NIC2 Port + Relevant Configuration

Switch:

```text
Model: Cisco WS-C2960S-48LPS-L
IOS: 15.2(2)E9
Image family: C2960S-UNIVERSALK9-M
```

OMV NIC2 port:

```text
Port: Gi1/0/48
Status: connected
Speed: 1000 Mb/s
Duplex: Full
Mode: static access
Access VLAN: 40 (Storage_Data)
PortFast: no
Port-security: disabled
Storm-control: not configured
STP: designated forwarding
```

```cisco
interface GigabitEthernet1/0/48
 switchport access vlan 40
 switchport mode access
```

File-server port:

```text
Port: Gi1/0/47
Status: connected
Speed: 1000 Mb/s
Duplex: Full
Mode: static access
Access VLAN: 40 (Storage_Data)
PortFast: yes
Port-security: disabled
Storm-control: not configured
STP: designated forwarding
```

```cisco
interface GigabitEthernet1/0/47
 switchport access vlan 40
 switchport mode access
 spanning-tree portfast
```

MAC evidence:

```text
44:1e:a1:61:e8:d9 -> VLAN40 -> Gi1/0/48
00:1d:7d:0a:63:74 -> VLAN40 -> Gi1/0/47
```

## E. Existing SPAN / RSPAN State

```text
Session 1
Type: Local SPAN
Source VLANs: 10,20
Direction: Both
Destination: Gi1/0/40
Ingress: enabled
Default VLAN: 10
```

RSPAN:

```text
Current RSPAN VLANs: none
VLAN40 Remote-SPAN role: disabled
```

Configured VLANs:

```text
1,10,20,30,40,50,105,205
```

Planning candidate for future RSPAN:

```text
VLAN 999
```

Not created.

For this Catalyst generation, current planning assumption after model/IOS verification:
- one Local SPAN source session is already in use;
- one additional source-session slot remains available for future RSPAN source use.

## F. CaptivPortal VM Current vNIC Configuration

Cisco ARP proof:

```text
192.168.0.202 -> 52:54:00:0d:2f:54
```

Libvirt mapping:

```text
VM name: Ubunt
Current vNIC count: 1
MAC: 52:54:00:0d:2f:54
Model: virtio
Source bridge: br0
Runtime tap: vnet1
Guest IP: 192.168.0.202
```

Persistent interface:

```xml
<interface type='bridge'>
  <mac address='52:54:00:0d:2f:54'/>
  <source bridge='br0'/>
  <model type='virtio'/>
  <address type='pci' domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
</interface>
```

## G. Ability to Add a Second vNIC

Technically supported.

Existing first vNIC can remain unchanged:

```text
virtio #1
→ br0
→ enp7s0f0
→ VLAN10
→ 192.168.0.202
```

Future second vNIC can be separate:

```text
virtio #2
→ dedicated monitoring bridge
→ passive sensor path
```

No second vNIC was created during precheck.

## H. Feasibility: NIC2 = Existing Storage + Tagged RSPAN

**Sysadmin verdict: technically feasible.**

Target concept:

```text
Catalyst Gi1/0/48
→ future 802.1Q trunk
   ├─ native/untagged VLAN40
   │    → existing Storage_Data
   │    → enp7s0f1 / 192.168.2.220
   │
   └─ tagged RSPAN VLAN
        → isolated OMV monitoring path
        → second CaptivPortal VM virtio NIC
```

Important:

```text
Gi1/0/48 should remain a normal trunk carrying:
- VLAN40 storage traffic
- tagged RSPAN VLAN

Gi1/0/48 should NOT become a local SPAN destination port.
```

## I. Risks / Limitations

1. **Shared 1 Gb/s link**  
   NFS and future mirror traffic will share `Gi1/0/48 <-> enp7s0f1`.

2. **Access → trunk migration risk**  
   Any native/allowed VLAN mistake could temporarily interrupt NFS.

3. **STP behavior**  
   Current Gi1/0/48 is not PortFast; future host-facing trunk behavior needs explicit design.

4. **Monitoring isolation**  
   Prefer:
   ```text
   no management IP on mirror interface
   no default route
   no DHCP
   no accidental bridge into br0
   no forwarding into production networks
   ```

5. **SPAN source-session capacity**  
   Existing Session 1 already occupies one source-session slot.

6. **Duplicate mirror load**  
   Mirroring VLAN10/20 both to local SPAN and future RSPAN creates an additional mirrored copy.

## J. Raw Evidence Summary

```text
OMV NIC1:
enp7s0f0
44:1e:a1:61:e8:d8
master br0
1000 Mb/s Full

OMV NIC2:
enp7s0f1
44:1e:a1:61:e8:d9
192.168.2.220/24
1000 Mb/s Full

OMV bridge:
br0
192.168.0.220/24
```

```text
Storage:
192.168.2.200:/Data_1
NFSv4
/srv/remotemount/Data_1
```

```text
Catalyst:
OMV primary bridge MAC a2:dc:57:31:19:0d -> VLAN10 -> Gi1/0/3
OMV NIC2 44:1e:a1:61:e8:d9 -> VLAN40 -> Gi1/0/48
File Server 00:1d:7d:0a:63:74 -> VLAN40 -> Gi1/0/47
```

```text
CaptivPortal VM:
192.168.0.202
52:54:00:0d:2f:54
VM Ubunt
virtio
br0
vnet1
```

## Final Decision

```text
READ-ONLY PRECHECK: PASS
Technical feasibility: GO for architecture design
Implementation: NOT AUTHORIZED BY THIS REPORT
```
