# Repository actions

Status: current
Updated: 2026-08-04

TASK перечисляет allowed, forbidden и owner-only operations. Отсутствующее разрешение означает запрет.

## Read-only

- read files и history;
- inspect issues, pull requests и checks;
- run non-mutating diagnostics.

## Write branch

- create feature branch;
- modify allowed files;
- create intentional commits;
- push feature branch.

Каждое действие разрешается отдельно; write permission не означает push.

## Pull request

- open Draft PR;
- update Draft PR;
- respond to review.

PR по умолчанию Draft. Merge не следует из PR permission.

## Protected

Требуют отдельного прямого разрешения owner:

- merge;
- force push или rewrite history;
- delete branch;
- branch protection;
- release и production tag;
- deploy;
- production secrets;
- destructive data operation.

## Truthfulness

Запланированное действие не считается выполненным. Handoff различает proposed, attempted, completed и blocked.
