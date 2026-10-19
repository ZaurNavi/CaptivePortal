"""Future direct-collector ports. B1 deliberately has NO live implementation.

Only bounded OP-A synthetic receipts can be injected in offline tests. Channel
tags describe evidence, never authenticate a kernel reader. There is no trusted
Boolean, public parser, OS reader, source path opener or environment override.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .cgroup_v2 import CgroupSample
from .operational_contracts import require
from .operator_profile_binding import ProfileBinding
from .release_fence import OwnershipReceipt, ReapReceipt
from .resource_admission import Geometry


class ReceiptChannel(Enum):
    UNAVAILABLE = 'not_collected'
    OFFLINE_FIXTURE = 'offline_fixture'


class RootLayout(Enum):
    SYNTHETIC_EXPORTED = 'synthetic_exported_controls'
    ROOT_CONTROLS_ABSENT = 'root_control_files_absent_not_qualified'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True, repr=False)
class ResourceReceipts:
    binding: ProfileBinding
    before: CgroupSample
    after: CgroupSample
    geometry: Geometry
    root_layout: RootLayout

    def __post_init__(self):
        require(type(self.binding) is ProfileBinding and type(self.before) is CgroupSample
            and type(self.after) is CgroupSample and type(self.geometry) is Geometry
            and type(self.root_layout) is RootLayout, 'config_trust')


@dataclass(frozen=True, repr=False)
class ReleaseReceipts:
    binding: ProfileBinding
    reap: ReapReceipt
    before: CgroupSample
    after: CgroupSample
    ownership: OwnershipReceipt
    root_layout: RootLayout

    def __post_init__(self):
        require(type(self.binding) is ProfileBinding and type(self.reap) is ReapReceipt
            and type(self.before) is CgroupSample and type(self.after) is CgroupSample
            and type(self.ownership) is OwnershipReceipt and type(self.root_layout) is RootLayout,
            'orphan_hold')


class ReceiptPorts(Protocol):
    """Future qualified implementation must collect directly, never via clients.

    Resource reads follow child-owned global flock; release reads follow actual
    wait/reap. No implementation of live collection is admitted by this interface.
    Returning a dataclass does not prove OS provenance. B1 accepts synthetic data
    ONLY for a simulation and still denies all real execution and release.
    """
    channel: ReceiptChannel

    def resources(self) -> ResourceReceipts | None: ...
    def release(self) -> ReleaseReceipts | None: ...


class UnavailableReceiptPorts:
    channel = ReceiptChannel.UNAVAILABLE

    def resources(self):
        return None

    def release(self):
        return None
