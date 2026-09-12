# Repository actions

Status: current
Updated: 2026-09-12
Acceptance-before-Publication governance effective: 2026-08-30

TASK перечисляет allowed, forbidden и owner-only operations. Отсутствующее
разрешение означает запрет.

## Read-only

- read files/history;
- inspect issues, pull requests and checks;
- run non-mutating diagnostics.

## Implementation / Lab transport

Patch is the normal implementation/handoff/Central Lab transport artifact.

A patch or LAB-only commit is not publication and is not production code identity.

Central Lab may materialize an exact candidate as a local immutable LAB ONLY
commit. That commit:

- is not pushed;
- is not a publication commit;
- is not a merge source;
- is not a production source.

## Acceptance before Publication

Normal publication is authorized only after **all mandatory acceptance gates for
the exact candidate tree have PASS**.

Mandatory gates may include:

- focused/targeted tests;
- Central Lab current official full-regression gate (currently V7 strict);
- Linux/production-compatible gate;
- production-size PERF/capacity;
- migration/schema compatibility;
- security/browser acceptance;
- any other gate required by TASK/FINAL/release contract.

Before full acceptance:

```text
publication commit: NO
push as accepted artifact: NO
PR as accepted/mergeable release artifact: NO
merge: NO
deploy: NO
activation: NO
```

A TEST-ONLY / EXPERIMENTAL publication before acceptance requires explicit
Owner + Tech Lead authorization and must be labelled:

```text
NOT ACCEPTED
NOT MERGEABLE
NOT DEPLOYABLE
```

It is an exception, not the normal workflow.

## Publication

After acceptance, allowed publication actions may be separately authorized:

- create publication commit;
- create/push feature branch;
- open/update Draft PR;
- respond to review.

Chain-of-custody target:

```text
accepted candidate tree
=
publication commit tree
=
PR head tree
=
accepted merge tree
```

unless a deliberately chosen merge strategy changes the tree. Any production or
test-file change after acceptance creates a new candidate tree and requires
re-evaluation/repetition of the necessary gates.

## Web Designer accepted-candidate publication

The Web Designer / Admin Console UI Designer role remains presentation-only.

Default flow:

```text
local presentation candidate / PATCH
→ Tech Lead + Owner scope review
→ required test gate
→ visual acceptance
→ ACCEPTED CANDIDATE
```

Repository write permission is not permanent. It is granted only after the exact
candidate is accepted and Owner / Tech Lead explicitly issue:

```text
PUBLISH APPROVED CANDIDATE
```

That authorization permits only:

```text
feature branch from specified baseline
accepted-candidate-only commit
push that feature branch
Draft PR to main
```

Before publication, exact match between accepted artifact and publication diff
must be proven.

Still forbidden without separate authorization:

```text
modify main
merge
deploy/release
force-push/history rewrite
post-acceptance extras
scope expansion
backend/API/data/security/business/system logic changes
```

A Coder is not required merely to publish a purely presentation-only accepted
candidate. Publication handoff must include TASK, baseline SHA, branch, commit
SHA, changed files, diff stat, exact artifact match, `NO EXTRAS`, Draft PR,
`MERGE=NO`, `DEPLOY=NO`.

## Protected

Require separate direct Owner authorization:

- merge;
- force push / history rewrite;
- branch deletion;
- branch protection;
- release / production tag;
- deploy;
- production secrets;
- destructive data operation.

## Git is the production code delivery boundary

Normal production application code comes only from:

```text
Git repository
+
explicit verified SHA/tree
```

Not from:

- local patch;
- copied source files;
- SCP patch;
- workstation ZIP/archive;
- manual file replacement;
- Central Lab worktree;
- Coder worktree.

Direct patch/source transfer to production is allowed only as an explicit
controlled emergency exception approved for the incident by Owner + Tech Lead.
After the incident, repository/Git truth must be reconciled.

## Truthfulness

Planned action is not an executed action. Handoff distinguishes proposed,
attempted, completed and blocked.
