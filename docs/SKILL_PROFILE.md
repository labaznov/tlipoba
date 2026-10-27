# Поля навыка из каталога

`damage_lab.skillprofile.profile(skills, tlidb_id, level)` — чистый офлайн-разбор
одной записи каталога на **явно выбранном** уровне. `skills` — объект с ключами
decimal ID и записями master, объединёнными с `english`. Формат результата —
`tli-skill-profile-v0`, версия `0.2.1`. Функция не читает игру, файлы или сеть и
пока не подключена к обычному импорту либо DPS.

Строго положительные integer ID и level исключают bool/float. Запись связывается
по целочисленному `tlidbId`; имя не участвует. `identity.status=exact` означает
только совпадение переданных каталожных данных, `runtimeVerified` всегда false.
GUID — bounded scalar string; непрозрачные объекты не копируются. Источник,
hashes, сезон и связь с установленным навыком проверяет будущий внешний binder.

- `tags`: whole-collection status `supplied|absent|invalid`. Типы урона идут в
  `damageTypes`, `elemental/damage/all` — в `reserved`, остальные нормализованные
  теги — в `skill`. Отсутствие не заменяется пустым списком
- `mainStat`: тот же status и отдельный список `attributes`. Принимаются только
  явные различные Strength, Dexterity, Intelligence; Spell не подразумевает Int
- `effectivenessOfAddedDamage`: процент переводится в exact decimal fraction
- `castSpeedField`: заявленные секунды сохраняются как секунды, не casts/s.
  Смысл поля и его применение к текущей игре ещё не подтверждены
- `hit`: кандидат spell range выбранного level с отдельным статусом и binding

`hit.status=catalog_render_consistent` допустим только при единственной строке
`Deals #-# Spell <Type> Damage`, точном `valueNMin/Max` binding, совпадении числа
токенов и полном рендере reference description; `#-#` считается одним range token,
не двумя символами `#`. Выбранный и reference range
должны быть упорядоченными неотрицательными целыми. Дубликаты уровней, неизвестный
шаблон, rational cell и неверный render не получают числового fallback.

Это внутренняя согласованность каталога. Она не подтверждает effective level,
актуальность базы, post-20 рост, активацию, Tangle inheritance или фактический hit.
Плоская таблица сама по себе не доказывает отсутствие дополнительного роста.
У сохранённого Chromatic Shot 7007 один range token `#-#` с Min/Max convention
воспроизводит полное reference description. Это исправляет раннее ошибочное
предположение о повреждённом binding. Известный конфликт старой SS14 базы,
effective level и post-20 профиль остаются пробелами.
[Исследование контекста](research/chromatic-skill-context.md).

Основа перенесена из проверенного локального helper `skill_profile` 0.2.0.
Версия tlipoba 0.2.1 также отделяет scope `all` от skill tags и отклоняет
повторные main-stat names, чтобы не передавать их downstream kernels как разные
атрибуты. Реальные данные игрока не включены; тесты используют вымышленные записи.

Проверка: `python -m unittest discover -s tests -p test_skillprofile.py -v`.
