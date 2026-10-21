# Captiv-Prod — Architecture Contract Amendment v3

**TASK:** `TASK-CAPTIVPROD-EDGE-NPM-01`  
**Основание:** Field Correction Request / Production Part A  
**Роль:** Captiv-Prod Architect  
**Тип решения:** Architecture Correction / No Implementation  
**Статус:** Architecture Amendment APPROVED; Part B HOLD

## 1. Архитектурный verdict

**Принимаю OPTION A — scheme-preserving upstream.**

Полевые результаты выявили два нарушения первоначального архитектурного контракта:

1. Принудительное направление всего трафика `NPM → Hestia:443` изменяет существующую HTTP-семантику Captive Portal.
2. Добавление NPM как промежуточного reverse proxy приводит к потере реального client IP на уровне CaptivePortal application.

Оба нарушения подтверждены полевыми проверками, а не являются гипотетическими рисками.

Поэтому прежний контракт с обязательным fixed HTTPS upstream **отменяется как универсальное правило для данного TASK**.

Новый целевой принцип:

> NPM принимает ownership публичного ingress и TLS, но не должен изменять наблюдаемую клиентом HTTP-семантику, client identity или существующее поведение backend-сервисов.

Принимается ограниченная коррекция Hestia proxy layer. Изменение CaptivePortal application code не разрешается.

## 2. AR-1 — NPM upstream scheme contract

**APPROVED TARGET TOPOLOGY:**

```text
                      Client
                        |
                        v
                   NPM / Edge
                    /       \
              HTTP /         \ HTTPS
                  v           v
            Hestia :80    Hestia :443
                  |           |
             Existing      Existing
           HTTP routing  HTTPS routing
```

| Frontend request | NPM upstream | Contract |
|---|---|---|
| HTTP :80 | HTTP → Hestia :80 | Required |
| HTTPS :443 | HTTPS → Hestia :443 | Required |

Общие инварианты:

- TCP destination — внутренний IP Hestia `192.168.0.202`.
- HTTP Host — исходный public FQDN.
- HTTPS upstream SNI — соответствующий public FQDN.
- URI/path/query — без изменения.
- Public FQDN запрещён как upstream destination.
- Дополнительные redirects, rewrites и authentication layers запрещены.

**Важная граница:** scheme-preserving определяется по исходному frontend request, а не по произвольному `X-Forwarded-Proto`, переданному клиентом.

Требуемая маршрутизация может потребовать корректировки NPM proxy-host configuration. Архитектурное разрешение не является утверждением, что стандартный интерфейс NPM уже поддерживает такое разделение без дополнительной настройки. Реализуемость и отсутствие побочных эффектов остаются обязательным preflight gate.

## 3. AR-2 — Captive Portal HTTP behavior

Устанавливается обязательная parity между direct Hestia и NPM path.

| Проверка | Baseline | Требование |
|---|---|---|
| HTTP `/` | 200 | 200 |
| HTTPS application routing | Flask :8088 | Сохранить |
| Host/path/query | Исходные значения | Без изменений |
| Redirect behavior | Production baseline | Без новых redirects |
| Client IP | Реальный клиент | Реальный клиент |
| HTTP frontend scheme | HTTP | HTTP |

Само по себе HTTP 200 не является достаточным доказательством parity: необходимо проверить destination/backend, redirect chain и forwarded headers.

Особенно важно: **Force SSL в NPM не должен навязываться для Captive Portal там, где он изменяет существующий HTTP baseline.**

Эта коррекция не изменяет требования к публичным TLS-сертификатам и полноценному HTTPS E2E.

## 4. AR-3 — Trusted proxy boundary

**APPROVED: Hestia real_ip canonicalization.**

```text
External client
    ↓
NPM 192.168.0.99
    ↓ trusted proxy boundary
Hestia real_ip module
    ↓ canonical client identity
Existing Hestia backend proxy
    ↓
CaptivePortal Flask / ProxyFix
```

| Параметр | Решение |
|---|---|
| Trusted proxy IP | `192.168.0.99` |
| `real_ip_header` | `X-Forwarded-For` |
| `real_ip_recursive` | `on` |
| Trust scope | Только три migrating vhosts |
| Arbitrary client-provided IP headers | Untrusted |
| Application identity source | Canonical client IP после trusted-proxy processing |

Использование nginx `http_realip_module` **разрешено**.

Однако доверие предоставляется только конкретному NPM hop, а не всей подсети `192.168.0.0/24`, всем Docker networks или любому отправителю `X-Forwarded-For`.

Дополнительный обязательный security invariant: NPM должен устанавливать достоверный IP непосредственно подключившегося клиента. Если клиент прислал произвольный `X-Forwarded-For`, эта информация не должна становиться доверенной client identity лишь потому, что запрос прошёл через NPM.

Нужно доказать, что выбор canonical IP не позволяет злоумышленнику подменить identity через forged header.

## 5. AR-4 — Canonical X-Forwarded-For

**APPROVED: сохранение proxy chain с однозначной trusted identity.**

1. NPM формирует forwarded chain, содержащую непосредственно наблюдаемый адрес клиента.
2. Hestia принимает identity только через явно доверенный NPM hop.
3. Hestia сохраняет traceable proxy chain при направлении запроса backend.
4. Application получает canonical client IP в позиции, соответствующей существующему `ProxyFix(x_for=1)`.

Пример обычного двухпрокси-маршрута:

```text
Client = 192.168.0.106
NPM    = 192.168.0.99

NPM → Hestia:
X-Forwarded-For: 192.168.0.106

Hestia canonical remote_addr:
192.168.0.106

Hestia → Flask:
X-Forwarded-For:
192.168.0.106, 192.168.0.106

ProxyFix(x_for=1):
request.remote_addr = 192.168.0.106
```

Повторное появление canonical IP в такой цепочке допустимо как результат текущего proxy forwarding. Это не требование специально дублировать IP.

**Acceptance определяется корректностью client identity, а не конкретным количеством одинаковых элементов в заголовке.**

Если frontend уже содержит цепочку доверенных прокси, она должна рассматриваться отдельно. В данном TASK никакие дополнительные trusted frontend proxies не утверждены.

## 6. AR-5 — Canonical X-Real-IP

**APPROVED.**

На выходе из Hestia к CaptivePortal:

```text
X-Real-IP = canonical client IP
```

Недопустимое значение в нормальном маршруте:

```text
X-Real-IP = 192.168.0.99
```

если `192.168.0.99` является лишь NPM intermediary.

После canonicalization Hestia должен передавать backend реальную identity клиента.

При этом `X-Real-IP` является единичным адресом, а не полной proxy chain.

## 7. AR-6 — X-Forwarded-Proto

**Authoritative value: original browser/client scheme.**

Необходимо различать два понятия:

- Frontend scheme — HTTP либо HTTPS между клиентом и NPM.
- Upstream transport scheme — HTTP либо HTTPS между NPM и Hestia.

В принятой topology значения должны совпадать, но архитектурно authoritative source остаётся frontend scheme.

| Запрос клиента | Canonical X-Forwarded-Proto |
|---|---|
| HTTP | `http` |
| HTTPS | `https` |

Hestia не должен принимать непроверенное клиентское значение этого заголовка в качестве authoritative.

Для CaptivePortal сохраняется:

```python
ProxyFix(
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1,
)
```

Дополнительный инвариант распространяется на `X-Forwarded-Host` и `X-Forwarded-Port`: поскольку приложение доверяет этим значениям через `ProxyFix`, итоговые host и port должны соответствовать публичному frontend request, а не произвольным клиентским forwarded headers.

## 8. AR-7 — Hestia real_ip scope

**APPROVED: per-domain, не global.**

Область применения ограничивается:

1. Captive Portal vhost.
2. Cloud vhost.
3. VPN Web vhost.

Распространять trust model глобально на все Hestia virtual hosts запрещается.

Доверие `192.168.0.99` вводится только в необходимых domain-level HTTP/HTTPS contexts.

Допускается использование существующих Hestia per-domain include hooks. Прямое редактирование autogenerated main vhost configuration не является утверждённым архитектурным способом.

Причина ограничения: другие Hestia-hosted ресурсы могут иметь собственные proxy/header assumptions, не проверенные в данном TASK.

Кроме того, для этих трёх vhosts нужно проверить оба пути:

```text
Path 1:
Client → NPM → Hestia

Path 2:
Client → Hestia directly
```

На протяжении Part A и rollback оба должны сохранять корректную client identity. Исправление NPM path не должно ломать существующий production path.

## 9. AR-8 — CaptivePortal application / ProxyFix

**FROZEN.**

В рамках текущего TASK запрещаются:

- изменение `ProxyFix(x_for=1, x_proto=1, x_host=1, x_port=1)`;
- изменение Flask request identity handling;
- изменение CAPPORT/auth/session logic;
- изменение Omada authorization flow;
- специальные application workarounds для нового NPM hop.

Любые необходимые корректировки должны оставаться на infrastructure reverse-proxy layer.

Если добиться корректной client identity без изменения приложения невозможно, SysAdmin обязан вернуть **Architecture HOLD**, а не самостоятельно изменять Flask или ProxyFix.

## 10. AR-9 — Required pre-Part-B acceptance tests

Все gates должны получить PASS до разрешения production cutover.

| Gate | Проверка | Требование |
|---|---|---|
| G01 | HTTP/HTTPS scheme routing | PASS |
| G02 | Captive Portal HTTP parity | PASS |
| G03 | Captive Portal HTTPS parity | PASS |
| G04 | Cloud HTTP/HTTPS parity | PASS |
| G05 | VPN Web HTTP/HTTPS parity | PASS / OUT |
| G06 | Upstream Host/SNI | PASS |
| G07 | URI/path/query preservation | PASS |
| G08 | Client IP through NPM | PASS |
| G09 | Client IP through direct Hestia | PASS |
| G10 | Spoofed X-Forwarded-For rejection | PASS |
| G11 | X-Real-IP canonicalization | PASS |
| G12 | X-Forwarded-Proto / Host / Port | PASS |
| G13 | Redirect parity / no loops | PASS |
| G14 | CaptivePortal sensitive logging boundary | PASS |
| G15 | NPM backup/restore + rollback readiness | PASS |
| G16 | No production mutation before Owner GO | PASS |

### Особые правила проверки

**G08–G10: Client identity.** Не ограничиваться сравнением HTTP-заголовков. Проверить фактическое значение `request.remote_addr` в CaptivePortal runtime. Обязательные сценарии: нормальный клиент через NPM, тот же клиент через прямой Hestia path и запрос с намеренно подставленным `X-Forwarded-For`. Для anti-spoofing нужен отрицательный тест: подставленный клиентом адрес не должен стать `request.remote_addr`.

**G02–G05: Behavior parity.** Для всех трёх hostname сравнивать результат с существующим production baseline, а не с ожидаемым поведением «типичного reverse proxy». Проверить HTTP по отношению к HTTPS.

**G14: Privacy.** Сохранить synthetic canary test и проверку persistent/container logs. Коррекция forwarded headers не разрешает дополнительное логирование MAC, session identifiers или token-like query values.

**G15: Rollback.** После per-domain Hestia real_ip correction исходный direct Hestia production path должен оставаться работоспособным. Возврат Cisco NAT на Hestia обязан оставаться достаточным для восстановления прежнего публичного маршрута без дополнительного исправления приложения.

## 11. AR-10 — TASK v2 amendment

**REQUIRED.**

Разделы A6/A7 первоначального TASK должны быть изменены. Необходимо также синхронизировать A8, A10 и Part A acceptance criteria.

| Раздел | Архитектурная коррекция |
|---|---|
| A6 | Fixed HTTPS для всего трафика заменить scheme-preserving upstream |
| A7 | Сохранить internal IP, Host/SNI и запрет public FQDN upstream |
| A8 | Добавить trusted-proxy boundary и canonical headers |
| A9 | Сохранить privacy и CAPPORT ограничения |
| A10 | Добавить HTTP/HTTPS parity, identity и spoofing gates |
| Part A PASS | Запрет PASS при fail любого нового обязательного gate |
| Part B | Сохранить Owner GO, порядок Portal → Cloud → VPN, 15-minute rollback guardrail |

Все остальные требования TASK v2 продолжают действовать, если они не противоречат настоящему amendment.

В частности, **не меняются** backup policy, image digest requirement, management port isolation, TLS issuance, Cisco NAT scope и запрет одновременной миграции прямых backend routes.

## 12. Уточнение архитектурных ограничений

**Первое — scheme-preserving не означает безусловное разрешение динамического proxy_pass.** Требуется корректная маршрутизация с сохранением NPM host configuration и TLS ownership. Способ реализации выбирает SysAdmin, но только в рамках принятого контракта, с воспроизводимым тестом и без небезопасного использования клиентских forwarded headers.

**Второе — real_ip не гарантирует anti-spoofing само по себе.** Достоверность адреса зависит от всей последовательности NPM → Hestia → backend. Поэтому тесты должны подтверждать фактическую identity, включая сценарии подмены заголовков. Наличие `set_real_ip_from` само по себе не считается достаточным PASS.

## 13. Финальный архитектурный статус

| Decision / Gate | Status |
|---|---|
| Architecture Amendment v3 | APPROVED |
| OPTION A / Scheme-preserving | APPROVED |
| Hestia per-domain real_ip | APPROVED |
| Application / ProxyFix changes | FORBIDDEN |
| Existing Part A evidence | RETAINED |
| A8 acceptance | HOLD |
| Part B / Cisco cutover | HOLD |

**Architect decision:** SysAdmin получает разрешение продолжить Part A по скорректированному архитектурному контракту и повторно проверить затронутые gates.

Это не отменяет ранее пройденные независимые проверки A1–A7, но требует повторной валидации изменённого upstream path, headers и Hestia routing.

**Owner GO на Part B не выдан.** Cisco NAT, DNS, Hestia certificates и CaptivePortal application остаются без изменений до полного Part A PASS и отдельного production cutover authorization.

Настоящий amendment является архитектурным решением, а не инструкцией на выполнение команд в production.
