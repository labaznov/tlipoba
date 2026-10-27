"""Plan source-shaped candidate header reads without accessing a process."""

from damage_lab.nativeanchor import Anchor


class Header:
    """Describe a bounded observation without asserting a native owner or cache."""

    def __init__(self, base, span, offset, instruction, guard, body, limit):
        self._anchor = Anchor(base, span, offset, instruction, limit)
        if (type(body) is not bytes or not 1 <= len(body) <= 1024
                or type(guard) is not int or not 0 <= guard <= span - len(body)):
            raise ValueError("Native cache guard source interval is invalid")
        self._guard = base + guard
        self._body = body
        self._limit = limit

    def code(self):
        return self._anchor.code()

    def guard(self):
        return {"address": self._guard, "size": len(self._body)}

    def slot(self, getter, body):
        request = self._anchor.slot(getter)
        if type(body) is not bytes or body != self._body:
            raise ValueError("Native cache guard does not match the source bytes")
        return request

    def header(self, getter, body, word):
        self.slot(getter, body)
        self._anchor.observation(getter, word)
        candidate = int.from_bytes(word, "little")
        if not 0 < candidate <= self._limit - 0x138:
            raise ValueError("Native cache candidate header is outside the address domain")
        return {"address": candidate + 0x128, "size": 16}

    def observation(self, getter, body, word, data):
        self.header(getter, body, word)
        if type(data) is not bytes or len(data) != 16:
            raise ValueError("Native cache header requires exactly sixteen immutable bytes")
        anchor = self._anchor.observation(getter, word)
        return {"format": "tli-native-cache-header-observation-v1", "anchor": anchor,
                "stored_function_source_match": True, "header_hex": data.hex(),
                "bucket_candidate_hex": hex(int.from_bytes(data[:8], "little")),
                "count_candidate": int.from_bytes(data[12:16], "little"),
                "reserved_hex": data[8:12].hex(),
                "claims": {**anchor["claims"], "cache_layout": False, "model_readiness": False},
                "limitations": ["Source-shaped candidates have unverified runtime owner and field semantics",
                                "Stored-function code equality does not show that the candidate uses that function",
                                "No bucket or node is followed and no DPS input is derived"]}
