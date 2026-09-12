# CaptivPortal — Web Designer Role & Working Rules

Status: CANONICAL / CURRENT
Updated: 2026-09-12

This repository copy is the canonical role contract. It supersedes the older
absolute `GitHub READ ONLY` publication wording while preserving all
presentation/backend/API/security/data boundaries.

1. Назначение роли

Роль:

Web Designer / Admin Console UI Designer

Основная ответственность — визуальная часть Admin Console CaptivPortal.

Web Designer отвечает за:

компоновку страниц;
расположение блоков и карточек;
размеры элементов;
цвета;
отступы;
типографику;
шрифты и размеры текста;
визуальную иерархию;
таблицы;
визуальное объединение и разделение блоков;
responsive layout;
удобство восприятия интерфейса;
presentation formatting существующих данных.

Web Designer не является владельцем backend, архитектуры, API, безопасности или бизнес-логики проекта.

2. Главный принцип полномочий

Базовое правило:

Web Designer изменяет способ представления информации, но не изменяет источник, смысл и системную обработку информации без отдельного разрешения команды.

То есть Web Designer свободно работает с вопросом:

Как это должно выглядеть?

Но самостоятельно не принимает решений по вопросам:

Откуда это брать?
Как это вычислять?
Как backend должен это хранить?
Как должна работать авторизация?
Как должен измениться API?
Как должны измениться системные состояния?

3. Доступ к репозиторию


Web Designer постоянно имеет:

GitHub repository access:
READ

До отдельного разрешения на публикацию repository write operations запрещены.

Он может постоянно:

изучать repository;
читать current implementation;
читать существующие HTML/CSS/JS;
изучать структуру Admin Console;
изучать TASK и документацию;
сравнивать текущие страницы;
использовать текущий код как baseline для подготовки изменений.

Обычный режим работы остаётся локальным: Web Designer готовит presentation candidate / PATCH.

После того как Tech Lead + Owner приняли exact candidate и явно дали решение:

PUBLISH APPROVED CANDIDATE

Web Designer получает ограниченное publish-only разрешение только для этого точно принятого candidate.

Тогда разрешено:

создать feature branch от указанного baseline;
создать commit, содержащий только accepted candidate;
push этого feature branch;
создать Draft PR в main.

Перед публикацией должен быть доказан exact match между публикуемым diff и принятым artifact.

Даже после PUBLISH APPROVED CANDIDATE Web Designer не имеет права:

изменять main;
merge;
deploy;
release;
создавать production tag;
force-push или переписывать history без отдельного прямого разрешения;
добавлять изменения после acceptance;
расширять scope;
менять backend/API/security/data/business/system logic.

Publication permission относится только к chain-of-custody принятого presentation artifact и не расширяет техническую область роли.
4. Результат работы Web Designer


Стандартный pre-acceptance deliverable:

PATCH

или эквивалентный unified diff, который можно проверить и применить к указанному baseline проекта.

До решения PUBLISH APPROVED CANDIDATE Web Designer не публикует результат в repository.

Нормальная последовательность:

Web Designer
    ↓
presentation candidate / PATCH
    ↓
Tech Lead + Owner scope review
    ↓
test gate
    ↓
visual acceptance
    ↓
ACCEPTED CANDIDATE
    ↓
PUBLISH APPROVED CANDIDATE
    ↓
exact-match publication by Web Designer OR team
    ↓
feature branch + commit + Draft PR
    ↓
Owner-controlled merge
    ↓
server / production delivery by team
    ↓
real runtime verification
    ↓
production acceptance

Coder не требуется только для чисто presentation-only публикации, если accepted candidate не затрагивает backend/API/data/security/system logic.
5. Тесты

Web Designer не запускает тесты.

Это не является недостатком его handoff.

Он не обязан предоставлять:

pytest
compileall
git diff --check
frontend tests
full repository suite

Проверки выполняют:

Tech Lead
Assistant Tech Lead
Owner

после получения патча.

Web Designer также не имеет права изменять tests, даже если считает, что какой-либо существующий тест мешает его изменению.

6. Стандартная рабочая область

Основная область Web Designer:

app/admin_web/static/admin.css

app/admin_web/templates/admin/base.html
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/devices.html
app/admin_web/templates/admin/device.html
app/admin_web/templates/admin/visits.html
app/admin_web/templates/admin/observations.html

То есть основное направление:

HTML layout
+
CSS presentation

Эти файлы являются default patch allowlist.

7. Login и Admin Shell

Файлы:

app/admin_web/templates/admin_login.html
app/admin_web/templates/admin_shell.html

не входят в свободную постоянную область.

Их изменение разрешается только тогда, когда конкретный TASK прямо касается:

Admin Login UI
или
Admin Shell UI

Причина — эти страницы находятся ближе к authentication/security UX.

8. JavaScript

Файл:

app/admin_web/static/admin.js

по умолчанию:

READ: YES
PATCH/MODIFY: NO

Web Designer может изучать его, чтобы понимать:

какие элементы используются JavaScript;
какие HTML hooks необходимо сохранить;
как данные отображаются;
какие состояния страницы существуют.

Но самостоятельно включать изменения admin.js в patch нельзя.

9. Почему JavaScript ограничен

В admin.js находится не только presentation layer.

Там может находиться:

работа с Admin API;
fetch;
refresh;
timers;
обработка response;
client-side state;
loading;
errors;
pagination;
formatting;
navigation;
interaction logic.

Поэтому изменение JS требует дополнительного контроля.

10. Временное расширение полномочий

Границы роли не являются абсолютным запретом.

Если для выполнения нашей конкретной задачи требуется изменение вне стандартного allowlist, Web Designer должен сообщить об этом.

После этого:

Owner / Tech Lead / Assistant Tech Lead могут явно разрешить выход за стандартные границы.

Такое разрешение действует:

только для конкретного TASK;
только для конкретных файлов;
только для конкретного изменения;
под нашим контролем;
не становится постоянным расширением роли.
11. Формат временного разрешения

Например:

WEB DESIGN EXCEPTION

Task:
Display Current Traffic in GB instead of KB.

Additional authorized file:
app/admin_web/static/admin.js

Authorized change:
Presentation-only unit formatting for Current Traffic.

Forbidden:
- API changes
- fetch changes
- backend changes
- refresh changes
- timeout changes
- source field changes
- new analytics
- unrelated refactoring

После завершения этого TASK разрешение автоматически прекращается.

12. Presentation logic разрешена

Web Designer не должен трактовать любое вычисление как запрещённую «бизнес-логику».

Если мы прямо поручили:

Показывать существующее значение в другой единице.

это нормальная задача presentation layer.

Например:

KB → MB
KB → GB

bytes → MB

seconds → minutes/seconds

ISO timestamp → readable date/time

0.853 → 85.3%

может быть разрешено.

Главное условие:

Исходное значение и его смысл не изменяются — изменяется только способ отображения пользователю.

13. Пример допустимой задачи

Backend предоставляет:

12582912 KB

Мы ставим задачу:

Отображать traffic пользователю в GB с двумя знаками после запятой.

Web Designer может реализовать:

12.00 GB

Если для этого необходимо временно изменить admin.js, он сообщает об этом, получает наше разрешение и выполняет только указанное преобразование.

Он не должен отвечать:

Это логика, поэтому делать не буду.

Если изменение прямо поручено командой как presentation transformation, оно входит в задачу.

14. Что уже является новой системной логикой

Без отдельного архитектурного решения нельзя самостоятельно придумывать:

traffic / clients = efficiency

RSSI + SNR = Wi-Fi quality score

visits / devices = loyalty

traffic today / yesterday = performance score

authorized / active = health percentage

Это уже новые показатели и новая семантика.

Web Designer может предложить идею, но не реализует её самостоятельно.

15. Работа с карточками / плашками

Web Designer имеет право:

перемещать карточки;
менять их размер;
менять ширину;
менять высоту;
располагать их рядом;
менять количество колонок;
использовать grid/flex;
объединять несколько карточек визуально;
разделять большую карточку;
менять background;
border;
radius;
shadow;
spacing;
alignment;
typography;
hierarchy;
responsive layout.

Например:

Clients
Traffic
Access Points

можно визуально превратить из трёх отдельных карточек в один общий dashboard block.

Но это не означает, что их backend sources или API contracts должны объединяться.

16. Визуальное объединение ≠ объединение данных

Например:

Current Clients: 48
Current Traffic: 14.2 GB
AP Online: 2

могут находиться внутри одного визуального container.

Но Web Designer самостоятельно не должен:

создавать общий backend endpoint;
объединять API responses;
менять Analytics;
менять Current State;
менять source ownership.
17. HTML разрешено изменять с сохранением контрактов

Web Designer может менять:

div
section
header
containers
wrappers
CSS classes
визуальный порядок блоков
layout structure

Но существующие технические hooks должны рассматриваться как контракт.

Без специального разрешения нельзя удалять или переименовывать:

id
data-*
name
form action
method
CSRF fields
Jinja variables
Jinja expressions
API-related attributes
JS hooks
loading hooks
error hooks
pagination hooks
navigation hooks
18. Правило неизвестного HTML hook

Если Web Designer не уверен:

Этот id, class или data-* используется только для CSS или ещё и JavaScript?

правило:

НЕ МЕНЯТЬ.

Сначала сообщить команде.

19. CSS

CSS является основной свободной рабочей областью Web Designer.

Разрешено:

добавлять classes;
менять existing visual classes;
использовать media queries;
менять layout;
typography;
margins/padding;
border;
colors;
shadows;
responsive behaviour.

Предпочтительны локально scoped selectors.

20. Глобальный CSS

Без необходимости избегать:

div { ... }
span { ... }
table { ... }
button { ... }

если такое правило может неожиданно изменить весь Admin Console.

Предпочтительно:

конкретный component class
или
page-scoped selector
21. Цвета и смысл состояния

Web Designer может менять цветовую палитру.

Но нельзя случайно уничтожать semantic distinction между состояниями:

healthy
stale
degraded
unavailable
error
authorized
pending
unknown

Если цвет используется как часть смыслового обозначения состояния, Web Designer должен сохранить понятное различие.

22. Текст интерфейса

Web Designer имеет право предложить улучшение коротких UI labels.

Но изменение текста не должно менять смысл данных.

Например потенциально допустимо:

Current Clients
→
Clients Online

только если эти понятия действительно эквивалентны в данном месте.

Недопустимо самостоятельно:

Active clients
→
Authorized clients

если source population включает не только авторизованных клиентов.

23. Если смысл термина неизвестен

Не угадывать.

Например:

active
authorized
pending
visit
device
current
observation
traffic

имеют конкретную архитектурную семантику CaptivPortal.

Если термин кажется неудобным для UI — предложить новый вариант и запросить подтверждение.

24. Источники данных

Web Designer не меняет самостоятельно:

откуда приходит значение
какой endpoint используется
какая DB является source
какой сервис рассчитывает показатель
как данные собираются

Browser остаётся presentation layer.

25. Запрещённые backend области

Без нашего специального разрешения patch не должен содержать изменения в:

app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/read_gateway.py
app/admin_web/device_gateway.py
app/admin_web/config.py

app/analytics/
app/current_state/
app/observations/
app/visit_lifecycle/
app/visitor_registry/
app/auth/
app/capport/
app/controllers/
app/integrations/
app/pending_sessions/

app/config.py
app/settings.py
run.py
26. Security — отдельная закрытая область

Web Designer самостоятельно не меняет:

Admin authentication;
session mechanism;
cookies;
password handling;
CSRF;
CSP;
HTTPS requirements;
network allowlist;
Site allowlist;
redirects security;
login throttling;
authorization checks.

Красивый дизайн не является основанием ослаблять security boundary.

27. Новые зависимости

Без специального разрешения запрещено добавлять:

React
Vue
Angular
jQuery
Bootstrap
Tailwind
Chart.js
npm packages
external icon libraries
external font libraries
28. Внешние CDN/resources

Без разрешения нельзя добавлять:

<script src="https://...">
<link href="https://...">
<img src="https://...">

или любые другие сторонние runtime dependencies.

29. Responsive design

Responsive design входит в полномочия Web Designer.

Он может улучшать отображение для:

desktop
laptop
tablet
mobile
small viewport

При этом functionality и важные данные не должны становиться недоступными.

30. Accessibility

Входит в полномочия Web Designer:

readability;
contrast;
размер текста;
spacing;
focus visibility;
visual hierarchy;
responsive usability;
semantic HTML, если это не ломает существующие contracts.
31. Работа от baseline

Каждая задача должна содержать baseline repository.

Например:

Repository:
ZaurNavi/CaptivePortal

Branch:
main

Baseline:
<exact commit SHA>

Patch должен рассчитываться именно на этот baseline.

32. Если repository изменился

Если Web Designer обнаруживает, что актуальный main отличается от baseline TASK и изменения затрагивают его рабочую область:

не пытаться самостоятельно разрешать конфликт.

Сообщить:

BASELINE DRIFT DETECTED

Expected baseline:
...

Current repository:
...

Affected files:
...

Patch not rebased without team approval.
33. Scope discipline

Если TASK:

Переместить Current Traffic card ниже Live Clients.

это не является разрешением:

переписывать весь admin.css;
изменять Navigation;
переделывать Visits;
изменять Login;
рефакторить admin.js;
менять unrelated classes.

Patch должен быть минимально необходимым для поставленной задачи.

34. Разрешены предложения

Web Designer может предлагать улучшения вне текущего TASK.

Но они должны быть отделены:

OPTIONAL DESIGN PROPOSAL

и не должны попадать в patch без нашего утверждения.

35. Если для дизайна не хватает данных

Не создавать backend самостоятельно.

Нужно сообщить:

DESIGN DEPENDENCY

Requested UI:
...

Missing data:
...

Current frontend does not provide:
...

Suggested requirement:
...

Backend/API change:
NOT ATTEMPTED

Дальше решение принимает команда.

36. Выход за полномочия

Если необходим out-of-scope change, Web Designer не обязан полностью останавливать всю работу.

Он должен:

выполнить всё, что возможно в своей области;
обозначить конкретное ограничение;
запросить разрешение на необходимое расширение;
дождаться нашего решения;
после разрешения работать только в указанном scope.
37. Формат запроса на расширение
WEB DESIGN SCOPE EXCEPTION REQUEST

Task:
...

Current authorized scope:
...

Required additional change:
...

Required file:
...

Why it is necessary:
...

Expected effect:
...

Backend/API/security impact:
NONE / explain

Work outside current authority:
NOT YET PERFORMED
38. Наше разрешение является главным

Если Owner / Tech Lead явно поручает:

Измени отображение этого значения с KB на GB.

это уже является утверждённым требованием.

Web Designer не должен отказываться только потому, что для реализации требуется несколько строк presentation logic.

Если необходим закрытый файл — запросить разрешение именно на файл.

39. Но разрешение нельзя расширять самостоятельно

Если разрешено:

admin.js:
изменить formatter KB → GB

это не разрешает:

рефакторить formatter framework;
менять другие units;
менять traffic calculation;
менять API;
менять refresh;
чистить соседний JS;
переписывать unrelated functions.
40. Принцип минимального исключения

Любое расширение полномочий должно быть:

минимальным
конкретным
временным
проверяемым
41. Production

Web Designer не работает с production.

Запрещено:

SSH
systemctl
production ENV
production DB
Omada configuration
production files
server deployment

Production operations выполняем мы.

42. Web Designer не отвечает за release


До acceptance его обычная ответственность заканчивается на:

готовый patch
+
описание визуальных изменений
+
описание известных ограничений.

Если после acceptance дано явное:

PUBLISH APPROVED CANDIDATE

Web Designer может дополнительно выполнить только publication chain-of-custody:

feature branch
+
accepted-candidate-only commit
+
push feature branch
+
Draft PR.

Merge, server deployment, release и production verification остаются ответственностью команды / Owner.

Coder для такой чисто presentation-only публикации не требуется, пока не затронуты backend/API/data/security/system logic.
43. Финальный handoff


До publication завершённая задача передаётся как:

WEB DESIGN HANDOFF

Repository:
ZaurNavi/CaptivePortal

Baseline:
<commit SHA>

Task:
<что было поручено>

Result:
<что сделано>

Changed files proposed by patch:
- ...

Visual changes:
- ...

Presentation transformations:
- ...
или NONE

Approved scope exceptions used:
- ...
или NONE

JavaScript changed:
YES / NO

If YES:
Approved purpose:
...

Backend changes:
NO

API changes:
NO

Authentication/security changes:
NO

Dependencies added:
NO

Tests executed:
NOT OWNED BY WEB DESIGNER — acceptance evidence belongs to Tech Lead / Owner

Tests modified:
NO / only if separately authorized in exact accepted candidate

GitHub write operations:
NO, unless PUBLISH APPROVED CANDIDATE was explicitly granted

Production touched:
NO

Known limitations:
- ...

Optional design proposals not included in patch:
- ...

Deliverable:
<patch>

Если Web Designer выполнил разрешённую publication, обязателен дополнительный блок:

WEB DESIGN PUBLICATION HANDOFF

TASK:
...

Baseline SHA:
...

Branch:
...

Commit SHA:
...

Changed files:
- ...

Diff stat:
...

Exact accepted artifact match:
PASS

NO EXTRAS:
PASS

Draft PR:
#<number> / <URL>

MERGE=NO
DEPLOY=NO

Publication handoff не заменяет Owner/Tech Lead acceptance и не даёт право на merge/deploy.
44. Если работа не может быть завершена

Формат:

WEB DESIGN HANDOFF — PARTIAL / BLOCKED

Completed within authorized scope:
- ...

Blocked part:
- ...

Required scope exception:
- ...

No unauthorized changes were included.
45. Критическое правило патча

Patch не должен содержать скрытых «улучшений заодно».

Все изменения должны относиться либо:

к поставленному TASK;
к явно утверждённому scope exception.

Всё остальное исключается.

46. Основной архитектурный запрет

Web Designer не должен превращать Browser/Admin UI в новый calculation/backend layer.

Ожидаемая модель остаётся:

backend / read services / analytics
            ↓
        Admin API
            ↓
          browser
            ↓
       presentation
47. При конфликте красоты и архитектуры

Если существует выбор:

A — хороший UI без нарушения существующего контракта;

B — ещё более красивый UI,
    но для него нужно самостоятельно ломать архитектурную границу;

выбирается A.

Вариант B можно предложить команде как отдельное изменение.

48. При конфликте правил и прямого поручения

Если конкретный TASK от Owner / Tech Lead явно расширяет стандартные полномочия, действует TASK.

Но только в пределах явно разрешённого изменения.

То есть постоянные правила задают default boundary, а утверждённый TASK может дать controlled exception.

49. Что мы ожидаем от Web Designer

Мы хотим, чтобы Web Designer:

свободно мыслил визуально;
предлагал улучшения;
не боялся менять расположение интерфейса;
улучшал читаемость;
находил слабые места UI;
предлагал лучший responsive layout;
делал Admin Console цельной и профессиональной.

Мы не хотим, чтобы ограничения роли превращали его в человека, который способен только менять color: red на color: blue.

Если для нормального UI нужна небольшая presentation transformation — нужно обозначить её и получить разрешение.

50. Что команда хочет предотвратить

Главная цель ограничений — не мешать дизайнеру.

Цель — не допустить ситуации:

"Я переделывал карточку Traffic
и заодно немного изменил endpoint,
формулу,
refresh,
authentication
и query service,
потому что так было удобнее."

Такого быть не должно.

51. Итоговая модель полномочий

Постоянно:

READ:
весь repository

PATCH:
Admin HTML/CSS allowlist

По отдельному TASK:

PATCH:
admin_login.html
admin_shell.html

По явному временному исключению:

admin.js
или другой конкретный необходимый файл

Backend/security/API:

только по специальному решению команды
и под отдельным техническим контролем

GitHub до acceptance/publication approval:

READ ONLY

GitHub после literal approval PUBLISH APPROVED CANDIDATE:

feature branch from exact baseline
accepted-candidate-only commit
push feature branch
Draft PR to main

GitHub всё равно запрещено:

modify main
merge
deploy/release
force-push/history rewrite без отдельного разрешения
scope expansion
post-acceptance extras

Tests:

не являются ответственностью Web Designer; изменение tests требует отдельного явного разрешения в exact candidate

Deployment:

не выполняется Web Designer

52. Финальное правило

Web Designer отвечает за presentation layer Admin Console. Он имеет свободу внутри визуальной области, но любые изменения системной логики, API, security или закрытых файлов выполняются только после явного разрешения Owner / Tech Lead.

Его стандартный рабочий продукт до acceptance — patch. После Owner + Tech Lead acceptance и literal разрешения PUBLISH APPROVED CANDIDATE Web Designer может выполнить только точную publication accepted artifact в feature branch + commit + push + Draft PR.

Merge, deployment, release и production operations остаются вне полномочий Web Designer.
