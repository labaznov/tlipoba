# Кандидаты прибавок к уровню

`damage_lab.levelcandidates` — чистый consumer диагностического артефакта helper.
Он проверяет вход и сохраняет кандидатов, но не выбирает политику уровней, не
складывает прибавки и не создаёт effective level или DPS.

## API и версии

```python
project(document, source_sha256) -> dict
summary(canonical) -> dict
```

`project` принимает `tli-effective-level-candidates-v0`, версии `0.3.1` и `0.4.0`.
Результат имеет `format: tli-effective-level-candidates-canonical-v1` и
сохраняет версию producer; canonical format описывает схему
проекции. `summary` заново проверяет именно эту проекцию. Обе функции возвращают
отделённое дерево из известных полей и не меняют вход. Синтетическая фабрика
`tests/test_levelcandidates.py:document()` демонстрирует полный контракт.

Неверные типы, версии, пути, значения или противоречия дают фиксированный
`ValueError`, без включения входного текста в сообщение. Чтения файлов, каталогов,
игры, журналов или сети нет. Совпадение SHA проверяет лишь переданную аннотацию:
`source.binding` остаётся `caller_supplied_document_only`; проверка байтов —
обязанность отдельного reader.

## Схема

Все имена известных полей нормализованы в `snake_case`:

```text
format, version, source{sha256,binding},
arithmetic_ready:false, runtime_verified:false, identity_verified:false,
import_complete:false, effective_level:null, uniquely_derivable:false,
target{skill_id,status,path,gem_level,catalog,skill_item_level},
candidates[], domains{}, gaps[{domain,path,reason}], limitations[]
```

Обязательны все 13 доменов: `gear`, `talents`, `divinity_slates`, `pactspirits`,
`ethereal_prism`, `supports`, `hero_traits`, `hero_memories`, `sp_talent_tree`,
`other_wear_items`, `jewel_items`, `talent_jewelry_data_list`,
`hero_character_items`. Неполный документ не дополняется пустыми доменами.
Счётчики `observed`, `bound`, `bound_level_candidates` и `candidate_coverage`
сохраняют неизвестность. Дополнительные известные поля — `items`, `notables`,
`slates`, `placement_verified`, `catalog_members`, `catalog_level_mentions`, `pairs`.
Счётчик найденных кандидатов сопоставляется со строками; это не полнота персонажа.

Каждый кандидат сохраняет `domain`, `path`, `template`, `binding`, `amount`,
`eligibility` и собственные координаты:

- `gear`: `native_id`, `slot`, точное own-definition binding, `tier`, `tier_id`,
  `tier_bounds{min,max}`; roll — строка `amount.exact` из `DynArgs[0]`
- `talent`: computed binding по position/tier отличается от exact notable binding;
  `rank{rank,max_points,server_point,semantics}` остаётся evidence, а многоточечный
  узел имеет `amount:null` и `rank_scaling_unknown`
- `slate`: установка всегда `listed_in_dressing_blocks_placement_unverified`
- `pactspirit`: `area`, bridge kind и публичный node; даже hashed bridge не
  повышает runtime/identity/полноту

Каталожные литералы и rolls сохраняются лексически, включая конечные нули.
Валидация границ использует Decimal-сравнение, без float-суммирования.
Шаблон целиком соответствует `+# [to ]<Scope> Skill Level`; поддерживаются одно
или два слова установленной грамматики, а не произвольные описания.

`eligibility{scope,scope_tokens,all_tokens_in_skill_tags,skill_category,status}`
пересчитывается только как проверка наличия слов в переданных каталожных tags.
`status` всегда `unverified`: совпадение слов не доказывает правила игры.
При неизвестном каталоге весь object сохраняется, а его boolean/category —
`null`. Это поведение released producer, несмотря на фразу о nullable eligibility
в его документации. `gem_level` — наблюдаемый уровень камня, не effective level;
`skill_item_level` — лишь согласованная статистика counts с `semantics: unknown`.

### Нативные поля конкретного навыка

В `0.4.0` каждый target обязательно содержит `native_level_fields`:

```text
skills_row{join,path,join_field:"Id"},
fields{Level{value,type},SkillItemLevel{value,type}},
level_equals_gem, semantics{Level:"unknown",SkillItemLevel:"unknown"},
arithmetic_ready:false, effective_level:null
```

Producer связывает единственный установленный клиентский экземпляр с единственной
строкой `sections.ServerSource.data.featuresInfo.skills.skills[i]` по точному `Id`.
Идентификатор экземпляра не экспортируется. Эта привязка отличается от server
skillLayout: наличие одного слоя не доказывает другой. Consumer проверяет схему,
путь, типы и согласованность, но не перечитывает строку источника.

Только `exact_instance` допускает путь строки и наблюдаемые поля. Остальные статусы
(`target_unavailable`, `no_instance`, `ambiguous_instance`, `no_skills_row`,
`collection_limit`, `section_<status>`) сохраняют оба поля как `unavailable/null`.
У точно связанной строки отсутствующее/null поле имеет `type: missing`, неверный
тип — `invalid`; они не заменяются нулём. Integer сохраняется в пределах
`-10^20 < n < 10^20`, включая ноль и отрицательные значения: это техническая
граница наблюдения, а не утверждение о допустимом игровом уровне.

`level_equals_gem` пересчитывается только для integer `Level` и известного gem
level, иначе равен `null`. Совпадение значений не доказывает смысл поля и учёт
прибавок. Ни одно из двух полей не становится effective level. Старый `0.3.1`
не получает выдуманных наблюдений; его проекция остаётся прежней.

Bundle принимает только проверенные пары `(0.1.2, 0.3.1)` и `(0.2.0, 0.4.0)`
для `(bundle version, resolver version)`. Версия каждого target должна совпадать
с resolver version всего bundle; descriptor и файл также должны согласоваться.

## Границы и безопасность

Перед проекцией проверяется bounded plain JSON: до 200 000 узлов, глубина до 64,
до 4096 элементов на контейнер и символов на строку/ключ; повторные контейнеры,
циклы, lone surrogates, NaN, Infinity и не-JSON объекты запрещены. Неизвестные
поля после этой проверки удаляются на любой глубине: account/instance IDs,
описания и непрозрачные payload не сохраняются.

Consumer допускает integer IDs и gem levels `1 <= n < 10^20`, остальные counts
`0 <= n < 10^12` (для partition `skill_item_level` — до 4096 включительно).
Координаты массивов — `0..4095`, slot — меньше `10^6`, rank/max_points/area —
меньше `10^4`, pact node — `0..99`. IDs, tags, tiers, каталожные и source paths
имеют отдельную ASCII-грамматику. Decimal-строки содержат до 12 целых и 9 дробных
цифр, без exponent notation. Это ограничения consumer, не доказательство полной
поддержки всех будущих форматов producer.

`collection_limit` сохраняет неизвестность всего домена без его частичных
кандидатов или посторонних gap. Census-only coverage относится к предоставленному
каталогу и не превращается в проверенную игровую применимость. Нет автоматического
применения к панели, rawspell, критам или росту навыка. Политики уровней и пределы
доказательств описаны в [исследовании](research/effective-level-policy.md).
