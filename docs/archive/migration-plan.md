# План миграции существующих документов

Status: current migration map; archive operations require separate approval
Updated: 2026-08-04
Runtime baseline: main `227ebe93831447d16b78f277ee3052ddd06e15a3`

## Значение действий

- `keep` — оставить файл на текущем пути; он сохраняет собственную роль.
- `supersede` — передать нормативную роль новому источнику истины, но не удалять и не перемещать старый файл без отдельного approval.
- `archive` — переместить в `docs/archive/` только после отдельного пофайлового approval, сохранив содержимое и header с новым источником истины.

Merge knowledge base передаёт нормативную роль новым module contracts для строк `supersede`; прежние документы получают короткий status/header со ссылкой на current contract, но не удаляются и не перемещаются. Любой `archive` остаётся отдельным repository action.

## Repository files

| Текущий путь | Действие | Новый источник истины | Причина |
|---|---|---|---|
| README.md | keep | README.md + docs/README.md для глубокой навигации | Англоязычный public overview остаётся самостоятельной точкой входа |
| README_RU.md | keep | README_RU.md + docs/README.md для глубокой навигации | Русскоязычный public overview остаётся самостоятельной точкой входа |
| .env.example | keep | .env.example; семантика параметров сверяется с app/config.py и app/settings.py | Действующий configuration example, не исторический документ |
| docs/CAPPORT.md | supersede | docs/modules/capport.md | Новый module contract объединяет границы, lifecycle, tests и запрещённые изменения |
| docs/auth_retry.md | supersede | docs/modules/authorization.md | Retry является частью единого authorization contract |
| docs/auth_telemetry.md | supersede | docs/modules/auth-telemetry.md | Нормативный module contract переносится в единый формат |
| docs/portal_counter.md | supersede | docs/modules/public-authorization-counter.md | Нормативный module contract переносится в единый формат |
| docs/public_traffic.md | supersede | docs/modules/public-traffic-counter.md | Нормативный module contract переносится в единый формат |
| docs/public_traffic.env.example | keep | docs/public_traffic.env.example; значения и имена сверяются с фактическим config code | Это configuration example, а не архитектурный источник |
| docs/visitor_snapshot_collector.md | supersede | docs/modules/authorized-client-snapshot.md | Новый module contract становится навигационным источником истины |
| docs/visitor_device_registry.md | supersede | docs/modules/visitor-registry.md | Новый module contract становится навигационным источником истины |
| docs/omada_webhook_receiver.md | supersede | docs/modules/omada-webhook-receiver.md | Новый contract отделяет application boundary от infrastructure |
| docs/omada_webhook_normalizer.md | supersede | docs/modules/omada-webhook-normalizer.md | Новый contract отделяет schema/normalization от transport setup |
| docs/omada_webhook_alloy.md | keep | docs/omada_webhook_alloy.md; docs/deployment.md задаёт только ownership boundary | Это конкретный infrastructure reference, не заменяемый общим deployment overview |
| outputs/omada-webhook-normalized.alloy | keep | файл остаётся infrastructure artifact; ownership решается отдельным TASK | Documentation migration не меняет Alloy configuration |

На текущем этапе действие `archive` не назначено ни одному repository file. Девять строк `supersede` помечены в исходных документах ссылкой на current contract. После Architect/Tech Lead review для конкретного старого файла может быть отдельно одобрен переход `supersede → archive`.

## Внешние Omada research reports

Эти источники не находятся в snapshot repository, но использовались при подготовке curated API contract. Они не являются «устаревшей документацией» и не архивируются автоматически.

| Текущий путь/источник | Действие | Новый источник истины | Причина |
|---|---|---|---|
| Отчёт об исследовании Omada Open API.docx | keep | исходный отчёт остаётся evidence; docs/api/omada-open-api.md — curated usage contract | Curated contract не заменяет экспериментальные наблюдения и raw research context |
| Отчёт об исследовании Omada Open API (1).docx | keep | исходный отчёт остаётся evidence; docs/api/omada-open-api.md — curated usage contract | Дополнительное исследование сохраняет доказательную ценность |
| Отчёт об исследовании сброса сессии Omada.docx | keep | исходный отчёт остаётся evidence; docs/api/omada-open-api.md — curated reconnect contract | Live результаты reconnect/disconnect/delete нужны для повторной архитектурной проверки |
| Pending Client Session Cleaner v1.0.docx | keep | исходное ТЗ Cleaner; current truth — merged code/tests + docs/modules/pending-session-cleaner.md | ТЗ сохраняет change-intent и acceptance evidence, но не подменяет merged implementation |

## Порядок будущей миграции

1. Сравнить каждый `supersede`-файл с current module contract по фактам и примерам.
2. Исправить current contract, если в нём потеряна актуальная информация.
3. Получить пофайловое решение Architect/Tech Lead для возможного archive.
4. Только затем переместить отдельно одобренный файл в `docs/archive/` с header `Superseded by`.
5. Ничего не удалять автоматически; research reports сохранять как evidence.

Pending-session probe/test artifacts не входят в таблицу: они уже удалены из main PR #28 до knowledge-base integration.
