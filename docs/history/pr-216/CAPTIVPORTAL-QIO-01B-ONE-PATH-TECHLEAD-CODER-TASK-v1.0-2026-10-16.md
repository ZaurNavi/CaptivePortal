# CaptivPortal — QIO-01B / ONE PATH / Tech Lead Coder Implementation TASK v1.0

**Дата:** 2026-10-16 (Asia/Baku)  
**Решение Owner:** выбрать один наиболее простой безопасный путь, без конкурирующих реализаций.  
**Выбор:** **B ONLY — доверие существующему сертификату Omada в границах OmadaProvider, без модификации Omada Controller**.  
**Источник архитектуры:** `CAPTIVPORTAL-QIO-01B-OMADA-TLS-ARCHITECTURE-CONTRACT-RU-v1.0-2026-10-16(1).md`, §2.B, §3–5.  
**Роль:** Coder — только код + узкие тесты; Tech Lead — независимые full Windows/Linux и TLS/PERF/lifecycle gates; SysAdmin/Owner — управление именем/сертификатом и production GO. **Owner разрешил продвигать выбранный единственный путь в реализацию; это разрешение распространяется только на лабораторный coding, не на production.**  
**Текущее production:** main `59aaac88e24ece85f448fab9bbef43cf9ff34de4`, изменения в production **не разрешены** настоящим TASK.

## Решение, без альтернативной ветки

Единственная целевая конфигурация OmadaProvider:

- HTTPS origin: `https://Omada:8043` — **имя из SAN действующего сертификата**.
- Разрешение `Omada` только на нужном хосте CaptivPortal в `192.168.0.222`; SysAdmin обеспечивает локальную managed `/etc/hosts` запись после отдельного допуска Owner. На production сейчас `getent ahostsv4 Omada` не находит имя, `/etc/hosts` записи нет. Никакого изменения DNS сети, Cisco, EAP или конфигурации Omada.
- CA/trust для `requests`: строго **путь к утверждённому публичному PEM существующего самоподписанного leaf-сертификата**, отдельный root-owned read-only файл вне Git. Никаких приватных ключей. Сертификат с сетевого handshake не утверждается автоматически.
- TLS проверка цепочки, имени `Omada`, дат и ошибок обязательна; `verify=False`, warning suppression, HTTP fallback, urllib3 adapter с отключённым hostname, глобальный `REQUESTS_CA_BUNDLE` и системный CA trust **запрещены**.
- Достоверность сертификата **перед admission должна быть подтверждена Owner/SysAdmin по независимому экспорту из Omada**, а не только fingerprint из сетевого handshake. Сетевой SHA-256 для сверки: `DA5FCCE1212BE7B861D0E934235390CF1D6268351B9EE6C1DE31641EF2DC58AE` (НЕ самостоятельный trust anchor).

**Прямо исключено:** перевыпуск/импорт сертификата и рестарт Omada, альтернативная PKI-разработка, программная эмуляция DNS/SNI, глобальный TLS redesign, QIO-01D, QIO-02, настройка межсервисного TLS, массовые правки warning filters.

## Результат Coder — одна ветка, один PR после acceptance

1. Изолированный worktree/ветка `task/qio-01b-omada-strict-tls` от verified current `origin/main`; зафиксировать baseline SHA/tree и исходный diff.
2. В **Omada-only composition/config** ввести явно проверяемые `canonical_https_origin=https://Omada:8043`, `trust_anchor_path` и эффективный strict-mode. Конфигурация формируется **один раз при startup** из принятого settings snapshot; не раскрывает секреты и PEM. Минимально адаптировать `app/config.py`, `app/settings.py`, `app/controllers/omada_config.py`, `app/controllers/omada.py` и, при необходимости, admin read-only public projection. Без writable Admin UI toggle.
3. **Все** запросы Omada/OpenAPI (token, GET, auth/unauth, pending sessions, observations) используют один verified transport/policy. Сохранить существующие URI API paths, timeout, idempotency, concurrency, response parsing и mutation semantics. Защитить запросы с токенами от cross-origin redirect, downgrade и прокси/незапланированного origin. Не расширять trust за пределы OmadaProvider.
4. Проверять trust-file existence/readability, canonical origin и сертификат до разрешения Omada-операций. Missing/invalid/unapproved TLS policy — **fail closed**, без `verify=False` fallback и без ложных успешных auth/snapshot. Обеспечить, чтобы TLS failure не превращался в authoritative `get_sites() == []` либо «нулевых клиентов»: корректно обрабатывать этот частный legacy boundary и связанные явные ошибки, сохранив штатный контракт допустимых пустых данных.
5. TLS/rotation/expiry failure: первая ошибка + переход состояния должны оставаться видимыми в health/security logs, одинаковые повторные ошибки можно bounded-rate-limit без потери audit. Не скрывать негативные результаты. Отразить effective verification и source в read-only Admin projection без секретов; не добавлять меняющие состояние элементы Admin.
6. Документировать **только выбранный путь**: подготовка утверждённого PEM и `/etc/hosts`, проверка разрешения, read-only preflight, controlled app restart, rollback к предыдущему **строгому** trust policy (не к `verify=False`), контроль предупреждений, мониторинг expiry/rotation. Ни сертификат, ни рабочие credentials, ни продакшн env в Git не помещать.
7. Чётко отделить staging и production: Coder не пишет в `/etc/hosts` production, не извлекает приватные ключи, не меняет сертификат/controller и не деплоит. Продуктивный runtime остаётся прежним до отдельного Owner GO. Если baseline drift — STOP, без автоматического rebase.

## Минимальная focused test matrix Coder

- Верный самоподписанный leaf + SAN=`Omada` + approved PEM ⇒ строгое успешное TLS (без API mutations); неверный IP/имя, unknown cert, expired, неверный EKU/chain/bundle, proxy, cross-origin redirect, HTTP downgrade ⇒ fail closed, никаких credentials на чужой origin.
- Token lifecycle/cache, GET sites/clients, hotspot auth/unauth и обработка исключений — в **изолированных mock/test TLS fixtures** без реальных guest/Omada mutations.
- Failures не возвращают authoritative empty-site/empty-client state. Предыдущие controlled errors, timeouts, retry semantics сохраняются.
- Public projection показывает *effective strict* и provenance без значения PEM/секретов.
- Запрещён глобальный change в `requests`/certifi/trust/urllib3, `disable_warnings`, `verify=False` в новых путях.
- Coder выполняет **только узкие regression-тесты изменённых компонентов** + compileall/diff-check. Никакие full windows/linux / реальный PERF / production tests не выполнять от имени Coder.

## Предпосылки и строгие gates

- **Gate RV-1 (SysAdmin+Owner)**: независимый (не из сетевого handshake) экспорт сертификата Omada и SHA-256 match; подтверждение ownership IP/name; права на root-owned trust PEM и ротационный runbook. Пока это **не подтверждено**. Не применять доверие к сетевому сертификату по TOFU.
- **Gate RV-2 (Tech Lead)**: read-only: Linux production `Omada` не разрешается. Необходимо позже допустить managed entry и проверить резолюцию/прокси/SNI/Host в lab; `/etc/hosts` сейчас **не менять**.
- **Gate RV-3 (Tech Lead)**: инвентаризация всех OmadaProvider request sites и downstream TLS-failure consumers; оценить случаи `get_sites`/null state; не переиспользовать старое `verify_ssl=False` молча.
- **Gate LAB**: Tech Lead запускает независимые Windows full / Linux full, strict positive-negative TLS fixture + real Requests/OpenAPI *non-mutating staging* validation, проверку охвата auth/unauth path mocks, security/redirect, cert rotation, health, preflight.
- **Gate PROD**: отдельное Owner GO по точному принятому commit/tree и плану rollback. Никакого unattended deploy. Переключение новой конфигурации и возможный рестарт **основного `captive-portal.service`** только в согласованном окне: OmadaProvider живёт в основном процессе, в отличие от отдельно работающего Fingerprint Integration Worker QIO-01A.
- **Gate PERF**: matched quiet + normal baseline / after, Omada warnings, journald cgroup `wios/wbytes`, portal guest cgroup, host physical `/dev/sda` — не заявлять эффект на физическом HDD до измерений.

## Статус GO

Это **единственное** направление, выбранное Owner. **Coder получает GO на изолированную LAB-разработку и узкие synthetic/mocked focused tests сейчас**, без живых запросов с Omada credentials и без реальных hotspot auth/unauth. Это осознанное Owner-решение начинать кодирование параллельно с RV-1/2/3. Архитектурные RV gates остаются обязательными **перед Tech Lead acceptance, GitHub publication GO и production activation**. Если для корректной реализации потребуются контроллерные сертификаты, credentials, real Omada API, SysAdmin изменения `/etc/hosts` или доверие к сетевому сертификату — STOP эту часть и передать blocker Tech Lead. Scope не расширять.

```ini
OPTION=B_ONLY
CONTROLLER_CERT_REISSUE=NO
OMADA_CONTROLLER_RESTART=NO
APP_SCOPED_STRICT_TLS=YES
REQUIRE_CERT_INDEPENDENT_CONFIRMATION=YES
REQUIRE_LAB_AND_OWNER_PROD_GO=YES
CODER_LAB_IMPLEMENTATION=GO
CODER_LIVE_OMADA_TESTS=HOLD_PENDING_RV_GATES
PUBLICATION_GO=NO
FULL_GATES=TECH_LEAD
PRODUCTION_ACTION=NO
```
