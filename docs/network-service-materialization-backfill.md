# NI-04 G4: bounded background recovery

The generation captures H, the committed feed high-water, once. Live delivery
starts above H. A separate durable keyset scans only the captured 24-hour window,
one Site at a time, at most 128 edges per page and at most one page per second.
Backfill yields whenever live delivery has a backlog. Restart resumes the committed
Site/event/edge cursor; it does not restart the scan or move confirmed facts.

The shared worker/store foundation includes the paging lane so live delivery,
Registry replay and backfill use exactly one evaluator and transaction boundary.
G4 additionally verifies pagination, resume, overlap, throttle and live priority.

Retention gaps are not successful processing. Bounded checkpoint recovery fields
record the frozen recovery high-water and cutoff, plus the independently consumed
new-live cursor. The original delivery cursor remains unchanged until the captured
recovery scan completes atomically. A gap timestamp still forbids complete negative
coverage for its affected 24-hour window, even after catch-up. No source rows are
deleted or reconstructed to hide a gap.

Legitimately expired SNI produces no positive; retained endpoint expiry preserves
the accepted direct-SNI evidence semantics and marks coverage limited. Source I/O
or integrity failures do not advance a feed, replay or backfill cursor.

This document and its tests confer no migration, feature activation or deployment
authority. The Owner controls all production operations.
