# K2A local conformance evidence

`run_conformance.py` is an explicitly invoked, offline conformance command. It
checks the three pinned p0f artifact hashes before invoking the local binary,
replays the retained 544 synthetic PCAPs without altering them, and compares
the frozen `tcp_syn/2` adapter/matcher with a small generated request-side
signature instrument. It does not import the upstream corpus into production.

The generated `evidence/` directory contains fixture digests, canonical
`tcp_syn/2` vectors, transient adapter outputs, signature sets, oracle output,
matcher output, comparison status, and the candidate package. The source
governance records are candidates for Owner/TechLead review, not admission.

The oracle workspace, including the p0f source, binary, archive, and complete
`p0f.fp`, remains external to this repository. No real capture, root privilege,
production database, sensor, or network access is used.
