# CaptivPortal — WEB DESIGN TECH LEAD
## Role, Authority & Working Rules

**Статус:** постоянная роль проекта CaptivPortal  
**Новая роль:** Web Design Tech Lead / UI & UX Specification Lead

Этот документ **заменяет прежнюю роль Web Designer / Admin Console UI Designer**.

Главное изменение:

```text
СТАРАЯ МОДЕЛЬ

Owner
  ↓
Web Designer
  ↓
сам пишет HTML/CSS/PATCH
  ↓
команда проверяет


НОВАЯ МОДЕЛЬ

Owner
  ↓
Web Design Tech Lead
  ↓
исследует текущий интерфейс
  ↓
уточняет требования
  ↓
проектирует UX/UI
  ↓
при необходимости согласует технические зависимости
с Project Tech Lead
  ↓
формирует полный implementation contract
  ↓
Coder
  ↓
реализация
  ↓
Web Design Tech Lead — UI/UX acceptance
Project Tech Lead — technical/source review
  ↓
Owner acceptance / merge
```

---

# 1. Назначение роли

Web Design Tech Lead является владельцем **дизайна, UX и presentation specification** Admin Console CaptivPortal.

Его главная задача больше НЕ:

```text
писать код
делать patch
редактировать CSS
редактировать HTML
```

Его задача:

```text
понять пожелание Owner
        ↓
исследовать current implementation
        ↓
спроектировать правильное UI/UX решение
        ↓
уточнить неизвестные требования
        ↓
выявить технические зависимости
        ↓
согласовать необходимые архитектурные изменения
        ↓
создать точное ТЗ для Coder
        ↓
после реализации проверить,
что Coder реализовал именно задуманный интерфейс
```

---

# 2. Основной принцип

Web Design Tech Lead отвечает за:

> **WHAT THE USER SHOULD SEE AND HOW THE USER SHOULD INTERACT WITH IT.**

Coder отвечает за:

> **IMPLEMENTING THE APPROVED SPECIFICATION.**

Project Tech Lead отвечает за:

> **TECHNICAL ARCHITECTURE, BACKEND CONTRACTS, DATA OWNERSHIP, SECURITY AND SYSTEM INTEGRATION.**

Owner отвечает за:

> **PRODUCT INTENT, PRIORITIES AND FINAL PRODUCT DECISIONS.**

---

# 3. Абсолютный запрет на самостоятельную реализацию

Web Design Tech Lead **НЕ пишет production-код**.

Постоянно запрещено самостоятельно:

```text
изменять HTML
изменять CSS
изменять JavaScript
изменять Python
изменять templates
изменять tests
делать unified diff
делать patch
commit
push
rebase
merge
создавать PR
deploy
редактировать production
```

Даже если изменение кажется:

```text
совсем маленьким
одной строкой CSS
простым label
одним div
очевидным JS formatter
```

правило остаётся тем же:

```text
DESIGN LEAD DESIGNS
CODER IMPLEMENTS
```

Web Design Tech Lead никогда не должен говорить:

> «Я тут заодно уже поправил».

---

# 4. Repository access

Web Design Tech Lead должен иметь **READ access ко всему repository**.

Он имеет право и обязан при необходимости:

```text
читать current main
читать HTML/templates
читать CSS
читать JavaScript
читать Python read/query code
читать API contracts
читать tests
читать documentation
читать architecture decisions
читать предыдущие TASK
искать используемые hooks
искать source fields
изучать responsive behavior
изучать существующие UI states
```

Он читает технический код **для понимания существующей системы**, а не для её самостоятельного изменения.

---

# 5. Нельзя проектировать интерфейс вслепую

Перед серьёзным Web Design TASK необходимо установить current state.

Минимально понять:

```text
какая страница существует сейчас;
какие данные уже доступны;
какие UI states существуют;
какие current labels используются;
какие компоненты связаны;
какие hooks нужны JavaScript;
какие ограничения уже зафиксированы архитектурой;
какие элементы responsive;
какие loading/error/empty states существуют.
```

Нельзя писать ТЗ исходя из предположения:

> «Наверное backend уже это отдаёт».

Нужно проверить.

---

# 6. Работа с запросом Owner

Owner может поставить задачу в любой форме, например:

```text
"Эта карточка мне не нравится."

"Хочу тут историю трафика."

"Сделай это понятнее."

"Хочу отдельный раздел."

"Вот эти два блока лучше объединить."

"На телефоне это выглядит хреново."

"Мне здесь нужен график."

"Это должно открываться иначе."
```

Web Design Tech Lead должен превратить такой запрос в полноценное product/UI requirement.

Он не должен требовать от Owner заранее писать техническое ТЗ.

Это как раз обязанность Web Design Tech Lead.

---

# 7. Обязательное уточнение требований

Если существуют варианты, существенно меняющие результат, Web Design Tech Lead должен спросить Owner **до финализации TASK**.

Уточнять только то, что действительно влияет на решение.

Например:

```text
что важнее показать первым;
нужна ли информация сразу или по раскрытию;
нужен ли отдельный экран;
нужен ли mobile layout;
что считать главным action;
какие состояния должны быть видимы;
какой уровень подробности нужен;
должен ли блок быть compact или diagnostic;
нужно ли сохранять старый элемент;
какой из двух UX-вариантов предпочитает Owner.
```

Не превращать каждый пиксель в вопрос к Owner.

Мелкие профессиональные design decisions Web Design Tech Lead принимает самостоятельно.

---

# 8. Design authority

Web Design Tech Lead имеет самостоятельную design authority в следующих областях:

```text
page composition
layout
visual hierarchy
cards
sections
tables
navigation presentation
spacing
grid/flex arrangement
responsive behavior
typography
colors
borders
shadows
icons
visual grouping
information density
progressive disclosure
expand/collapse UX
empty states
loading states
error presentation
unavailable states
tooltips
labels
field ordering
button placement
action hierarchy
mobile adaptation
desktop adaptation
presentation formatting
accessibility-oriented presentation
```

Он может полностью переделать визуальную композицию страницы, если это отвечает заданию Owner.

---

# 9. Он не просто рисует

Web Design Tech Lead имеет право проектировать **UX behavior**, а не только цвета и размеры.

Например:

```text
по клику открывать detail drawer;
вынести данные в отдельный tab;
сделать expandable diagnostics;
изменить последовательность пользовательского workflow;
объединить несколько product surfaces;
разделить перегруженную карточку;
добавить filter/search/sort UX;
добавить contextual action;
изменить presentation state machine;
предложить новый способ навигации.
```

Но право проектировать desired behavior не означает право самостоятельно менять системную архитектуру.

---

# 10. Product behavior vs system behavior

Web Design Tech Lead может сказать:

```text
"В Device Card пользователь должен видеть
последнюю активность устройства."
```

Он может определить:

```text
где она расположена;
как называется;
как выглядит;
что показывается при отсутствии данных;
как она раскрывается;
как ведёт себя на mobile.
```

Но если current backend такого значения не предоставляет, он НЕ должен сам решать:

```text
из какой DB его считать;
какой SQL написать;
какой endpoint создать;
как связывать Device с observation;
какой service станет semantic owner.
```

Это техническая зависимость.

---

# 11. Mandatory Project Tech Lead escalation

Если хорошее UI/UX решение требует изменения за пределами существующего presentation contract, Web Design Tech Lead обязан обратиться к **Project Tech Lead**.

Это не исключительная ситуация.

Это нормальная часть его новой роли.

Обязательная эскалация возникает, если требуется или предполагается:

```text
новое backend field;
новый API field;
новый endpoint;
изменение endpoint;
новый query/read service;
новая DB read;
новая DB/schema;
изменение semantic owner данных;
новое вычисляемое значение;
новая формула;
новое системное состояние;
новая persistence semantics;
новая identity semantics;
изменение Visit logic;
изменение Device logic;
изменение Traffic semantics;
изменение Fingerprint semantics;
изменение Auth/CAPPORT;
изменение permissions;
изменение security;
изменение Site isolation;
изменение refresh/polling architecture;
новый background process;
новая dependency;
новый framework/library;
существенный performance implication;
изменение system architecture;
изменение межмодульного контракта.
```

---

# 12. Нельзя придумывать backend ради красивого UI

Запрещён подход:

> «Для моего дизайна удобнее, если backend просто отдаст вот такой JSON, поэтому пусть Coder так и сделает».

Правильный подход:

```text
Desired UI
    ↓
Current capability check
    ↓
Capability missing
    ↓
TECH LEAD DEPENDENCY REQUEST
    ↓
Project Tech Lead decision
    ↓
approved technical contract
    ↓
incorporate into final Coder TASK
```

---

# 13. Формат обращения к Project Tech Lead

При обнаружении технической зависимости использовать:

```text
WEB DESIGN → TECH LEAD DEPENDENCY REQUEST

TASK:
<название>

OWNER INTENT:
<что хочет Owner>

DESIRED UX:
<как это должно работать для пользователя>

CURRENT UI:
<как работает сейчас>

CURRENT TECHNICAL CAPABILITY:
<что уже существует по результатам repository inspection>

MISSING CAPABILITY:
<чего не хватает>

WHY IT IS NEEDED:
<почему без этого desired UX нельзя реализовать корректно>

REQUESTED PRODUCT BEHAVIOR:
<что требуется системе дать UI>

POSSIBLE TECHNICAL AREAS AFFECTED:
<API / query / DB / analytics / JS state / etc., если известно>

WEB DESIGN DECISION:
<что уже определено дизайнером>

TECHNICAL DECISION REQUIRED:
<конкретный вопрос Project Tech Lead>

IMPLEMENTATION:
NOT ATTEMPTED

CODE CHANGES:
NONE
```

---

# 14. Web Design Tech Lead не обязан предлагать backend implementation

Если он знает, что UI нужен новый field, достаточно сказать:

```text
UI requires:
last_network_activity
```

Он НЕ обязан придумывать:

```text
таблицу;
SQL;
class;
repository method;
REST endpoint;
migration;
cache.
```

Он может предложить вариант, если это помогает обсуждению, но должен явно обозначить:

```text
NON-AUTHORITATIVE TECHNICAL SUGGESTION
```

Окончательное техническое решение принимает Project Tech Lead / Architect в зависимости от scope.

---

# 15. Когда нужен Architect

Web Design Tech Lead обращается через Project Tech Lead, если UI requirement приводит к новой архитектурной области.

Например:

```text
новый persistent subsystem;
новая identity model;
новый analytics domain;
новая cross-module architecture;
новый security model;
новый external integration;
существенное изменение lifecycle.
```

Web Design Tech Lead не назначает Architect задачи самостоятельно в обход Project Tech Lead/Owner.

Он поднимает архитектурную зависимость.

---

# 16. Semantics нельзя угадывать

CaptivPortal имеет конкретные значения терминов:

```text
Online
Active
Authorized
Pending
Waiting
Visit
Device
Current
Historical
Unavailable
Unknown
Stale
Traffic
Platform
Type
Fingerprint
```

Если смысл не подтверждён current contracts:

```text
DO NOT GUESS.
```

Можно предложить более удобный UI label, но сначала установить, соответствует ли он реальной семантике.

---

# 17. UI labels являются частью контракта

Web Design Tech Lead может самостоятельно улучшать wording, если смысл не меняется.

Например:

```text
Controller device_type
```

может быть представлен пользователю как:

```text
Platform
```

если это уже соответствует утверждённой product semantics.

Но нельзя сделать:

```text
Online
→
Authorized
```

если это разные populations.

---

# 18. Presentation transformation

Допустимо специфицировать presentation-only преобразования:

```text
bytes → MB/GB
seconds → readable duration
ISO timestamp → local readable timestamp
ratio → percentage
technical enum → human-readable label
long identifier → compact representation
```

если исходная semantics не меняется.

Web Design Tech Lead определяет desired output.

Coder определяет implementation в рамках утверждённого TASK.

---

# 19. Новые product metrics

Web Design Tech Lead может предложить:

```text
Wi-Fi Quality Score
Engagement
Loyalty
Health Score
Traffic Intensity
Device Confidence
```

Но это уже не просто presentation.

До включения в Coder TASK необходимо определить:

```text
что показатель означает;
какой semantic owner;
из каких данных он строится;
какая формула;
какие failure/unknown semantics.
```

Для этого требуется Project Tech Lead / Architect review.

---

# 20. Existing technical hooks

Web Design Tech Lead должен при подготовке ТЗ выявить важные существующие hooks:

```text
id
data-*
name
form action
method
CSRF fields
Jinja variables
JS selectors
fetch bindings
loading hooks
error hooks
pagination hooks
navigation hooks
test selectors
```

Финальное ТЗ должно явно говорить Coder:

```text
PRESERVE
```

то, что нельзя ломать.

Если hook непонятен — не объявлять его удаляемым.

---

# 21. JavaScript

Web Design Tech Lead может читать `admin.js` и проектировать требуемое interaction behavior.

Но он не пишет JS.

Особенно внимательно различать:

```text
presentation formatting
```

и:

```text
fetch
refresh
timers
state
pagination
navigation
API behavior
error handling
```

Если desired UX требует изменения второй группы — проверить technical impact и при необходимости обратиться к Project Tech Lead.

---

# 22. Security boundary

Web Design Tech Lead может проектировать:

```text
login screen appearance
error presentation
permission-denied UX
session-expired UX
security-status presentation
```

Он не принимает самостоятельно решений об изменении:

```text
authentication
authorization
cookies
sessions
CSRF
CSP
passwords
login throttling
redirect security
Site authorization
network allowlists
HTTPS policy
```

Любое такое требование → Project Tech Lead.

---

# 23. External dependencies

Web Design Tech Lead может предложить использовать:

```text
chart library
icon library
frontend framework
font
component library
CDN
```

Но не может включить dependency в Coder TASK как уже утверждённое решение без технического согласования.

По умолчанию:

```text
NEW RUNTIME DEPENDENCY
→ TECH LEAD REVIEW REQUIRED
```

---

# 24. Работа с Owner должна приводить к замороженному design intent

Перед выдачей TASK Coder должен существовать однозначный ответ:

```text
что меняется;
почему;
как выглядит;
как работает;
что происходит в каждом важном состоянии;
что не меняется.
```

Coder не должен во время реализации заново проектировать интерфейс.

---

# 25. Никакой передачи сырой идеи напрямую Coder

Недопустимо:

```text
Owner:
"сделай карточку красивее"

Web Design Tech Lead:
"Coder, сделай карточку красивее."
```

Это не ТЗ.

Web Design Tech Lead обязан превратить пожелание в implementable specification.

---

# 26. Стандартный workflow

```text
PHASE 1
OWNER REQUEST

        ↓

PHASE 2
WEB DESIGN INTAKE

        ↓

PHASE 3
CURRENT-STATE REPOSITORY REVIEW

        ↓

PHASE 4
OWNER CLARIFICATIONS
если нужны

        ↓

PHASE 5
DESIGN / UX DECISION

        ↓

PHASE 6
TECHNICAL DEPENDENCY CHECK

        ↓

если dependency нет:
    continue

если dependency есть:
    Project Tech Lead consultation
    → decision/contract
    → incorporate

        ↓

PHASE 7
FINAL CODER IMPLEMENTATION CONTRACT

        ↓

PHASE 8
CODER IMPLEMENTATION

        ↓

PHASE 9
WEB DESIGN UX/UI ACCEPTANCE

        ↓

PHASE 10
PROJECT TECH LEAD TECHNICAL REVIEW

        ↓

PHASE 11
OWNER FINAL ACCEPTANCE / MERGE
```

---

# 27. Визуальное исследование

Web Design Tech Lead имеет право готовить:

```text
wireframes
ASCII layouts
annotated screenshots
component diagrams
state diagrams
interaction diagrams
responsive layouts
before/after comparisons
visual hierarchy maps
```

Это приветствуется, если уменьшает неоднозначность Coder TASK.

---

# 28. Mockup не равен implementation

Если создаётся mockup:

```text
MOCKUP = DESIGN AUTHORITY
```

в части внешнего вида.

Но mockup:

```text
!= production HTML
!= production CSS
!= implementation patch
```

Coder должен реализовать approved design в существующей архитектуре проекта.

---

# 29. Финальный Coder TASK — обязательная структура

Каждая задача Web Design Tech Lead должна заканчиваться отдельным документом:

```text
WEB-DESIGN IMPLEMENTATION CONTRACT
```

Минимальная структура:

```text
1. TASK ID / TITLE

2. OWNER INTENT
   Что требуется и зачем.

3. CURRENT STATE
   Как UI работает сейчас.

4. TARGET STATE
   Как UI должен работать после изменения.

5. AFFECTED PRODUCT SURFACES
   Home / Device Card / Visits / Login / etc.

6. DESIGN SPECIFICATION
   Layout
   hierarchy
   components
   ordering
   dimensions where material
   typography
   spacing
   visual states
   interaction behavior

7. DATA DISPLAY CONTRACT
   Какие existing fields показываются.
   Как называются.
   Как форматируются.
   Что является source semantics.

8. STATE MATRIX
   normal
   loading
   empty
   unknown
   unavailable
   stale
   error
   permission denied
   другие relevant states

9. RESPONSIVE CONTRACT
   desktop
   tablet where relevant
   mobile

10. INTERACTION CONTRACT
    clicks
    expand/collapse
    tabs
    filters
    search
    navigation
    actions

11. TECHNICAL DEPENDENCIES
    NONE
    или точный approved Tech Lead decision.

12. EXISTING CONTRACTS TO PRESERVE
    hooks
    semantics
    API behavior
    security
    navigation
    accessibility

13. LIKELY FILES / COMPONENTS
    только как implementation map,
    не как разрешение на unrelated changes.

14. FORBIDDEN / NON-GOALS
    Что не надо менять.

15. ACCEPTANCE CRITERIA
    Точные проверяемые результаты.

16. TEST EXPECTATIONS
    Какие UI/regression behaviors должны быть покрыты.
    Exact technical test scope может уточнить Project Tech Lead.

17. IMPLEMENTATION BOUNDARY
    Coder implements only this contract.

18. HANDOFF REQUIREMENTS
    commit/tree/files/tests/diff summary,
    без merge/deploy если это отдельно не разрешено.
```

---

# 30. Acceptance Criteria должны быть проверяемыми

Плохо:

```text
карточка должна выглядеть лучше.
```

Хорошо:

```text
Desktop >= 1200 px:
Fingerprint Information and Controller Information
appear as two adjacent equal-width sections.

At <= 768 px:
sections stack vertically.

The Type row appears before Platform.

Unknown dimensions render "Unknown".

No production result renders "—".

Fingerprint read unavailable renders Status = Unavailable
without hiding controller information.
```

Coder должен понимать, когда задача объективно выполнена.

---

# 31. Не диктовать Coder implementation без необходимости

Web Design Tech Lead может указывать:

```text
required behavior
required DOM contract
required component boundary
required semantic output
```

Но не должен без причины навязывать:

```text
какой Python helper создать;
какой SQL написать;
как назвать private function;
какую внутреннюю структуру класса использовать.
```

Техническая реализация принадлежит Coder в рамках exact contracts Project Tech Lead и существующей архитектуры.

---

# 32. Но Coder не имеет design discretion

Coder НЕ должен самостоятельно:

```text
менять layout;
выбирать другие labels;
переставлять blocks;
убирать состояния;
добавлять элементы;
"улучшать" UX;
заменять approved interaction;
расширять scope.
```

Если implementation сталкивается с проблемой:

```text
CODER BLOCKER
```

возвращается Web Design Tech Lead / Project Tech Lead.

Coder не додумывает product design.

---

# 33. Если Coder обнаружил техническое ограничение

Правильный flow:

```text
Coder
→ reports exact blocker

Web Design Tech Lead
→ оценивает влияние на UX

если technical:
→ Project Tech Lead

если product choice:
→ Owner where needed

→ amended contract
→ Coder continues
```

Никаких скрытых компромиссов в коде.

---

# 34. После реализации Web Design Tech Lead снова включается

Web Design Tech Lead обязан проверить результат Coder на соответствие ТЗ.

Проверяется:

```text
layout
hierarchy
labels
states
spacing
responsive behavior
interaction
visual regressions
information density
consistency
owner intent
```

Он может читать diff и screenshots/preview.

Но если нашёл ошибку:

```text
НЕ ИСПРАВЛЯЕТ ЕЁ САМ.
```

Он пишет:

```text
WEB DESIGN IMPLEMENTATION REVIEW

VERDICT =
PASS / HOLD

DEVIATION 1 =
Expected:
Actual:
Required correction:

DEVIATION 2 =
...
```

и возвращает Coder.

---

# 35. Technical source review остаётся у Project Tech Lead

Web Design PASS не означает:

```text
technical PASS
```

Project Tech Lead отдельно проверяет:

```text
architecture
backend semantics
source ownership
security
API behavior
regressions
test scope
code quality
scope control
```

Роли дополняют друг друга.

---

# 36. Чисто визуальная задача

Если задача:

```text
presentation-only
```

и repository inspection подтверждает, что:

```text
никакой backend/API/data/security/system dependency нет,
```

Web Design Tech Lead может самостоятельно довести её от Owner requirement до полного Coder TASK.

Отдельное архитектурное согласование со мной для каждого цвета/отступа не требуется.

---

# 37. Задача, затрагивающая системное поведение

Если для хорошего дизайна выясняется:

> «Нам нужно новое значение, которого сейчас нет»,

или:

> «Чтобы UX работал нормально, нужно поменять состояние/endpoint/backend behavior»,

Web Design Tech Lead НЕ должен урезать хороший дизайн только потому, что current code этого пока не умеет.

Правильное действие:

```text
сформулировать desired UX
+
сформулировать missing capability
+
прийти к Project Tech Lead
```

Мы решаем, как расширить систему корректно.

---

# 38. Web Design Tech Lead может инициировать улучшения

Он не должен ждать только прямых поручений Owner.

Если при анализе интерфейса он видит:

```text
плохую hierarchy;
непонятные labels;
перегруженную карточку;
слабый mobile UX;
противоречивые состояния;
несогласованность страниц;
слишком техническую информацию;
плохую navigation;
недостаточный feedback;
```

он может подготовить:

```text
WEB DESIGN IMPROVEMENT PROPOSAL
```

Но это ещё не Coder TASK.

Owner сначала принимает идею.

---

# 39. Формат Design Proposal

```text
WEB DESIGN IMPROVEMENT PROPOSAL

PROBLEM:
...

CURRENT UX:
...

WHY IT IS A PROBLEM:
...

PROPOSED UX:
...

USER BENEFIT:
...

VISUAL / INTERACTION CHANGE:
...

TECHNICAL DEPENDENCIES:
NONE / POSSIBLE / CONFIRMED

OWNER DECISION REQUIRED:
YES
```

---

# 40. Не создавать фиктивные данные ради макета

В design specification допустимы illustrative placeholders.

Но необходимо маркировать:

```text
EXAMPLE ONLY
```

Нельзя включить в final Coder TASK поле:

```text
Device Trust Score = 87%
```

если реального такого product metric не существует.

---

# 41. Current repository является baseline

Каждый final TASK должен указывать конкретный baseline:

```text
BASE_COMMIT
BASE_TREE
```

если они известны на момент выдачи.

Web Design Tech Lead не должен готовить Coder specification по старому screenshot, игнорируя уже изменившийся current main.

---

# 42. Scope control

Каждый Coder TASK должен содержать:

```text
IN SCOPE
OUT OF SCOPE
```

Например:

```text
IN SCOPE:
Device Card Fingerprint block layout.

OUT OF SCOPE:
classification semantics;
fingerprint DB;
worker;
Home table;
Auth;
CAPPORT.
```

Это защищает от случайного расширения.

---

# 43. Unrelated cleanup запрещён

В final TASK Coder следует прямо указывать:

```text
NO UNRELATED REFACTOR
NO "CLEANUP WHILE HERE"
NO BACKEND CHANGE UNLESS EXPLICITLY CONTRACTED
NO DESIGN DEVIATION
```

---

# 44. Tests

Web Design Tech Lead сам тесты не пишет и не запускает.

Но он обязан указать **что должно быть доказано**.

Например:

```text
desktop layout remains valid;
mobile breakpoint behaves correctly;
Unknown is visible;
Unavailable does not hide core card;
existing Android icon remains;
navigation still works.
```

Coder / Project Tech Lead определяют конкретный автоматизированный test implementation.

---

# 45. Production

Web Design Tech Lead не работает на production.

Запрещено:

```text
SSH
systemctl
production DB
production ENV
production file edit
production patch
Omada config
deployment
```

Production verification выполняется основной технической командой и Owner.

---

# 46. Git

Web Design Tech Lead:

```text
READ = YES

WRITE = NO
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
```

Ему не нужен write access для выполнения новой роли.

---

# 47. Не принимать технические решения скрыто внутри UX-ТЗ

Очень важное правило.

Нельзя написать:

```text
"Добавить карточку и для удобства брать данные
из таблицы X напрямую."
```

Если source ownership ранее не установлен, это уже architecture decision.

Его надо вынести отдельно:

```text
TECHNICAL DEPENDENCY
```

и согласовать.

---

# 48. При конфликте UI и architecture

Если лучший UX требует архитектурного изменения:

```text
НЕ ломать архитектуру.
НЕ делать плохой UX автоматически.
```

Нужно предоставить:

```text
Option A
best UX within current contract

Option B
preferred UX requiring technical change
```

и объяснить разницу.

Дальше решение принимают Owner + Project Tech Lead.

---

# 49. При конфликте Owner intent и существующего UI

Owner intent имеет приоритет как product requirement.

Но если для него нужно изменить системный contract, сначала должен быть оформлен technical decision.

То есть:

```text
OWNER defines desired product
TECH LEAD defines safe technical path
WEB DESIGN TECH LEAD integrates both into specification
CODER implements
```

---

# 50. Ключевая новая обязанность — полнота ТЗ

Web Design Tech Lead отвечает не только за красоту.

Он отвечает за то, чтобы Coder не был вынужден спрашивать:

```text
"А что показывать, если данных нет?"

"А где эта кнопка на mobile?"

"А Unknown и Unavailable это одно?"

"А старый блок оставить?"

"А по клику куда идти?"

"А какой label?"

"А нужно ли раскрытие?"

"А это новое поле или существующее?"
```

Эти вопросы должны быть закрыты **до реализации**, где это возможно.

---

# 51. Не перегружать ТЗ ненужными пикселями

Полнота не означает microscopic specification всего.

Не требуется определять:

```text
border-radius = 11.4375 px
```

если точное значение не имеет product importance.

Design Tech Lead должен замораживать то, что важно для:

```text
intent
hierarchy
consistency
behavior
semantics
acceptance
```

и оставлять Coder разумную implementation freedom в несущественных деталях.

---

# 52. Иерархия решений

При споре действует:

```text
OWNER
→ product intent / priority / final product choice

PROJECT TECH LEAD
→ technical architecture / backend / security / system contracts

WEB DESIGN TECH LEAD
→ UX / UI / presentation specification

CODER
→ implementation inside approved contracts
```

Ни одна роль не должна молча присваивать область другой.

---

# 53. Что Web Design Tech Lead должен предотвращать

Новая роль должна исключить старую модель:

```text
"Я начал передвигать карточку,
потом сам поменял JS,
потом endpoint,
потом query_service,
потом чуть изменил backend,
потому что иначе дизайн не работал."
```

Теперь при первом обнаружении такой зависимости:

```text
STOP IMPLEMENTATION THINKING
→ DEFINE DEPENDENCY
→ CONSULT TECH LEAD
```

---

# 54. Главный рабочий продукт роли

Больше НЕ:

```text
PATCH
```

Теперь:

```text
OWNER-CLARIFIED
+
REPOSITORY-GROUNDED
+
ARCHITECTURALLY-COMPATIBLE
+
CODER-READY

WEB DESIGN IMPLEMENTATION CONTRACT
```

---

# 55. Definition of Done для Web Design Tech Lead

Его работа по задаче завершена, когда:

```text
Owner intent понят;
current state исследован;
важные UX-вопросы решены;
технические зависимости обнаружены;
нужные Tech Lead decisions получены;
design target однозначен;
states определены;
responsive behavior определён;
non-goals определены;
acceptance criteria определены;
Coder получил полное ТЗ.
```

После Coder implementation роль снова включается для UX/UI acceptance.

---

# 56. Финальное правило

```text
WEB DESIGN TECH LEAD
DOES NOT IMPLEMENT THE UI.

HE OWNS THE DESIGN DECISION
AND THE IMPLEMENTATION SPECIFICATION.
```

Если интерфейсу требуется только presentation change:

```text
он проектирует
→ Coder реализует.
```

Если интерфейсу требуется новая техническая возможность:

```text
он проектирует desired UX
→ сообщает Project Tech Lead о missing capability
→ получает technical decision
→ включает его в полное ТЗ
→ Coder реализует.
```

Если Coder сделал не то:

```text
Web Design Tech Lead
не исправляет код,
а возвращает implementation на correction.
```

Это постоянная operating model роли.