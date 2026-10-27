"""Plan data-only reads from an admitted x64 RIP-load/return source profile.

The caller supplies module metadata and an address-domain bound. Neither those
inputs nor an eight-byte code match prove module, manager or actor identity.
This module performs no process access or pointer following.
"""


class Anchor:
    """Describe bounded reads for one source-shaped singleton candidate."""

    def __init__(self, base, span, offset, instruction, limit):
        if (type(instruction) is not bytes or len(instruction) != 8
                or instruction[:3] != b"\x48\x8b\x05" or instruction[-1:] != b"\xc3"):
            raise ValueError("Native anchor source requires an eight-byte RIP load and return")
        if (any(type(value) is not int for value in (base, span, offset, limit))
                or not 0 < base < limit <= 2 ** 64 or not 0 < span <= limit - base
                or not 0 <= offset <= span - 8):
            raise ValueError("Native anchor module bounds are invalid")
        target = offset + 7 + int.from_bytes(instruction[3:7], "little", signed=True)
        if not 0 <= target <= span - 8:
            raise ValueError("Native anchor module bounds are invalid")
        self._base = base
        self._offset = offset
        self._target = target
        self._instruction = instruction
        self._limit = limit

    def code(self):
        return {"address": self._base + self._offset, "size": 8}

    def slot(self, observed):
        self._match(observed)
        return {"address": self._base + self._target, "size": 8}

    def observation(self, observed, data):
        self._match(observed)
        if type(data) is not bytes or len(data) != 8:
            raise ValueError("Native anchor field requires exactly eight immutable bytes")
        value = int.from_bytes(data, "little")
        return {"format": "tli-native-anchor-observation-v1", "raw_hex": data.hex(),
                "value_hex": hex(value),
                "state": "zero" if value == 0 else "in_domain" if value < self._limit else "outside_domain",
                "code_match": True,
                "claims": {"module_identity": False, "manager_identity": False, "actor_identity": False,
                           "selected_build": False, "currentness": False, "atomicity": False, "dps": False}}

    def _match(self, observed):
        if type(observed) is not bytes or observed != self._instruction:
            raise ValueError("Native anchor getter does not match the source instruction")
