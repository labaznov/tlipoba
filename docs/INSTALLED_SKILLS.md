# Наблюдаемые установленные навыки

`damage_lab.installedskills.project(document, source_sha256)` проверяет уже
сформированный artifact `tli-support-inventory-v0`, **только версии 0.1.2**, и
возвращает отделённую snake_case проекцию. `summary(canonical)` повторяет те же
проверки и удаляет неизвестные свойства на всех уровнях. Модуль чистый: без файлов,
manifest, каталога, игры, сети и расчётов.

`source.sha256` должен точно совпасть с явным аргументом — 64 lowercase hex.
`source.binding=caller_supplied` сохраняет заявление вызывающей стороны, а не
доказывает принадлежность персонажу. Вложенные runtime fields остаются строго
`verified=false`, `identity_verified=false`, `freshness=unknown`,
`activation=unknown`, `panel_skill=unverified`.

Сохраняются только известные поля схемы: `source`, `runtime`, `domains`, `groups`
с `members`, `relationships`, `unmatched_server_slots`, `issues` и format/version.
Числа skill ID — публичные ConfigBaseId, gem level — наблюдённый уровень камня,
server key — наблюдённый layout key. Instance/account IDs и raw trees не входят
в проекцию. Флаги установки сохраняются как bool или null.

Client/server domain status — `captured`, `absent`, `invalid`, `not_captured`.
При `captured` counts — неотрицательные целые числа, bool не принимается; при
других статусах все counts равны null. Отсутствующее поле самого artifact — ошибка,
а не основание создать пустой complete domain.

Группы и gem aliases следуют порядку producer и сохраняют точные client tab/row
coordinates. Group status сверяется с наблюдаемыми slots: `ok`, `ambiguous_slot`
или `no_primary_slot`. Несовпавший TabIdx сохраняется с issue; равенство tab position
не навязывается как правило игры.

`exact_instance` требует integer server key и допустимый уникальный server path;
server status допускает только `Activating`, `other` или null. Остальные membership
statuses не могут содержать server key/status/path. Проверяется внутренний учёт
exact matches, unmatched entries и malformed server slots. Скрытые instance IDs
повторно не сопоставляются: consumer проверяет контракт producer, а не raw capture.

Relationships связывают slot-1 primary и другой member того же `ok` group с
известными skill ID и slot. Их единственный смысл — `installed_observed` на основе
`client_tab_co_membership`. Activation всегда unknown, effective level всегда null
с `gem_level_is_not_effective_level`, panel skill — unverified. Это не определяет
роль support, энергию, enabled state, бонусы уровней или реальный эффект на DPS.

Чужая группа, повторный alias/path/edge, несогласованный status/count, недопустимое
значение, версия или SHA вызывают контролируемый `ValueError` без входного payload.
Положительные флаги Valid/IsActive/Activating не повышают runtime claims.
