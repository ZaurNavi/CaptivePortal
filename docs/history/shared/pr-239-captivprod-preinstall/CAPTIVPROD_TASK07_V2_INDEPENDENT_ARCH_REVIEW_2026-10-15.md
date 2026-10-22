# Captiv-Prod — Independent Architect Review: TASK-07 v2

**Дата:** 2026-10-15 (Asia/Baku)  
**Объект:** `TASK-CAPTIVPROD-ARCH06-TARGETED-CLOSURE-07_v2`  
**Режим проверки:** офлайн-документы, целостность ZIP, локальный независимый запуск тестов; **без доступа к live production и без изменений**.

## Решение

- `TASK07_V2_REPORT=ACCEPTED_AS_HONEST_READONLY_HANDOFF`
- `NET01_REV4_1_PREVIOUS_CLI_P1=FIXED_OFFLINE`
- `NET01_REV4_1_OFFLINE_PACKAGE=REVIEWED_WITH_SCOPE_LIMITATION`
- `NET01_SENSOR_LOCAL_POLICY=NOT_IMPLEMENTED_IN_REV4_1`
- `NET01_FINAL_DEPLOYMENT_ACCEPTANCE=HOLD`
- `NEW_OMADA_SITE_ID=UNKNOWN_TLS_GATE`
- `PREINSTALL_READY=HOLD`
- `CAPTIVEPORTAL_INSTALL=NOT_AUTHORIZED`
- `OLD_PRODUCTION_AND_LEGACY_CISCO=OUT_OF_SCOPE_UNTOUCHED`

## Проверенные файлы и целостность

Получено `NET01_REV4_1_FULL(1).zip` и `TASK07_V2_SYSADMIN_HANDOFF(1).zip`. Распакованы в отдельную рабочую директорию. `sha256sum -c MANIFEST.sha256` — успешно для обоих пакетов. Вложенный `NET01_REV4_1_FULL.zip` имеет тот же SHA256, что отдельно переданный архив: `0bb12d269f8ae0826786c71c3ba2bb3f43ac54dc4c3c1a26500bf2d67a155687`. Это **реконструированный** ZIP, не бинарно идентичный Windows candidate SHA256 `422f2cbc1a37535c26c934ddcd244740d6c2408940a57269350c075e4ae68ee7`; их нельзя подменять в evidence.

Независимый тест: `python3 -m pytest -q tests --disable-warnings --maxfail=1` → **105 passed in 7.63s**. `bash -n firewall/*.sh` — OK. Эти тесты синтетические/офлайн; реальный systemd PID1 и iptables на целевом хосте **не проверялись**.

## Подробности NET01 REV4.1

**Закрытая старая P1:** в REV4 команда `net01-fw-install.sh --maintenance-reinstall` вызывала `net01-verify.py --identity --ignore-maintenance --ignore-hold`, но verifier запрещал комбинацию. В REV4.1 `main()` принимает эту комбинацию только при root EUID, корневой директории с владельцем root/mode `0700` и файле MAINTENANCE root/mode `0600`; обычный запуск без bypass по-прежнему блокируется marker. Новый `tests/test_rev4_1_real_verifier_cli.py` вызывает настоящую функцию verifier `main()` и проверяет положительные и отрицательные комбинации. **ПРЕДЫДУЩИЙ конкретный дефект исправлен.** Однако часть identity/firewall функций в тесте подменена, так что end-to-end shell + живой Docker/firewall не доказаны.

**Незакрытый gate:** `net01-verify.py:check_firewall()` и `net01-fw-install.sh` по-прежнему имеют ровно один IPv4 allow к `172.18.0.1:18089` — NPM `172.18.0.2` с точным MAC/bridge. Локальный Sensor на хосте через `lo` попадёт под REJECT. Нельзя отдельно руками добавить правило и назвать пакет принятым: нарушится exact-match verifier/watchdog/rollback. Нужна **единая следующая ревизия** всех компонентов (`INPUT` + при необходимости `OUTPUT` с UID для host-local initiator, installer, verifier, watchdog, rollback, maintenance, tests). Положительные/отрицательные сценарии локальных процессов, NPM, чужих контейнеров, LAN/Guest/WAN и IPv6 обязательны. Правило без scope (`lo ACCEPT` или `172.18.0.0/16 ACCEPT`) запрещено.

Сетевой маршрут `ip -4 route get 172.18.0.1` зафиксирован SysAdmin как `local ... dev lo src 172.18.0.1`; это **read-only наблюдение**, а не подтверждение реального UID-контроля в firewall.

## Новая Omada

`https://192.168.0.99:8043` предлагает self-signed сертификат с `SAN=DNS:Omada`, но **без** `IP:192.168.0.99`: для строгого IP-URL доверенная TLS identity сейчас не установлена. Anonymous `/api/info` подтверждает Omada v5.14.32.3 и `omadacId` длиной 32 hex; это **не** Site ID. Token exchange и Site/AP/WLAN GET не были выполнены. Следующий безопасный шаг — выполнить проверку доверенного имени и сертификата (`Omada` + контролируемое локальное разрешение имени и отдельный CA/cert trust file) **без отключения TLS verification для credentialed requests**, если это реально даёт корректную проверку chain/SAN; при невозможности — отдельная согласованная замена контроллерного сертификата. Только после TLS PASS выполнять OpenAPI client_credentials и read-only inventory. Секреты в файлы отчёта/командную строку не помещать; перед go-live ротировать раскрытый client secret.

## Suricata / Evidence / другие зависимости

- Подтверждённый порядок: Core TCP readiness → Sensor runtime создаёт EVE UNIX_DGRAM socket → Suricata использует socket и запускает AF_PACKET на **новом** `enp3s0`; Unit `Type=simple` у Sensor не доказывает готовность socket самим `After=`. Старый `ExecStartPre timeout 1830` при effective `TimeoutStartSec 90` нельзя без проверки переносить.
- Новый Evidence `127.0.0.1:9443`, CA с `IP SAN 127.0.0.1`, отдельные bearer IDs, registration и F-B1 admission — **план**, а не установленный и доказанный listener.
- Отдельный NPM Proxy Host нового домена пока **не создан**; DNS/само наличие сертификата не означает HTTPS PASS.
- На новом `enp3s0` forwarding=1: решение только по **новому** Linux интерфейсу после scoped GO, не менять global forwarding. Cisco исключительно **порт Gi1/0/45** в ранее разрешённом режиме; legacy Cisco/порты/VLAN полностью исключены из работ.
- Согласно SysAdmin `lsblk ROTA`, `/` на SSD-подобном устройстве (`ROTA=0`), `/srv/backups` на HDD (`ROTA=1`). Уточнить при storage manifest; не предполагать HDD для root.

## Узкий следующий directive SysAdmin в рамках TASK-07 v2

1. **NET-01:** использовать именно этот сохранённый и захешированный REV4.1 как исходную review-базу, подготовить одну **интегрированную следующую ревизию** firewall policy под NPM + локальный Sensor. Подготовить точный diff, real-verifier tests, полный ZIP+MANIFEST и negative/rollback matrix; затем независимый Architect review. Без живой активации. Обязательно этап реального **изолированного** systemd PID1 staging.
2. **Omada:** до token exchange сформировать работоспособный строгий TLS trust/name маршрут. Если можно без изменений Omada — представить результат и доказательства; иначе сформировать единственный узкий change plan для Owner GO. После PASS — только credentialed read-only GET, получить настоящий Site ID, AP/WLAN/hotspot/webhook inventory/permissions, без секретов в отчёте.
3. **Suricata/Evidence:** довести deployment-specific артефакты до точных готовых к staged test конфигураций (NIC `enp3s0`, EVE socket permissions, bounded unit waits; TLS receiver CA/SAN, IDs/credential references, F-B1 admission prerequisites); не выдавать планы за live PASS.
4. **Не делать:** Portal install, изменения старой `.202`/`.222`, Cisco legacy, NPM recreate, firewall apply, выпуск/смену сертификата/ключей и запуск постоянных услуг без отдельного scoped Owner GO.

## Допуск

`OFFLINE_REVIEW=PASS_FOR_REV4_CLI_FIX_ONLY`  
`FULL_PREINSTALL_ACCEPTANCE=HOLD`  
`NEXT_EXPECTED=NET01_INTEGRATED_REVISION_AND_OMADA_STRICT_TLS_SITE_ID_EVIDENCE`.
