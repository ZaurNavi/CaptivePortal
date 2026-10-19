# CAPTIVPORTAL — QIO-01B: архитектурный контракт безопасного TLS с Omada

**Версия:** v1.0, 16.10.2026 (Asia/Baku)  
**От:** Performance & Optimization Researcher / Architect Review  
**Кому:** Tech Lead оптимизации CaptivPortal  
**Основание:** QIO-01 Journaling Root Cause; распоряжение `QIO-01B PRIORITY_ARCHITECTURE_REVIEW`  
**Статус:** `ARCHITECTURE_CONTRACT=APPROVED_FOR_READONLY_AND_LAB_VALIDATION` · `CODER=HOLD` · `PRODUCTION_CHANGES=NO`. **Это не Coder TASK и не Owner GO.**

## 1. Подтверждённая проблема и уровень доказательств

Tech Lead установил за 3 минуты: `captive-portal.service` выдал **191** запись в journald, из них **178 строк сопровождали 89 предупреждений** `urllib3 InsecureRequestWarning`. Это число записей журнала, **не** число физических операций HDD. Физический выигрыш ещё не доказан.

Исходный код: `app/config.py:VERIFY_SSL=False` → `app/settings.py:get_settings()` → `app/controllers/omada_config.py:build_omada_runtime_config()` → `OmadaProvider` → `requests.get/post(..., verify=self._verify_ssl)` для получения токена и OpenAPI-операций. Конфигурационный объект и публичный Admin snapshot сегодня отражают проверку как `bool`; архитектурный контракт требует уточнить эту модель.

Проведена **дополнительная read-only проверка TLS** с Ubuntu production до `192.168.0.222:8043` (без авторизации, без API-запросов, без записи конфигурации):

- Сертификат **самоподписанный**, Subject/Issuer `CN=localhost, O=TP-Link, OU=TP-Link`, RSA 2048 / SHA-256, EKU `TLS Web Server Authentication`.
- SAN: **`DNS:Omada`**, **IP SAN нет**; действителен с 25.07.2026 по **27.10.2028 UTC**.
- SHA-256 DER fingerprint наблюдаемого сертификата: `DA:5F:CC:E1:21:2B:E7:B8:61:D0:E9:34:23:53:90:CF:1D:62:68:35:1B:9E:E6:C1:DE:31:64:1E:F2:DC:58:AE`. Это **пока только сетевое свидетельство**, не независимое подтверждение подлинности! Для одобрения trust anchor требуется отдельная сверка из доверенного источника Owner/Omada.
- Python `ssl.create_default_context(cadata=PEM)` + TCP к `192.168.0.222:8043` + `server_hostname='Omada'` → **успешно проверенный TLS 1.3**. Тот же сертификат при `server_hostname='192.168.0.222'` → **IP mismatch**; при `server_hostname='localhost'` → **hostname mismatch**.

**Главная причина:** приложение не доверяет этому сертификату явно и обращается по IP, который не совпадает с SAN. Настройка доверия не исправляет mismatch имени; смена имени без trust anchor не исправляет цепочку доверия. `CN=localhost` нельзя применять вместо SAN (RFC 9525).

## 2. Архитектурное решение

**Основной путь — B: строгое application-scoped доверие существующему сертификату с именем `Omada`, без модификации контроллера.** Это допустимый кандидат, потому что read-only TLS-проверка технически успешна. **Не считать этим доказанными работоспособность Requests/OpenAPI, инфраструктурную DNS-настройку или подлинность якоря доверия**: для них обязательны независимые проверки и staging.

**Альтернативный, более масштабный путь — A: установить на Omada новый сертификат с правильным SAN и управляемым CA.** Это отдельное изменение контроллера, не объединяемое с первым Coder TASK. TP-Link документирует импорт HTTPS-сертификата для Software Controller и необходимость рестарта контроллера; точный способ импорта и rollback для **v5.14.31** нужно подтвердить на соответствующем тестовом экземпляре.

### B. Существующий сертификат, только CaptivPortal

1. Утвердить канонический HTTPS origin **`https://Omada:8043`** (имя без учёта регистра, строго соответствует `DNS:Omada`); не использовать как TLS identity `192.168.0.222` либо `localhost`. Локальное разрешение `Omada` → `192.168.0.222` допускается через управляемый `/etc/hosts` **после отдельного SysAdmin/Owner GO** или внутренний контролируемый DNS. Никаких изменений EAP inform, Omada hostname, portal URL либо Cisco в QIO-01B.
2. Независимо удостоверить исходный сертификат и установить **только его публичный PEM** как явно утверждённый trust anchor в отдельном, недоступном на изменение приложению root-owned файле вне Git-репозитория. **Приватный ключ контроллера не копировать.** Это pinning доверенного самоподписанного leaf, а не доверие к произвольному сертификату из сети. Передача сертификата при самом TLS handshake сама по себе **не подтверждает** подлинность.
3. Политика применяется **исключительно** к `OmadaProvider`: Requests `verify=<approved PEM CA bundle path>` или эквивалентная строгая SSLContext, **со включённой проверкой имени**. Не менять глобальный CA trust Linux, `certifi`, `REQUESTS_CA_BUNDLE` для всего процесса и другие HTTP-интеграции.
4. HTTPS URL, TLS SNI, reference hostname для верификации и HTTP Host согласованы с `Omada`. Endpoint привязан к утверждённым `scheme=https`, `host=Omada`, `port=8043`, допустимым API path. **Запрещены** обход имени через подмену HTTP `Host` при URL по IP; `verify=False`, `assert_hostname=False`, `urllib3.disable_warnings`, HTTP fallback, TOFU при ошибке и слепой custom adapter.
5. **Cross-origin redirect запрещён**, чувствительные заголовки/токены не уходят на другой host/port/protocol. Не допускать непроверенного proxy-посредника, подмены origin, redirect downgrade и неожиданного DNS/IP fallback. Если понадобится нестандартный SNI/address-binding transport — это новая архитектурная ревизия, а не реализация по умолчанию.
6. Обязательны owner/provenance адресного соответствия, права на bundle, проверки файла и valid cert до переключения runtime, безопасная диагностика без credentials. Любые сетевые запросы с авторизацией — только в изолированном Lab и затем после Owner GO.

### A. Новый сертификат на стороне Omada

1. Предпочтительно выделить стабильное управляемое DNS-имя контроллера и включить **точный DNS SAN**. Если клиенты должны продолжить обращаться именно к `https://192.168.0.222:8043`, новый сертификат **обязательно** должен иметь `iPAddress:192.168.0.222` в SAN. `CN` не компенсирует отсутствие IP SAN.
2. Сформировать ограниченный доверенный CA/issuer и обеспечить раздачу **CA-публичного сертификата** нужным клиентам. Ключ CA и приватный ключ Omada никогда не хранятся в CaptivPortal.
3. Проверить импорт keystore/ключа именно в Omada Controller v5.14.31, состояние других клиентов HTTPS/UI/API, restart impact на портал и EAP, backup/rollback, окна обслуживания. Сначала staging, затем отдельный Owner GO. **Не менять контроллер сейчас.**
4. Приложение всё равно применяет тот же **строгий** `OmadaProvider` TLS-контракт. Отличается лишь выпуск/ротация сертификатов и управление trust anchor.

## 3. Runtime и конфигурационный контракт

- Вместо неявного `verify_ssl:bool` архитектурно требуется **явный строгий профиль**: `canonical_https_origin`, `verification_mode=strict`, `trust_anchor_path`, подтверждённый origin, provenance/effective generation. При отсутствии утверждённой политики новая конфигурация не должна автоматически переходить на небезопасную.
- Конфигурация берётся из принятого startup settings snapshot. Не выполнять per-request перечитывание env. Учесть существующие `app/config.py` константы, `app/settings.py`, `OmadaControllerRuntimeConfig`, Settings-Control и публичную проекцию Admin. **Не вводить writable Admin UI TLS toggle без отдельного архитектурного договора.**
- Валидация canonical HTTPS origin: никаких URL credentials, query, fragment, нестандартного path/алиасов, произвольного HTTP, другого port/host. Убрать возможность смешать `strict` и `verify=False` в разных методах одного провайдера.
- Вся Omada коммуникация — token acquisition/cache/refresh, сайты, клиенты, hotspot auth/unauth, прочие методы — через единую policy. Сохранить timeout, API parser, concurrency, identity/authorization flow. `requests` transport change не должен менять другие сервисы.
- Публичная конфигурация/health должна честно показывать **effective TLS verification и выбранный trust policy**, а не только `bool`; статус сертификата и источник настроек без PEM/секретов. Корректно классифицировать `cert_unknown`, `name_mismatch`, `expired`, `trust_bundle_missing`, `tls_handshake`, `redirect_origin_violation` и т.п. Ограничивать повторное логирование одинакового дефекта, но **не скрывать** первый дефект, state transitions и security audit.

## 4. Fail-closed / ротация / восстановление

1. Неизвестный сертификат, неправильная SAN/цепочка, неприемлемые EKU/даты, нечитаемый trust bundle, неожиданная ротация, redirect/proxy/handshake failure = **Omada authority unavailable**. Никаких успешных `auth`/`unauth`/других мутаций и никакого оптимистического трактования пустого списка клиентов.
2. На downstream границах `Omada unavailable` **не равно** `zero clients`, `offline`, `unauthorized`, `no change` либо успешный snapshot. Не порождать ложные Visit/Registry/Current State переходы. При ошибке использовать явный неавторитетный state и границы freshness; нельзя терять audit/unknown provenance. Важно проверить существующий `get_sites()`, который возвращает `[]` на исключение: в новом fail-closed контракте TLS failure не должен маскироваться как authoritative empty.
3. **Граница гарантии:** уже авторизованные клиенты могут остаться в Omada до истечения времени или отдельной проверенной деавторизации. При недоступном TLS приложение не способно гарантировать мгновенный revoke для уже существующих сессий. `Fail-closed` в этой задаче означает прежде всего запрет **новых неподтверждённых успешных действий и ложных состояний**.
4. Текущий сертификат истекает **27.10.2028**: предупреждения до истечения (кандидат 30/14/7 дней, утверждает эксплуатация), ротационный runbook и alarm до отказа. При самоподписанном leaf новый сертификат **не является автоматически доверенным** даже при том же SAN. До смены контроллера заранее проверить и установить новый якорь доверия; допускается строго ограниченное окно двойного доверия старого+нового PEM с независимым approve и обязательным выводом старого. При неподготовленной смене — **fail closed + alert**, никогда автоматическое скачивание/принятие.
5. Переподключение проверяет новый peer cert, а долгоживущие connection pools не служат бесконечным доказательством новой идентичности; bounded lifetime и контрольная свежая handshake при maintenance/rotation без нового лог-спама.
6. **Rollback** — к предыдущему **строго проверенному** trust policy/origin или временной остановке Omada-зависимых операций до исправления. **Автоматический возврат к `VERIFY_SSL=False` запрещён.** Исключение из security policy — отдельное Owner/security решение вне QIO-01B.

## 5. Проверки до implementation TASK

### READ-ONLY: RV-1…RV-3

- **RV-1 сертификат:** сверить fingerprint/PEM с независимым подтверждённым экспортом с Omada, а не только с сетевой handshake. Сохранить в evidence issuer/SAN/EKU/dates/signature/chain count, OpenSSL/Python/Requests versions, валидное время. Не сохранять ключи или живые токены.
- **RV-2 имя и маршрутизация:** проверить существующую локальную резолюцию `Omada` (сейчас не доказана), управляемый путь `Omada` → `192.168.0.222`, DNS spoof/fallback/IPv6, влияние proxies, SNI и Host. Зафиксировать тесты позитивного `Omada` и отказов для `192.168.0.222`, `localhost`, unknown CA, неправильного SAN. Тест c Python `ssl` уже PASS, но **Requests/OpenAPI integration ещё не проверены**.
- **RV-3 потребители/совместимость:** инвентаризировать `OmadaProvider` callers и владельцев; OAuth access token, Omada OpenAPI, portal auth, background workers, Admin public projection, current state/visitor-state error consumers, сторонние HTTPS-клиенты контроллера. Исключить влияние смены hostname на API/site IDs/редиректы.

### Изолированная лабораторная матрица

1. Valid pinned self-signed cert + `Omada` + правильная резолюция + тестовые token/GET API → PASS; никакие реальные guest/client mutation операции не производить.
2. Valid trusted cert + URL `192.168.0.222`, `localhost`, другое имя → strict REJECT.
3. Unknown CA/leaf, неверный SAN, expired/not-yet-valid, неправильная цепь/EKU, битый/недоступный bundle, неверные часы → strict REJECT, без HTTP/verify-false fallback.
4. Подмена DNS/host, proxy, cross-origin redirect, HTTP downgrade и неожиданные 30x на endpoints с токенами → reject; секреты никогда не выходят за утверждённый origin.
5. Planned rotation old/new anchors, retirement old, unexpected rotation, изменение ключа, SNI и HTTP Host → предсказуемое окно и fail closed вне утверждённого набора.
6. Token cache/refresh/concurrency, GET sites/clients, isolated hotspot authorization/unauthorization, read-back, retry/timeouts и обработка ответов Omada → корректно; TLS отказ не превращается в успешный ответ, нулевой клиентский список или потерю audit.
7. Startup/restart, новый TCP/TLS handshake после ротации, сломанный trust file, некорректное время, долгоживущие connection pools → корректные health/alert/stale-state, нет ложного `ready`.
8. Сравнение matched quiet + normal окон: TLS warnings действительно исчезают только после верификации; реальные TLS ошибки остаются видимы. Снимать producer records/s, guest journald cgroup `wios/wbytes`, Ubuntu QEMU cgroup host, `/dev/sda` physical IOPS/await/busy, auth latency, error rate. **Никакие проценты экономии HDD заранее не обещать.**

### Stage gates и роли

**Gate 1 — Security/Identity:** Owner/SysAdmin подтверждает подлинность текущего trust anchor и владелец имени/адреса, возможность безопасного обновления и отказа.  
**Gate 2 — Lab Correctness:** Tech Lead независимо проверяет перечисленные positive/negative TLS, Omada API, provenance/health tests.  
**Gate 3 — Production Change Admission:** отдельный Owner GO, конкретный runtime artifact/commit, controlled staging, backup/rollback, отсутствие влияния на старый production без допуска.  
**Gate 4 — Performance:** matched physical host/guest I/O, проверка security/audit и функциональности. Уменьшение строк предупреждений **само по себе не является физическим performance PASS**.

## 6. Указание техлидеру

**Выбор:** вести **Option B как основную** архитектуру QIO-01B; вариант A сохранить как альтернативное SysAdmin/Owner решение для будущего нормального PKI. До выполнения RV-1/2/3 и лабораторного плана **Coder HOLD**. Далее Tech Lead готовит узкий implementation contract **только по strict OmadaProvider transport/trust и безопасной настройке**, без подавления warning или переделки остальных модулей.

**Границы параллельных работ:** `QIO-01D` остаётся в исследовании повторного logging, `QIO-02` — независимое исследование физических SQLite writes. Ни один из этих этапов не блокируется этим контрактом. `PRODUCTION_CHANGES=NO`.

## 7. Источники

- Addendum `ARCHITECT — QIO-01B PRIORITY ADDENDUM` (Tech Lead read-only), ранее принятый QIO-01 Journaling Root Cause & Architecture Handoff.
- Дополнительная read-only TLS/x509 проверка Omada с Ubuntu 192.168.0.202 без секретов/мутаций.
- Исходники CaptivPortal `app/config.py`, `app/settings.py`, `app/controllers/omada_config.py`, `app/controllers/omada.py` (сверять production loaded SHA перед Coder TASK).
- RFC 9525: https://www.rfc-editor.org/rfc/rfc9525.html
- Requests SSL cert verification: https://requests.readthedocs.io/en/stable/user/advanced/#ssl-cert-verification
- TP-Link Omada SDN Controller Guide: https://www.tp-link.com/us/user-guides/omada-sdn-software-controller/chapter-5-configure-the-omada-sdn-controller.html

**Конец контракта QIO-01B v1.0.**
