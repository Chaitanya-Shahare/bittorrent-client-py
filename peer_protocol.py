# peer_protocol.py
#
# BitTorrent peer wire protocol implementation.
#
# Key concepts:
# - Handshake: 68 bytes to establish connection
# - Messages: <length><id><payload> format
# - Message types: choke, unchoke, interested, have, bitfield, request, piece, etc.

import struct


def create_handshake(info_hash: bytes, peer_id: bytes) -> bytes:
    """
    Create handshake message.

    Format (68 bytes total):
    - 1 byte: pstrlen (19)
    - 19 bytes: pstr ("BitTorrent protocol")
    - 8 bytes: reserved (all zeros)
    - 20 bytes: info_hash
    - 20 bytes: peer_id
    """
    pstr = b"BitTorrent protocol"
    pstrlen = bytes([len(pstr)])  # 19
    reserved = b"\x00" * 8
    return pstrlen + pstr + reserved + info_hash + peer_id


def parse_handshake(data: bytes) -> dict:
    """
    Parse handshake response.
    Returns {'info_hash': bytes, 'peer_id': bytes}
    """
    if len(data) < 68:
        raise ValueError(f"Handshake too short: {len(data)} bytes")

    pstrlen = data[0]
    if pstrlen != 19:
        raise ValueError(f"Invalid pstrlen: {pstrlen}")

    pstr = data[1:20]
    if pstr != b"BitTorrent protocol":
        raise ValueError(f"Invalid protocol: {pstr}")

    info_hash = data[28:48]
    peer_id = data[48:68]

    return {'info_hash': info_hash, 'peer_id': peer_id}


def create_message(message_id: int, payload: bytes = b"") -> bytes:
    """
    Create a message.

    Format:
    - 4 bytes: length (big-endian int) = 1 + len(payload)
    - 1 byte: message ID
    - N bytes: payload
    """
    length = 1 + len(payload)
    return struct.pack(">I", length) + bytes([message_id]) + payload


def parse_message(data: bytes) -> tuple:
    """
    Parse message from data.

    Returns (message_id, payload, bytes_consumed)
    Returns (None, None, 0) if not enough data yet
    Returns (None, b"", 4) for keep-alive message
    """
    if len(data) < 4:
        return None, None, 0

    length = struct.unpack(">I", data[:4])[0]

    if length == 0:
        # Keep-alive message
        return None, b"", 4

    if len(data) < 4 + length:
        # Not enough data yet
        return None, None, 0

    message_id = data[4]
    payload = data[5:4+length]

    return message_id, payload, 4 + length


def create_request(piece_index: int, begin: int, length: int) -> bytes:
    """
    Create a 'request' message (ID=6).

    Payload: <index><begin><length> (3 x 4-byte big-endian ints)

    Args:
    - piece_index: Which piece we're requesting
    - begin: Byte offset within the piece
    - length: Number of bytes to request (usually 16KB)
    """
    payload = struct.pack(">III", piece_index, begin, length)
    return create_message(6, payload)


def parse_piece_message(payload: bytes) -> dict:
    """
    Parse 'piece' message payload (ID=7).

    Format:
    - 4 bytes: piece index (big-endian int)
    - 4 bytes: begin offset (big-endian int)
    - N bytes: block data
    """
    index, begin = struct.unpack(">II", payload[:8])
    block = payload[8:]
    return {'index': index, 'begin': begin, 'block': block}


def parse_bitfield(payload: bytes) -> list:
    """
    Parse bitfield message payload (ID=5).

    Returns list of piece indices that peer has.
    Each byte represents 8 pieces (MSB first).
    """
    pieces = []
    for byte_index, byte in enumerate(payload):
        for bit_index in range(8):
            if byte & (1 << (7 - bit_index)):
                piece_index = byte_index * 8 + bit_index
                pieces.append(piece_index)
    return pieces


# Message ID constants
MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7
MSG_CANCEL = 8


if __name__ == "__main__":
    # Test handshake
    info_hash = b"a" * 20
    peer_id = b"b" * 20

    handshake = create_handshake(info_hash, peer_id)
    print(f"Handshake length: {len(handshake)} bytes")

    parsed = parse_handshake(handshake)
    print(f"Parsed info_hash: {parsed['info_hash']}")
    print(f"Parsed peer_id: {parsed['peer_id']}")

    # Test messages
    interested = create_message(MSG_INTERESTED)
    print(f"\nInterested message: {interested.hex()}")

    request = create_request(0, 0, 16384)
    print(f"Request message length: {len(request)} bytes")

    msg_id, payload, consumed = parse_message(request)
    print(f"Parsed request: id={msg_id}, payload_len={len(payload)}, consumed={consumed}")
