# Chromatic Shot: source-bound skill context

Проверено 2026-10-22, только по сохранённым guide/source и локальному каталогу. Нового чтения игры, лога, сети или `.pak` не было. Поля каталога уже извлекает чистый skillprofile; byte-level binder и resolver точного DPS ещё не реализованы.

## Источники и точная адресация

Каталожная identity основного навыка: `tlidbId=7007`, GUID `261da8ef-2841-5f03-994c-e8f20d7d20d2`. Master: `skill/Active/master.skills[id=<GUID>]`; английский текст: `skill/Active/i18n/en.skills[<GUID>]`. Соответствие проверено одновременно по полному GUID и game ID; имя навыка не является ключом.

Сохранённые публичные контейнеры Compendium:

| Файл в exporter `catalog-cache/` | SHA-256 | Содержание |
| --- | --- | --- |
| `433814c7bbad21fe.json` | `7de41c53bf9d5391b0b9f2e3889c61fc9fb2c61ffa8b937cfb157786bee94c57` | Master активных навыков и поддержек |
| `d91d89a4c5e47cd2.json` | `0c41bcb0f740372338d33aeee1ff8c8e3f7cfea0455baa652f220d81849a1e94` | English для тех же категорий |

Их logical paths совпадают с сохранённым `current-manifest.json.mappings`; это проверка локальной адресации, а не актуальности сервера. Класс источника — сторонняя каталожная компиляция; она не заменяет native-схему текущей игры. `schemaVersion=1`, `seasonId=SS14` не доказывают применимость конкретного обновления. Байты source/guide, связи предметов и построчный аудит сохранены только в ignored research.

## Поля основного навыка

В master есть `levelProgression[level=<L>]`. Таблица содержит уровни 1–40; база растёт до 20, затем повторяется. Ниже «corroborated» означает сопоставление именованного поля с английским описанием этого каталога, не проверку текущего native-формата.

| Поле | Возможная роль / единица | Сила свидетельства и граница |
| --- | --- | --- |
| `value1Min`, `value1Max` | Нижняя/верхняя база spell physical hit, damage | Явный Min binding с парой Max воспроизводит полное reference description; только согласованность сохранённого каталога |
| `value2` | Базовое число снарядов, count | Corroborated только постоянным числом в предложении; явного field-role binding нет |
| `value3` | Внутренний бонус количества снарядов, count | Та же граница; не тождественен итоговому UI Projectile Quantity Bonus |
| `value4` | Шанс взрыва при убийстве, percent points | Та же граница; это отдельное условное событие |
| `value5` | Урон взрыва относительно Max Life жертвы, percent points | Та же граница; не база spell и не постоянный more основного hit |
| `value6` | Радиус взрыва, metres | Та же граница; не множитель урона |

**Привязка базового диапазона подтверждена офлайн-аудитом 0342.** `descriptionBindings` у Chromatic указывает `value1Min`; один токен диапазона `#-#` использует его вместе с `value1Max`. Он содержит два символа `#`, но это не два независимых плейсхолдера. Полная подстановка на reference level 20 точно воспроизводит все восемь строк English description. Ранний вывод о повреждённом binding был ошибкой подсчёта символов. Поля `value2..6` не перечислены в bindings; совпадения постоянных чисел не позволяют resolver назначить им роли. Version/effective-level gates этим не закрываются.

[Helper `skill_values.resolve`](C:/Repos/tli-build-exporter/skill_values.py:111) при совпадении description level с gem level возвращает `catalog_level` без проверки шаблона. Это характеристика показанного текста, не сертификат field-role mapping. [Наш `skillvalues.parameters`](../../damage_lab/skillvalues.py:40) проверяет уровень, числа и исходные cells. Новый [skillprofile](../SKILL_PROFILE.md) отдельно проверяет токены, Min/Max convention и полный reference render; исправлять сохранённый binding 7007 не требуется. Byte-level source/catalog binder, актуальная версия и effective level остаются отдельными prerequisites.

Аудит 0342 проверил точные member slices сохранённых wrappers: master `skill/Active/master`, SHA256 `f6f3fc68063992a1e626dddd08292f50696b7b31cafff4b8d00fce561bb5f4b1`; English `skill/Active/i18n/en`, SHA256 `fb6f25319d2d9a9ecbf7b793315af67f69e45d96dd93c2195f36df51ea4e1b82`. Это хеши локальных member bytes, не HTTP/client bytes. Независимая повторная проверка подтвердила единственную запись, grammar, полный рендер и отказ при изменении одного символа reference.

Metadata этого master: `castSpeed="0.65 s"`, `effectivenessOfAddedDamage="131%"`; `tags` перечисляет Spell, Projectile, Area, Physical, Horizontal и три элементальных тега; `mainStat` содержит Strength, Dexterity, Intelligence. Значение в секундах может быть нормализовано как заявленный каталогом интервал, но не как число casts/s; обратная величина требует отдельного правила cast speed. Процент effectiveness нормализуется делением на 100. Base critical rating/chance/multiplier в проверенных master/English отсутствуют: не подставлять стандартное число или ноль. Теги не доказывают три одновременно наносящихся элемента либо фактическую conversion.

## Обычные и особые поддержки

Для обычных `skill/Support` записей 7401 и 7420 единственный `value1` привязан к единственному процентному плейсхолдеру; рендер строки каталожного уровня воспроизводит English. Роль: additional damage поддерживаемого навыка для 7401; **crit-only additional damage**, а не crit multiplier, для 7420. Значения каталога на уровне 20 — 15% и 35.5%; это публичные ячейки таблицы, не роллы персонажа. Постоянный бонус снарядов 7401 находится в тексте, отдельно от `value1`. В проверенном экспорте у обычных поддержек нет native Prefix-строк; их отсутствие не даёт основания выдумывать line ID.

Особые поддержки и Activation Medium используют `tierProgression[].lines[]`, `modifierId` и `lineTemplates[line.id]`, а не обычную таблицу gem level. Соединение: exact game ID + GUID навыка, затем **полный** native `Id == modifierId`; ни обрезание tier-цифры, ни имя, ни `previewTier` не заменяют этот join. Публичные роли строк:

| Skill ID / line ID | Аргументы по English template | Ограничение |
| --- | --- | --- |
| 8030 / `77103276` | Additional damage, percent points | Native roll; grouping/activation отдельны |
| 8030 / `77103277` | Радиус проверки, m; интервал создания, s | Не интервал атак уже прикреплённого Tangle; дополнительный Tangle — отдельная константа текста |
| 8030 / `77103288` | Attach Range, percent points; Movement Speed, signed percent points | Требуется отдельное правило знака native аргумента |
| 7986 / `77103279` | Additional damage, signed percent points | Отрицательный roll не превращать в положительный или preview-середину |
| 8108 / `77103305` | Additional **Hit** Damage, percent points | Не универсальный damage scope |

Все пять наблюдаемых непустых native-строк имеют единственное exact-ID совпадение. Есть null-padding; его надо учитывать отдельно, а не считать эффектом. **Один exact-ID join недостаточен:** у `77103288` второй native аргумент уже отрицателен, тогда как template добавляет минус, а tier bounds записаны положительными. Прямая подстановка даст двойной минус и ложную ошибку диапазона. Сохранённый native `Simple` подтверждает порядок и знак для этой строки; нужен явный signed-role binding, а не общий `abs()` или перестановка чисел.

Фиксированные header clauses особых поддержек не являются найденными native line rolls. Их +damage, conversion, main-stat effect и ограничения слота требуют собственных полей происхождения/активации. Не синтезировать им modifier ID и не объединять автоматически с динамической строкой в один pool.

## Контракт и gates будущего resolver

Минимальный результат будущего binder хранит раздельно. Ниже общий вымышленный пример с неизвестной привязкой поля; это не статус уже проверенного base binding 7007:

```json
{
  "identity": {"tlidbId": 9000, "guid": "synthetic-guid", "status": "exact_catalog_match"},
  "source": {"masterSha256": "...", "englishSha256": "...", "path": "skill/Active/..."},
  "levels": {"exported": 17, "effective": null, "status": "effective_level_unknown"},
  "version": {"catalogSeason": "SS14", "runtimePatch": null, "status": "unverified"},
  "fields": [{"role": "base_min", "cell": "value1Min", "unit": "damage", "status": "unresolved"}],
  "gaps": ["field_binding", "effective_level", "version_profile"],
  "applicableToDps": false
}
```

1. Exact identity, source/guide byte hashes и native source paths сохраняются без повышения до verified character identity/freshness. Публичная projection не содержит instance IDs.
2. Numeric cells разбираются без eval; требуются единственный level row, finite values, известные unit/sign/owner/scope и неповреждённые bindings. Неразрешённые поля не получают числовой DPS effect.
3. `exported` не заменяет `effective`: global/tag/active/passive level modifiers, лимиты и post-20 профиль пока не сведены. [Конфликт правил роста](help-skill-levels.md) сохраняется.
4. Каталожная база 529–881, effectiveness 131% и shotgun 70% конфликтуют с [ранее проверенными SS14 фактами](carino-combat-formulas.md): 498–831, 123%, 80%. Это две версии свидетельств; ни одну нельзя выбирать по совпадению с панелью.
5. Skill context описывает заявленную базу/поддержки. Он не подтверждает включённость, Tangle inheritance, Lucky, shotgun topology, цель или panel inclusion; не накладывать поддержку повторно поверх panel hit/DPS.

Следующий безопасный шаг — byte-level binder каталожного профиля с exact-ID/hash fixtures и отдельное правило signed Tangle-строки. Числовой resolver для текущего персонажа остаётся заблокирован version/effective-level gates. Действующий DPS не изменён.
