"""Source-bound Chromatic Shot profile from one saved TLIDB page (offline, pure, diagnostic; tasks 0233, 0253).

profile(data, expected_sha256, *, source_url) checks the declared URL (exactly the canonical page URL, a caller
declaration and not an origin proof), the byte bound, the digest and strict UTF-8. It then builds a bounded element
tree with the stdlib HTMLParser: comments produce no elements and inert subtrees cannot supply selected roles;
every element keeps its exact character offsets, and node count and depth are limited while parsing.

Selection is structural, never a global text match:
  - identity: exactly one real <h1> "Chromatic Shot", and exactly one Info card (a card whose card-header is "Info")
    whose body reads "id: 7007";
  - header: the single skill card (classes card, ui_item, popupItem), its own item_ver, level, label/value pairs and
    its own Details text (the explicitMod beginning "Chromatic Shot:");
  - progression: the single card whose header reads "Progression /N", and the single table inside that same card,
    with headings exactly "level" and "Descript". Each body row is a <tr> of two cells: the level, then an optional
    damage_effective div followed by the des div, and nothing else.

Every number is kept as its exact ASCII lexeme; character references inside a value are refused. A row's effectiveness
and shotgun falloff come only from that row; a missing value stays null with an explicit gap and is never filled from
the header or another row. Row spans are the selected <tr> elements' own offsets. Nothing is scaled, interpolated,
extrapolated or fitted; the cast speed is the displayed value (casts per second, precision unknown). The result is
catalog text only: runtimeVersion is unknown, effectiveLevel null and arithmeticReady false. Any changed, duplicated
or ambiguous structure is a ProfileError with a fixed code that never echoes input.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser

FORMAT = 'tli-tlidb-skill-profile-v0'
VERSION = '0.2.2'
SKILL = ('Chromatic Shot', 7007)
CANONICAL_URL = 'https://tlidb.com/en/Chromatic_Shot'
LIMITS = {'maxBytes': 4 * 1024 * 1024, 'maxNodes': 20000, 'maxDepth': 128, 'maxRows': 64, 'maxRowChars': 8192,
          'maxTagChars': 4096, 'maxTextChars': 256}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
SKIP = {'script', 'style'}
INERT_TAGS = {'script', 'style', 'template', 'noscript', 'textarea', 'title'}
SHA256 = re.compile(r'[0-9a-f]{64}')
INT = r'([0-9]{1,9})'
PERCENT = r'([0-9]{1,4}(?:\.[0-9]{1,4})?)'
BASE = re.compile(r'Deals <span class="text-mod">' + INT + '-' + INT + r'</span> Spell Physical Damage')
SHOTGUN = re.compile(r'falloff coefficient is ' + PERCENT + '%')
INTRINSIC = re.compile(r'This skill fires <span class="text-mod">' + INT + r'</span> Projectile in its base state\.')
# Inert or non-element markup: comments, declarations, processing instructions and raw-text containers. None of it may
# appear inside a value-bearing region, so numeric roles can only come from ordinary rendered markup (task 0316).
INERT = re.compile(r'<!|<\?|<(?:script|style|template|noscript|textarea|title)\b', re.I)
VERSION_LABEL = re.compile(r'[A-Za-z0-9]{1,32}')
MANA_COST = re.compile(r'[0-9]{1,6}')
HEADER_LEVEL = re.compile(r'[0-9]{1,3}')
QUANTITY = re.compile(r'Projectile Quantity of this skill <span class="text-mod">(\+[0-9]{1,4})</span>')


class ProfileError(ValueError):
    """The input is outside the supported shape; the message is the fixed code and never echoes page text."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class _Node:
    """One parsed element: tag, attributes, exact character offsets (start, inner start, end) and children."""

    __slots__ = ('tag', 'attrs', 'start', 'inner', 'end', 'children', 'parent')

    def __init__(self, tag, attrs, start, inner, parent):
        self.tag, self.attrs, self.start, self.inner, self.parent = tag, attrs, start, inner, parent
        self.end, self.children = None, []

    def classes(self):
        return set((self.attrs.get('class') or '').split())


class _Tree(HTMLParser):
    """A bounded element tree with exact character offsets; comments, scripts and styles produce no elements."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text, self.lines = text, [0]
        for index, char in enumerate(text):
            if char == '\n':
                self.lines.append(index + 1)
        self.root = _Node('#root', {}, 0, 0, None)
        self.root.end = len(text)
        self.stack, self.nodes, self.skip = [self.root], 0, 0

    def _offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if self.skip:
            return
        self.nodes += 1
        if self.nodes > LIMITS['maxNodes']:
            raise ProfileError('too_many_nodes')
        start = self._offset()
        raw = self.get_starttag_text() or ''
        if tag in INERT_TAGS and raw.endswith('/>'):
            raise ProfileError('html_unsupported_rawtext')
        names = [key for key, _ in attrs]                 # HTMLParser lowercases names, so case variants collide too
        if len(set(names)) != len(names):
            raise ProfileError('duplicate_attribute')     # refused before the dict, never last-wins
        node = _Node(tag, {key: value for key, value in attrs}, start, start + len(raw), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag in VOID or raw.endswith('/>'):
            node.end = node.inner
            return
        if tag in SKIP:
            self.skip = 1
            node.end = None
        self.stack.append(node)
        if len(self.stack) > LIMITS['maxDepth']:
            raise ProfileError('too_deep')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if not self.skip and self.stack[-1].tag == tag and self.stack[-1].end is None and tag not in VOID:
            node = self.stack.pop()
            node.end = node.inner

    def handle_endtag(self, tag):
        start = self._offset()
        close = self.text.find('>', start)
        end = len(self.text) if close < 0 else close + 1
        if self.skip:
            if tag in SKIP and self.stack[-1].tag == tag:
                self.skip = 0
                self.stack.pop().end = end
            return
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                while len(self.stack) > depth:
                    node = self.stack.pop()
                    node.end = end if node.tag == tag else start          # implicitly closed elements end here
                return
        # a stray end tag with no open element is ignored

    def finish(self):
        self.close()
        while len(self.stack) > 1:
            self.stack.pop().end = len(self.text)


def _prescan(text):
    """A linear bound check BEFORE HTMLParser, whose scan of unterminated tags is quadratic.

    Every tag-like '<' (followed by a letter, '/' or '!') must close with '>' within maxTagChars and contain no other
    '<'; comments must close with '-->'; script and style contents must reach their own end tag. The tag count is
    bounded by maxNodes. Each check advances the position, so the whole scan is linear in the input.
    """
    lower, position, tags = text.lower(), 0, 0
    while True:
        start = text.find('<', position)
        if start < 0:
            return
        if text.startswith('<!--', start):
            close = text.find('-->', start + 4)
            if close < 0:
                raise ProfileError('html_unterminated')
            position = close + 3
            continue
        following = text[start + 1:start + 2]
        if not (following.isascii() and (following.isalpha() or following in '/!?')) or not following:
            position = start + 1
            continue
        close = text.find('>', start + 1, start + 1 + LIMITS['maxTagChars'])
        if close < 0:
            raise ProfileError('tag_too_long')
        if '<' in text[start + 1:close]:
            raise ProfileError('html_malformed_tag')
        tags += 1
        if tags > 2 * LIMITS['maxNodes']:
            raise ProfileError('too_many_nodes')
        name = re.match(r'[a-z0-9]*', lower[start + 1:close]).group(0)
        position = close + 1
        if name in SKIP and not text[close - 1:close + 1].startswith('/'):
            end = lower.find('</' + name, position)
            if end < 0:
                raise ProfileError('html_unterminated')
            position = end


def _walk(node):
    stack = list(reversed(node.children))
    while stack:
        current = stack.pop()
        if current.tag in INERT_TAGS:
            continue
        yield current
        stack.extend(reversed(current.children))


def _text(tree, node, code='value_markup'):
    """The plain text of a scalar element. Any markup inside it (a child tag, comment, declaration, processing
    instruction or script) or a character reference is refused with `code`, so a scalar role can never be sourced
    from ignored markup."""
    if node.end is None or node.end - node.inner > LIMITS['maxTextChars'] + 32:
        raise ProfileError(code)                          # bounded by offsets before any slice or scan
    raw = tree.text[node.inner:_closing_start(tree, node)]                 # inner text, without the own end tag
    if '&' in raw or '<' in raw:
        raise ProfileError(code)
    return raw.strip()


def _inner(tree, node):
    return tree.text[node.inner:node.end]


def _closing_start(tree, node):
    """Character offset of an element's own end tag (its raw inner end)."""
    if node.end is None:
        return node.inner
    return tree.text.rfind('</', node.inner, node.end) if node.end > node.inner else node.inner


def _elements(node):
    return [child for child in node.children]


def _fraction(percent):
    sign, digits, exponent = Decimal(percent).as_tuple()
    return format(Decimal((sign, digits, exponent - 2)), 'f')


def _base(description, code):
    found = BASE.findall(description)
    if len(found) != 1:
        raise ProfileError(code)
    low, high = found[0]
    if int(low) > int(high):
        raise ProfileError('base_range_invalid')
    return {'min': low, 'max': high}


def _at_most_one(pattern, text, code):
    found = pattern.findall(text)
    if len(found) > 1:
        raise ProfileError(code)
    return found[0] if found else None


def _byte_offsets(text, offsets):
    """Exact UTF-8 byte offsets of increasing character offsets, encoding each gap once."""
    result, last_char, last_byte = {}, 0, 0
    for offset in sorted(set(offsets)):
        last_byte += len(text[last_char:offset].encode('utf-8'))
        last_char = offset
        result[offset] = last_byte
    return result


def _only_children(tree, node, code):
    """Refuse non-whitespace text (including comments) before, between or after a role container's element children."""
    cursor = node.inner
    for child in node.children:
        if tree.text[cursor:child.start].strip():
            raise ProfileError(code)
        cursor = child.end if child.end is not None else child.inner
    if tree.text[cursor:_closing_start(tree, node)].strip():
        raise ProfileError(code)


def _card_body_text(tree, card, header):
    """For a card whose own card-header child reads `header`, the card element."""
    heads = [c for c in card.children if c.tag == 'div' and 'card-header' in c.classes()]
    return len(heads) == 1 and _safe_text(tree, heads[0]) == header


def profile(data, expected_sha256, *, source_url):
    """The diagnostic profile of one saved page; see the module docstring."""
    if type(source_url) is not str or source_url != CANONICAL_URL:
        raise ProfileError('bad_source_url')
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ProfileError('bad_expected_digest')
    if not isinstance(data, bytes):
        raise ProfileError('not_bytes')
    if len(data) > LIMITS['maxBytes']:
        raise ProfileError('too_large')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ProfileError('digest_mismatch')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise ProfileError('not_utf8') from None
    _prescan(text)
    tree = _Tree(text)
    try:
        tree.feed(text)
        tree.finish()
    except ProfileError:
        raise
    except (AssertionError, ValueError, IndexError):
        raise ProfileError('html_unparseable') from None
    elements = list(_walk(tree.root))
    titles = [n for n in elements if n.tag == 'h1' and _text(tree, n, 'identity_mismatch') == SKILL[0]]
    if len(titles) != 1:
        raise ProfileError('identity_mismatch')
    infos = [n for n in elements if n.tag == 'div' and 'card' in n.classes() and _card_body_text(tree, n, 'Info')]
    if len(infos) != 1:
        raise ProfileError('identity_mismatch')
    ids = [n for n in _walk(infos[0]) if n.tag == 'div' and not n.attrs and _safe_text(tree, n).startswith('id:')]
    if (len(ids) != 1 or not re.fullmatch(r'id: ' + INT, _text(tree, ids[0], 'identity_mismatch'))
            or int(_text(tree, ids[0], 'identity_mismatch')[4:]) != SKILL[1]):
        raise ProfileError('identity_mismatch')
    cards = [n for n in elements if n.tag == 'div' and {'card', 'ui_item', 'popupItem'} <= n.classes()]
    if len(cards) != 1:
        raise ProfileError('header_markup_changed')
    card = cards[0]
    inside = list(_walk(card))
    versions = [n for n in inside if n.tag == 'div' and 'item_ver' in n.classes()]
    levels = [n for n in inside if n.tag == 'div' and 'level' in n.classes()]
    attributes = {}
    for pair in (n for n in inside if n.tag == 'div' and n.classes() == {'d-flex', 'justify-content-center'}):
        parts = [c for c in pair.children if c.tag == 'div']
        if len(parts) != 2 or 'ps-2' not in parts[1].classes():
            raise ProfileError('header_markup_changed')
        label, value = _text(tree, parts[0], 'header_markup_changed'), _text(tree, parts[1], 'header_markup_changed')
        if label in attributes:
            raise ProfileError('header_markup_changed')
        attributes[label] = value
    details = [n for n in inside if n.tag == 'div' and 'explicitMod' in n.classes()
               and _inner(tree, n).startswith('Chromatic Shot:<br/>')]
    if len(details) != 1:
        raise ProfileError('header_markup_changed')
    detail_text = _inner(tree, details[0])
    if INERT.search(detail_text) or '&' in detail_text:
        raise ProfileError('header_markup_changed')
    effect = attributes.get('Effectiveness of added damage')
    effect_match = re.fullmatch(PERCENT + '%', effect) if effect is not None else None
    cast = attributes.get('Cast Speed')
    if (effect is not None and effect_match is None) or (
            cast is not None and not re.fullmatch(r'[0-9]{1,4}(?:\.[0-9]{1,4})?', cast)):
        raise ProfileError('header_markup_changed')
    mana = attributes.get('Mana Cost')
    if mana is not None and not MANA_COST.fullmatch(mana):
        raise ProfileError('header_markup_changed')
    header = {'manaCost': mana,
              'castSpeed': ({'display': cast, 'meaning': 'displayed_casts_per_second', 'precision': 'unknown'}
                            if cast is not None else None),
              'effectiveness': ({'display': effect, 'percent': effect_match.group(1),
                                 'fraction': _fraction(effect_match.group(1))} if effect_match else None),
              'baseDamage': _base(detail_text, 'header_markup_changed'),
              'shotgunFalloffPercent': _at_most_one(SHOTGUN, detail_text, 'header_markup_changed')}
    progression = []
    for node in elements:
        if node.tag == 'div' and 'card' in node.classes():
            heads = [c for c in node.children if c.tag == 'div' and 'card-header' in c.classes()]
            if len(heads) == 1 and re.fullmatch(r'Progression /[0-9]{1,4}', _safe_text(tree, heads[0])):
                progression.append((node, int(_text(tree, heads[0], 'progression_markup_changed').split('/')[1])))
    if len(progression) != 1:
        raise ProfileError('progression_markup_changed')
    container, total = progression[0]
    if total < 1:
        raise ProfileError('row_count_invalid')
    if total > LIMITS['maxRows']:                     # a technical bound, separate from the 40 reference rows
        raise ProfileError('too_many_rows')
    tables = [n for n in _walk(container) if n.tag == 'table']
    if len(tables) != 1:
        raise ProfileError('progression_markup_changed')
    table = tables[0]
    sections = [c for c in table.children]
    if [c.tag for c in sections] != ['thead', 'tbody']:
        raise ProfileError('progression_markup_changed')
    head_cells = [n for n in _walk(sections[0]) if n.tag == 'th']
    if [_text(tree, n, 'progression_markup_changed') for n in head_cells] != ['level', 'Descript']:
        raise ProfileError('progression_markup_changed')
    body = sections[1]
    if len(body.children) > LIMITS['maxRows']:
        raise ProfileError('too_many_rows')
    rows, gaps, spans = [], [], []
    previous = body.inner
    for tr in body.children:
        if tr.tag != 'tr' or text[previous:tr.start].strip():
            raise ProfileError('row_markup_changed')
        previous = tr.end
        if tr.end is None or tr.end - tr.start > LIMITS['maxRowChars']:
            raise ProfileError('row_too_long')
        _only_children(tree, tr, 'row_markup_changed')
        cells = tr.children
        if [c.tag for c in cells] != ['td', 'td'] or not re.fullmatch(INT, _text(tree, cells[0], 'row_markup_changed')):
            raise ProfileError('row_markup_changed')
        level = int(_text(tree, cells[0], 'row_markup_changed'))
        _only_children(tree, cells[1], 'row_markup_changed')
        divs = cells[1].children
        sources = [d.attrs.get('data-source') for d in divs]
        if any(d.tag != 'div' for d in divs) or sources not in (['damage_effective', 'des'], ['des']):
            raise ProfileError('row_markup_changed')
        effectiveness = None
        if sources[0] == 'damage_effective':
            match = re.fullmatch(r'Effectiveness of added damage ' + PERCENT + '%', _safe_text(tree, divs[0]))
            if match is None or '&' in _inner(tree, divs[0]):
                raise ProfileError('row_markup_changed')
            effectiveness = match.group(1)
        description = _inner(tree, divs[-1])
        if '&' in description or INERT.search(description):
            raise ProfileError('row_markup_changed')
        shotgun = _at_most_one(SHOTGUN, description, 'row_markup_changed')
        entry = {'level': level, 'source': {'charSpan': [tr.start, tr.end]},
                 'baseDamage': _base(description, 'row_markup_changed'),
                 'effectiveness': {'percent': effectiveness, 'fraction': _fraction(effectiveness)} if effectiveness else None,
                 'shotgunFalloffPercent': shotgun,
                 'projectiles': {'intrinsicBase': _at_most_one(INTRINSIC, description, 'row_markup_changed'),
                                 'quantityModifier': _at_most_one(QUANTITY, description, 'row_markup_changed'),
                                 'totalActual': 'unknown'}}
        spans += [tr.start, tr.end]
        if effectiveness is None:
            gaps.append({'level': level, 'field': 'effectiveness', 'reason': 'not_in_own_row'})
        if shotgun is None:
            gaps.append({'level': level, 'field': 'shotgunFalloffPercent', 'reason': 'not_in_own_row'})
        rows.append(entry)
    if text[previous:_closing_start(tree, body)].strip():
        raise ProfileError('row_markup_changed')
    if not rows:
        raise ProfileError('row_count_invalid')
    if [entry['level'] for entry in rows] != list(range(1, len(rows) + 1)):
        raise ProfileError('levels_not_unique_contiguous')
    if len(rows) != total:
        raise ProfileError('row_count_mismatch')
    version_label = header_level = None              # missing or ambiguous (more than one) stays unknown
    if len(versions) == 1:
        version_label = _text(tree, versions[0], 'header_markup_changed')
        if not VERSION_LABEL.fullmatch(version_label):
            raise ProfileError('header_markup_changed')
    if len(levels) == 1:
        level_text = _text(tree, levels[0], 'header_markup_changed')
        if not HEADER_LEVEL.fullmatch(level_text):
            raise ProfileError('header_markup_changed')
        header_level = int(level_text)
    byte_at = _byte_offsets(text, spans)
    for entry in rows:
        start, end = entry['source']['charSpan']
        entry['source']['byteSpan'] = [byte_at[start], byte_at[end]]
    result = {'format': FORMAT, 'version': VERSION,
              'source': {'url': CANONICAL_URL, 'urlMeaning': 'caller_declared_not_origin_verified', 'sha256': digest,
                         'bytes': len(data)},
              'identity': {'name': SKILL[0], 'infoId': SKILL[1],
                           'itemVersionLabel': version_label, 'headerLevel': header_level},
              'header': header, 'rows': rows, 'gaps': gaps,
              'counts': {'rows': len(rows), 'rowsWithEffectiveness': sum(1 for r in rows if r['effectiveness']),
                         'rowsWithShotgun': sum(1 for r in rows if r['shotgunFalloffPercent'] is not None)},
              'runtimeVersion': 'unknown', 'effectiveLevel': None, 'arithmeticReady': False,
              'applicability': 'catalog_page_text_only_not_runtime_data'}
    return json.loads(json.dumps(result))


def _safe_text(tree, node):
    """Text used only for selection: an entity makes it unselectable rather than raising."""
    try:
        return _text(tree, node)
    except ProfileError:
        return ''
