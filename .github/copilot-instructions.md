Read AGENTS.md first.
Use docs/ as the project knowledge base.
Use the current TASK as the scope contract.
Do not reconstruct architecture from repository history when current docs exist.

# GitHub Copilot adapter for CaptivPortal

Status: current
Updated: 2026-08-04

Это только платформенный адаптер. Универсальные правила находятся в AGENTS.md и не дублируются здесь.

Перед изменением открой только документы, перечисленные в TASK, проверь фактические связанные файлы и тесты и не расширяй scope.

Если implementation TASK отсутствует или не определяет execution mode, allowed files, repository actions либо test responsibility, запроси уточнение до изменений.

Для Copilot Code Review отсутствие отдельного TASK не блокирует проверку PR целиком. Отметь scope ambiguity, затем продолжи проверку security, correctness и regression risks. Не предлагай и не вноси расширяющие scope исправления без отдельного разрешения.

Используй path-specific instructions из .github/instructions/ только для затронутых путей. Не загружай все инструкции одновременно.

В ответе не заявляй о test, commit, push, PR, merge или deploy без фактического результата. По умолчанию PR должен быть Draft; merge выполняет только owner.
