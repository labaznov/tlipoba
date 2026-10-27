# Специальные поддержки: исходные строки и конверсия

Проверено 2026-10-22 по ранее сохранённому каталогу SS14 и результатам офлайн-аудитов
exporter 0315/0328. Это привязка статических определений к данным экспорта;
активация, актуальность патча и применение к выбранному навыку не подтверждены.
Нового доступа к игре не было. Реальные роллы и данные игрока остаются локальными.

## Точные идентификаторы

| Определение | Категория | Base ID | Tiered line ID |
|---|---|---|---|
| Chromatic Shot: Condensed Cold | Noble_Support | 8108 | 77103305 |
| Chromatic Shot: Lightchaser | Magnificent_Support | 7986 | 77103279 |
| Activation Medium: Tangle | Activation_Medium | 8030 | 77103276, 77103277, 77103288 |

Это публичные идентификаторы каталога. Ordinary supports Multiple Projectiles 7401
и Critical Strike Damage Increase 7420 имеют отдельные level tables; правила их
уровней нельзя переносить на tiered строки.

В сохранённом native поддереве строки имеют поля `Prefix[i].Id`, `DynArgs`,
`Version`. Полный `Id` сопоставляется с **ровно одним**
`tierProgression[t].lines[].modifierId`; строка также должна быть объявлена в
`lines[]`. Нельзя отрезать цифру, искать ближайший tier или сопоставлять по имени.
`DynArgs` проверяются по числу параметров и диапазону именно найденного tier.
Preview description не заменяет фактический roll. Значение `Version` само по себе
не доказывает ранг, вариант или правило активации.

Для 8108 точная английская строка задаёт процент additional Hit Damage; для 7986 —
процент additional damage, включая отрицательные значения в своих диапазонах.
Знак сохраняется: отрицательный roll не превращается в положительный через `abs`.
В отдельной двухпараметрической строке Tangle знак Movement Speed не согласован с
положительным диапазоном и явным минусом шаблона; такой случай остаётся пробелом.

## Константы без native roll

В английском `templateDescription` записи 8108 есть буквальная конверсия 100%
Physical → Cold для урона поддержанного навыка. В этой строке нет placeholder `#`;
для неё нет отдельной tiered line или native `DynArgs`. Источник константы — само
определение каталога, а не выдуманный roll.
[Condensed Cold](https://tlidb.com/en/Chromatic_Shot_Condensed_Cold_Noble).

Формулировка относится к Physical Damage навыка целиком. Она согласуется с обычной
конверсией, при которой сохраняется применимость бонусов исходного и конечного
типов. Это кандидат для уже существующего rawspell Physical→Cold пути; совпадение
текста не подтверждает runtime порядок или активацию.
[Damage Type Conversion](https://tlidb.com/en/Damage_Type_Conversion).

У обеих поддержек есть дополнительная константа damage; у Lightchaser также есть
main-attribute ratio, Projectile Speed и tracking. Эти строки отделяются от
роллируемых. Одинаковый текст двух damage-констант **не устанавливает общую affix
identity**: их pooling и порядок остаются неизвестными. Ratio разобран отдельно в
[main-attribute-damage.md](main-attribute-damage.md).
[Lightchaser](https://tlidb.com/en/Chromatic_Shot_Lightchaser_Magnificent).

Панель уже содержит вклад Lightchaser в агрегате Additional Damage. Повторное
применение этих строк к панельному DPS недопустимо. Отдельное сырое моделирование
требует полных источников и доказанной семантики групп.

## Происхождение английского текста

Master записи поступили из `/data/SS14/skill/<category>/master.json`, английские
поля — из `/data/SS14/skill/<category>/i18n/en.json`, entry `skills[<guid>]`.
GUID определяется точной master записью по base ID, а не поиском текста. Wrapper
master и wrapper английского текста — разные документы:

- Master wrapper SHA256:
  `7de41c53bf9d5391b0b9f2e3889c61fc9fb2c61ffa8b937cfb157786bee94c57`
- English wrapper SHA256:
  `0c41bcb0f740372338d33aeee1ff8c8e3f7cfea0455baa652f220d81849a1e94`

Hash относится к сохранённым локальным bytes, а не исходному HTTP ответу или
текущему клиенту. Аудит 0328 сохраняет точные member byte ranges/hashes, entry
identity и проверяет равенство текста с полями, объединёнными `guide_model.Catalog`.
Отдельный master hash не связывает английскую константу.

`templateDescription` — одна JSON string. После JSON decoding координата
`{field: "templateDescription", line: k}` означает нумерацию с нуля в
`text.split('\n')`, LF only. Это индекс текстовой строки, а не JSON array. Тела
исследованных записей не содержат CR. Unknown literal сохраняется как причина и
координата; opaque текст не требуется переносить в публичный отчёт.

## Что ещё блокирует арифметику реального билда

- Связь установленного состава с выбранным навыком, активация и актуальный патч
- Effective levels обычных поддержек и точные финальные характеристики
- Additional pool identity констант и оператор main-attribute ratio
- Shotgun/hit topology, наследование Tangle и времена действия эффектов
- Несогласованность знака указанной строки Tangle

Известный конфликт SS14 базы/эффективности Chromatic Shot 7007 в старом каталоге
сохраняется. Preview с falloff 70% не выбирается автоматически вместо более нового
источника с 80%. Эти привязки позволяют расширять автоматический импорт, но не
объявлять точный итоговый DPS.
