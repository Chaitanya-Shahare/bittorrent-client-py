# bencode.py
#
# Minimal bencode decoder for BitTorrent.
# - Works on bytes, not str
# - Returns:
#     int           for integers
#     bytes         for strings
#     list          for lists
#     dict[bytes,*] for dictionaries
#
# Usage:
#     from bencode import decode, encode
#     obj = decode(b"4:spam")
#     bencode = encode(obj)

class BencodeError(Exception):
    """Generic bencode parsing error."""
    pass


class BencodeDecoder:
    def __init__(self, data: bytes):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("BencodeDecoder expects bytes or bytearray")
        self.data = data
        self.i = 0  # current cursor position

    def decode(self):
        """Decode entire input, ensure no extra trailing data."""
        value = self._parse_value()
        if self.i != len(self.data):
            raise BencodeError(
                f"Extra data after valid bencode: {len(self.data) - self.i} bytes"
            )
        return value

    # ---------- core dispatch ----------

    def _parse_value(self):
        if self.i >= len(self.data):
            raise BencodeError("Unexpected end of data while parsing value")

        c = self.data[self.i:self.i+1]  # single-byte slice
        if c == b"i":
            return self._parse_int()
        elif c == b"l":
            return self._parse_list()
        elif c == b"d":
            return self._parse_dict()
        elif b"0" <= c <= b"9":
            return self._parse_bytestring()
        else:
            raise BencodeError(f"Invalid bencode prefix byte {c!r} at position {self.i}")

    # ---------- integer: i<digits>e ----------

    def _parse_int(self):
        # expect 'i'
        if self.data[self.i:self.i+1] != b"i":
            raise BencodeError(f"Expected 'i' at start of int, got {self.data[self.i:self.i+1]!r}")
        self.i += 1  # skip 'i'

        # find 'e'
        end = self.data.find(b"e", self.i)
        if end == -1:
            raise BencodeError("Missing 'e' terminator for integer")

        int_bytes = self.data[self.i:end]
        if not int_bytes:
            raise BencodeError("Empty integer")

        # validation: no leading zeros except "0", and "-0" is invalid
        if int_bytes == b"-0":
            raise BencodeError("Invalid integer '-0'")
        if int_bytes[0:1] == b"0" and len(int_bytes) > 1:
            raise BencodeError(f"Leading zeros not allowed in integer: {int_bytes!r}")
        if int_bytes[0:1] == b"-" and (len(int_bytes) == 1 or int_bytes[1:2] == b"0"):
            # "-0", "-01", etc.
            raise BencodeError(f"Invalid negative integer: {int_bytes!r}")

        try:
            value = int(int_bytes.decode("ascii"))
        except ValueError as e:
            raise BencodeError(f"Invalid integer digits: {int_bytes!r}") from e

        self.i = end + 1  # move past 'e'
        return value

    # ---------- bytestring: <len>:<data> ----------

    def _parse_bytestring(self):
        # read length string until ':'
        colon = self.data.find(b":", self.i)
        if colon == -1:
            raise BencodeError("Missing ':' in bytestring length")

        len_bytes = self.data[self.i:colon]
        if not len_bytes:
            raise BencodeError("Empty length for bytestring")

        # length must be all digits (remember: iterating bytes -> ints in Py3)
        if not all(ord("0") <= ch <= ord("9") for ch in len_bytes):
            raise BencodeError(f"Non-digit in bytestring length: {len_bytes!r}")

        # leading zeros only allowed if length is "0"
        if len_bytes[0:1] == b"0" and len(len_bytes) > 1:
            raise BencodeError(f"Leading zeros not allowed in bytestring length: {len_bytes!r}")

        length = int(len_bytes.decode("ascii"))

        start = colon + 1
        end = start + length
        if end > len(self.data):
            raise BencodeError("Bytestring length exceeds available data")

        value = self.data[start:end]
        self.i = end
        return value

    # ---------- list: l<value>...e ----------

    def _parse_list(self):
        if self.data[self.i:self.i+1] != b"l":
            raise BencodeError("Expected 'l' at start of list")
        self.i += 1  # skip 'l'

        result = []
        while True:
            if self.i >= len(self.data):
                raise BencodeError("Unexpected end of data inside list")
            if self.data[self.i:self.i+1] == b"e":
                self.i += 1  # skip 'e'
                break
            result.append(self._parse_value())
        return result

    # ---------- dict: d<key><value>...e ----------

    def _parse_dict(self):
        if self.data[self.i:self.i+1] != b"d":
            raise BencodeError("Expected 'd' at start of dict")
        self.i += 1  # skip 'd'

        result = {}
        while True:
            if self.i >= len(self.data):
                raise BencodeError("Unexpected end of data inside dict")
            if self.data[self.i:self.i+1] == b"e":
                self.i += 1  # skip 'e'
                break

            # keys must be byte strings per spec
            key = self._parse_bytestring()
            value = self._parse_value()
            result[key] = value

        return result


def decode(data: bytes):
    """Convenience top-level API: decode bencoded bytes into Python objects."""
    return BencodeDecoder(data).decode()

def encode(obj) -> bytes:
    """
    Encode Python objects into bencode format.

    Supports: int, bytes, list, dict
    """
    if isinstance(obj, int):
        # Integer: i<number>e
        return b"i" + str(obj).encode('ascii') + b"e"

    elif isinstance(obj, bytes):
        # Bytestring: <length>:<data>
        return str(len(obj)).encode('ascii') + b":" + obj

    elif isinstance(obj, list):
        # List: l<items>e
        result = b"l"
        for item in obj:
            result += encode(item)
        result += b"e"
        return result

    elif isinstance(obj, dict):
        # Dictionary: d<key><value>...e
        # IMPORTANT: keys must be sorted!
        result = b"d"
        for key in sorted(obj.keys()):
            result += encode(key)
            result += encode(obj[key])
        result += b"e"
        return result

    else:
        raise TypeError(f"Cannot bencode object of type {type(obj)}")



# Optional: quick manual tests if run as a script
if __name__ == "__main__":
    def check(encoded, expected):
        try:
            out = decode(encoded)
            ok = out == expected
            print(f"{encoded!r} -> {out!r} | expected {expected!r} | {'OK' if ok else 'FAIL'}")
        except Exception as e:
            print(f"{encoded!r} -> ERROR {e!r}")

    print("=== basic tests ===")
    # integers
    check(b"i0e", 0)
    check(b"i42e", 42)
    check(b"i-7e", -7)

    # strings
    check(b"0:", b"")
    check(b"4:spam", b"spam")

    # lists
    check(b"l4:spam4:eggse", [b"spam", b"eggs"])
    check(b"li1ei2ei3ee", [1, 2, 3])

    # dicts
    check(b"d3:cow3:moo4:spam4:eggse", {b"cow": b"moo", b"spam": b"eggs"})
    check(b"d4:spaml1:a1:bee", {b"spam": [b"a", b"b"]})

    # complex
    check(
        b"d3:bar4:spam3:fooi42ee",
        {b"bar": b"spam", b"foo": 42},
    )

    print("\n=== encode/decode round-trip tests ===")
    # Test that encode(decode(x)) == x
    test_cases = [
        b"i42e",
        b"4:spam",
        b"li1ei2ei3ee",
        b"d3:bar4:spam3:fooi42ee",
    ]
    for test in test_cases:
        decoded = decode(test)
        encoded = encode(decoded)
        match = encoded == test
        print(f"{test!r} -> decode -> encode -> {encoded!r} | {'OK' if match else 'FAIL'}")

