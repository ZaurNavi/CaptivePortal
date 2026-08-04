# Omada Open API: уровни подтверждения

Status: current
Updated: 2026-08-04
Sources: runtime baseline `227ebe9…`, local Swagger research и переданные live-test reports для Omada Controller 5.14.31

Этот документ разделяет доказательства, а не объединяет их словом «confirmed». Один endpoint может одновременно находиться в разделе live-tested, быть описан Swagger и использоваться текущим кодом. Наличие endpoint в Swagger без live-выполнения не подтверждает его runtime behavior и не разрешает новую mutation.

## OAuth и общая проверка ответа

    POST /openapi/authorize/token?grant_type=client_credentials

Body содержит `omadacId`, `client_id` и `client_secret`. Последующие запросы используют:

    Authorization: AccessToken=<token>

Значение header и credentials не логируются.

Ответ проверяется по отдельным уровням:

1. network/timeout;
2. HTTP status;
3. наличие JSON object;
4. Omada `errorCode`;
5. endpoint-specific result shape.

HTTP 200 не означает успех при `errorCode != 0`.

## 1. Live-tested endpoints

Live-tested означает, что запрос был выполнен против реального проверенного контроллера и результат зафиксирован в research report. Ошибка 404 тоже является live-tested результатом, но не доказательством поддержки операции.

### Общие и клиентские операции

| Endpoint | Наблюдавшийся результат |
|---|---|
| `POST /openapi/authorize/token?grant_type=client_credentials` | token получен и использован в последующих live-запросах |
| `GET /openapi/v1/{omadacId}/sites` | успешный ответ |
| `GET /openapi/v1/{omadacId}/sites/{siteId}/devices` | успешный ответ |
| `GET /openapi/v1/{omadacId}/sites/{siteId}/clients` | успешный paginated client inventory |
| `GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}` | карточка клиента получена до и после операции |
| `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect` | успешное завершение pending session; после операции `active=false`, клиент исчез из active list |
| `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/disconnect` | live-tested как HTTP 404 на Omada 5.14.31; операция не поддержана |
| `GET /openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceMac}` | live-tested как HTTP 404; для общей карточки используется `/devices` с выбором по MAC |

### AP read-only operations

Следующие endpoints выполнены live на реальном EAP613/Omada 5.14.31:

    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/available-channel
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/general-config
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/ip-setting
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/lan-traffic-info
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/ofdma
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/override
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/power-saving
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/radio-config
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/radios
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/rf-scan-result
    GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/wired-uplink
    GET /openapi/v2/{omadacId}/sites/{siteId}/aps/{apMac}/override
    GET /openapi/v2/{omadacId}/sites/{siteId}/aps/{apMac}/rf-scan-result

`power-saving` был обработан endpoint router, но для проверенной модели/конфигурации не вернул объект настроек. Override response может содержать пароль SSID и не должен сохраняться целиком.

## 2. Schema-confirmed endpoints

Присутствие следующих endpoints подтверждено локальным Swagger. Для `reconnect` дополнительно существует live-tested доказательство. Для остальных перечисленных mutations рассмотренные отчёты не содержат отдельного подтверждения успешного live-выполнения:

    POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/block
    POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
    POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/unblock
    POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth
    POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth
    POST /openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceMac}/forget

Для `unauth`, `block` и `unblock` schema presence не следует называть live confirmation без отдельного отчёта выполнения.

## 3. Endpoints used by current code

Runtime baseline `227ebe9…` использует `app/controllers/omada.py` и pending-session adapter `app/controllers/omada_pending_sessions.py`. Один `OmadaProvider` вызывает:

    POST /openapi/authorize/token?grant_type=client_credentials
    GET  /openapi/v1/{omadacId}/sites
    GET  /openapi/v1/{omadacId}/sites/{siteId}/clients
    GET  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}
    POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth
    POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth
    POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect

Использование endpoint кодом не доказывает live success само по себе. В частности, рассмотренные research reports подтверждают `unauth` по Swagger, но не содержат отдельного live execution proof.

`list_active_clients()` использует query `page`/`pageSize`; `get_pending_client_state()` и `reconnect_client()` форматируют MAC через общую utility и возвращают defensive/safe contracts без token, Authorization header или raw response. Pending-session methods подключаются к существующему provider class, а не создают отдельный client.

Current code не вызывает `block`, `unblock`, `forget` или AP read-only endpoints из application provider. `disconnect` и client `DELETE` отсутствуют в action path. Текущий shared token-cache lifecycle фиксируется в `docs/project-inventory.md` и module contract Cleaner.

## 4. Unsupported or rejected operations

| Операция | Статус | Причина |
|---|---|---|
| `POST /clients/{clientMac}/disconnect` | unsupported on tested controller | live HTTP 404; отсутствует в локальном Swagger |
| `DELETE /clients/{clientMac}` | unsupported/unverified | отсутствует в локальном Swagger; не использовать |
| `GET /devices/{deviceMac}` | unsupported on tested controller | live HTTP 404; использовать list `/devices` и exact MAC match |
| `POST /hotspot/clients/{clientMac}/unauth` | rejected for Cleaner v1 | schema-confirmed и используется другим current-code contract, но не подтверждён как безопасная замена reconnect для pending session |
| `POST /clients/{clientMac}/block` и `/unblock` | rejected for Cleaner v1 | schema-confirmed, но block запрещает повторное подключение и не соответствует action policy Cleaner |
| `POST /devices/{deviceMac}/forget` | rejected for Cleaner v1 | относится к device removal, а не к guarded завершению pending session |

Rejected for Cleaner не означает глобально unsupported: это ограничение конкретного change intent.

## Pagination, identity и MAC

Client list пагинируется. Неполный inventory запрещает batch mutation. Fresh exact client card обязателен перед `reconnect`.

MAC normalization находится в `app/common/mac.py`. Формат URL выбирается по endpoint contract; client snapshot использует hyphen format. Не реализовывать ad-hoc `replace` в новом модуле.

## Mutation safety

Любой новый mutation endpoint требует отдельного TASK, audit-before-action, bounded retry, protection against stale identity/session и verification. Успешный POST без последующей проверки не объявляется подтверждённым результатом.
