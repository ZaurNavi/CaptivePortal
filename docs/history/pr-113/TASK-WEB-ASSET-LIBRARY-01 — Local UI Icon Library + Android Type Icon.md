# TASK-WEB-ASSET-LIBRARY-01  
## Local UI Icon Library + Android Type Icon

### Status

`PROPOSED / TECH LEAD REVIEW REQUIRED`

### Purpose

Создать в Admin Web CaptivPortal централизованную локальную библиотеку небольших UI assets / icons и выполнить первое ограниченное внедрение этой схемы на примере Android icon в списке Devices.

Задача является исключительно presentation-layer изменением.

Не изменять:

- backend;
- API;
- database/schema;
- Device List semantics;
- Current State semantics;
- device classification;
- `device_type`;
- hostname;
- current presence;
- pagination;
- sorting;
- security/capability model;
- routes;
- feature-flag semantics;
- Omada/Analytics/read-source logic.

---

## 1. Motivation

Admin Console постепенно развивается от преимущественно текстового интерфейса к более читаемому визуальному представлению.

В дальнейшем могут понадобиться небольшие локальные иконки для:

- operating platforms;
- device classes;
- status presentation;
- Wi-Fi / traffic / network presentation;
- других элементов Admin Web.

Чтобы не добавлять assets хаотично в разные директории и не использовать внешние CDN, предлагается создать одну централизованную локальную структуру.

---

## 2. Proposed asset structure

Создать внутри существующего Admin Web static tree:

```text
app/admin_web/static/icons/
├── README.md
├── platforms/
│   └── android.svg
├── devices/
│   └── .gitkeep
└── ui/
    └── .gitkeep
```

Назначение:

```text
platforms/
```

Иконки ОС / платформ:

- Android;
- Windows;
- iOS;
- Linux;
- будущие платформы.

```text
devices/
```

Иконки классов устройств:

- smartphone;
- tablet;
- laptop;
- desktop;
- IoT;
- unknown;
- будущие device-class assets.

```text
ui/
```

Общие UI symbols:

- status;
- traffic;
- Wi-Fi;
- warning;
- health;
- другие presentation-only assets.

`.gitkeep` используется только для сохранения пока пустых каталогов в Git.

---

## 3. Asset policy

Все production UI icons должны храниться локально внутри repository.

Запрещается для этой задачи:

- CDN;
- external runtime image URLs;
- external icon frameworks;
- Font Awesome / Bootstrap Icons dependencies;
- runtime загрузка assets с third-party resources.

Предпочтительный формат небольших UI icons:

```text
SVG
```

Причины:

- масштабирование без потери качества;
- небольшой размер;
- хорошая работа на HiDPI displays;
- удобство дальнейшей CSS-композиции.

---

## 4. First implementation example — Android

Первым asset будет Android platform icon.

Исходное backend значение остаётся без изменений:

```text
device_type = "Android"
```

Frontend не должен менять или переопределять это значение.

Предлагаемое представление поля Type:

```text
Type
[Android icon] Android
```

Текст `Android` на первом этапе сохраняется.

Иконка отображается непосредственно перед текстом.

---

## 5. Mapping rule

Frontend presentation layer может иметь ограниченное отображение:

```text
Android
→
/admin/static/icons/platforms/android.svg
```

Mapping должен влиять только на presentation.

Он не должен:

- определять устройство;
- изменять `device_type`;
- создавать новый semantic device type;
- выполнять дополнительные API requests;
- делать fallback classification.

Если `device_type` не соответствует известному asset mapping, UI просто показывает исходное значение текстом.

Например:

```text
device_type = "boot"
→
boot
```

Без иконки.

```text
device_type = "Unknown"
→
Unknown
```

Без иконки.

---

## 6. No semantic inference

Критически важно:

Icon mapping не является механизмом классификации.

Frontend использует только уже полученное backend значение.

Запрещено выводить Android icon на основании:

- hostname;
- MAC;
- vendor;
- browser/user-agent;
- SSID;
- AP;
- device activity;
- IP;
- исторических наблюдений;
- любых косвенных признаков.

Условие отображения первой иконки:

```text
device_type == "Android"
```

---

## 7. Accessibility

Иконка в данном случае является дополнительным visual cue.

Так как рядом сохраняется текст:

```text
Android
```

иконка не должна дублировать информацию для screen reader.

Предпочтительно использовать её как decorative asset с соответствующим accessibility поведением.

---

## 8. Styling

Размер и положение Android icon относятся только к CSS/presentation layer.

Ожидаемое поведение:

- маленький размер;
- вертикальное выравнивание по тексту;
- небольшой стабильный gap между icon и `Android`;
- отсутствие влияния на высоту строки Device row;
- отсутствие layout shift;
- корректная работа desktop/mobile responsive layout.

Точный размер определяется Web Designer во время Lab visual review.

---

## 9. Asset source / attribution

Для первого Android asset предполагается использовать официальный Android robot/head artwork либо каноническую локальную копию такого asset.

В:

```text
app/admin_web/static/icons/README.md
```

должны быть зафиксированы:

- имя asset;
- назначение;
- источник;
- license / attribution requirements, если применимо.

Это вводится как постоянное правило для будущих third-party/branded assets.

---

## 10. Future extension model

После создания библиотеки новые иконки добавляются без изменения архитектуры.

Пример:

```text
platforms/
├── android.svg
├── windows.svg
├── ios.svg
└── linux.svg
```

или:

```text
devices/
├── smartphone.svg
├── tablet.svg
├── laptop.svg
└── desktop.svg
```

Добавление нового asset должно состоять из:

1. локального SVG;
2. записи source/license при необходимости;
3. presentation mapping;
4. CSS only if требуется новый visual treatment.

Backend при этом не должен знать расположение или существование icon assets.

---

## 11. Initial implementation scope

Предпочтительный scope:

```text
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/static/icons/**
```

Templates изменяются только если текущая структура действительно не позволяет корректное presentation-only внедрение.

Backend Python не изменять.

---

## 12. Existing Devices UI requirements remain frozen

Новая задача не должна ломать ранее принятые свойства Devices list:

- MAC остаётся primary identity;
- hostname остаётся рядом/под MAC;
- Type остаётся отдельным field;
- Current Presence использует только accepted backend semantics;
- backend Global Online-first order сохраняется;
- frontend не выполняет sorting;
- server pagination / Load More сохраняется;
- Search / Clear / Refresh сохраняются;
- whole-row Device Detail navigation сохраняется.

---

## 13. Implementation workflow

Работа должна начаться только после завершения текущих recovery/database/indexing работ и фиксации нового clean production/repository baseline.

После этого Owner передаёт Web Designer:

```text
current main SHA
current tree SHA
production/deployment status
relevant merged work status
```

Web Designer обязан:

1. проверить фактический repository state;
2. не использовать старый patch blindly;
3. определить, какие предыдущие UI изменения уже присутствуют;
4. построить новый cumulative patch против актуального baseline;
5. добавить icon library;
6. добавить Android asset;
7. выполнить presentation mapping;
8. проверить patch applicability и formatting;
9. передать patch Owner / Tech Lead для Lab visual acceptance.

---

## 14. Validation

Минимальные проверки:

```text
git apply --check
git diff --check
```

Дополнительно проверить:

- Android icon появляется только при `device_type == "Android"`;
- текст `Android` остаётся;
- неизвестные Type отображаются без icon;
- нет нового fetch/API request;
- нет client-side sorting;
- pagination не изменена;
- Device Detail navigation не изменена;
- responsive layout не сломан;
- asset загружается локально из `/admin/static/icons/...`.

---

## 15. Deliverable

Web Designer возвращает новый cumulative patch против актуального baseline.

Handoff должен содержать:

```text
TASK
BASELINE_SHA
BASELINE_TREE
CHANGED_FILES
PATCH_FILE
PATCH_SHA256
DIFF_STAT
GIT_APPLY_CHECK
GIT_DIFF_CHECK
ASSET_FILES
GITHUB_WRITE=NONE
PRODUCTION=UNTOUCHED
OWNER_VISUAL_ACCEPTANCE=PENDING
```

Не выполнять:

```text
commit
push
PR creation
merge
deploy
```

---

## 16. Requested Tech Lead review

Tech Lead требуется подтвердить:

1. что proposed `static/icons/` structure допустима для Admin Web;
2. что локальный presentation mapping `device_type → icon asset` не нарушает backend/UI boundary;
3. что `admin.js + admin.css + static/icons/**` допустимы как presentation-layer scope;
4. что отдельный backend task для первого Android icon не требуется;
5. что после фиксации нового clean baseline Web Designer может подготовить cumulative patch на описанных условиях.

### Requested decision

```text
TASK-WEB-ASSET-LIBRARY-01
TECH_LEAD_REVIEW = PENDING

Requested:
APPROVE
or
RETURN WITH REQUIRED CHANGES
```