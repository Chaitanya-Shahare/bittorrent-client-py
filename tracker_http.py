# tracker_http.py
# Communicate with HTTP trackers to get peer lists

import hashlib
import random
import urllib.parse
import urllib.request
from bencode import decode, encode

def calculate_info_hash(info_dict: dict) -> bytes: 
    """
    Calculate the SHA-1 hash of the bencoded info dictionary
    """
    bencoded = encode(info_dict)
    return hashlib.sha1(bencoded).digest()

def generate_peer_id() -> bytes:
    """Generate a random 20-byte peer id"""
    prefix = b"-PY0001-"
    random_part = bytes([random.randint(0, 255) for _ in range(12)])
    return prefix + random_part

def url_encode_bytes(data: bytes) -> str:
    """URL-encode bytes for use in query parameters

    Some bytes in info_hash and peer_id need special encoding.
    Example: a space becomes %20, a null byte becomes %00
    """
    return urllib.parse.quote(data, safe='')

def build_tracker_url(announce_url: str, info_hash: bytes, peer_id: bytes,
                      total_length: int, port: int = 6881) -> str:
    params = {
        'info_hash': url_encode_bytes(info_hash),
        'peer_id': url_encode_bytes(peer_id),
        'port': str(port),
        'uploaded': '0',
        'downloaded': '0',
        'left': str(total_length),
        'compact': '1',
        'event': 'started'
    }

    query_string = '&'.join(f"{key}={value}" for key, value in params.items())

    separator = '&' if '?' in announce_url else '?'
    return announce_url + separator + query_string

def request_peers(tracker_url: str) -> dict:
    """Make HTTP GET request to tracker and decode the response.

    The tracker responds with bencoded data containing:
    - interval: How often to re-announce (seconds)
    - peers: List of peers (either compact or dictionary format)

    Retrun the decoded response dictionary.
    """

    with urllib.request.urlopen(tracker_url, timeout = 10) as response:
        data = response.read()

    return decode(data)

def parse_compact_peers(peer_data: bytes) -> list[dict]:
    """
    Parse compact peer format from tracker response.
    
    Compact format: Each peer is 6 bytes:
    - 4 bytes: IP address (each byte is one octet)
    - 2 bytes: Port number (big-endian uint16)

    Example: b'\\x7f\\x00\\x00\\x01\\x1a\\xe1' means: 
    - IP: 127.0.0.1 (127, 0, 0, 1)                       
    - Port: 6881 (0x1ae1 in hex)
    """
    if len(peer_data) % 6 != 0:
        raise ValueError(f"Invalid compact peer data length: {len(peer_data)}")

    peers = []
    for i in range(0, len(peer_data), 6): 
        chunk = peer_data[i:i+6]

        ip = f"{chunk[0]}.{chunk[1]}.{chunk[2]}.{chunk[3]}"

        # Last 2 bytes are port (big-endian)
        port = (chunk[4] << 8) | chunk[5]

        peers.append({'ip': ip, 'port': port})

    return peers


# Example usage
if __name__ == "__main__":
    from torrent_meta import load_torrent

    print("=== BitTorrent Tracker Test ===\n")

    # Load torrent file
    meta = load_torrent("ubuntu-24.04.3-live-server-amd64.iso.torrent")

    # Extract info
    announce = meta[b'announce'].decode('utf-8')
    info = meta[b'info']

    print(f"Tracker: {announce}")

    # Calculate info hash
    info_hash = calculate_info_hash(info)
    print(f"Info hash: {info_hash.hex()}")

    # Get total file size
    if b'length' in info:
        total_length = info[b'length']
    else:
        total_length = sum(f[b'length'] for f in info[b'files'])
    print(f"Total size: {total_length:,} bytes")

    # Generate peer ID
    peer_id = generate_peer_id()
    print(f"Our peer ID: {peer_id}")

    # Build tracker URL
    tracker_url = build_tracker_url(announce, info_hash, peer_id, total_length)
    print(f"\nTracker URL (first 120 chars):\n{tracker_url[:120]}...\n")

    # Request peers from tracker
    print("Requesting peers from tracker...")
    try:
        response = request_peers(tracker_url)
        print(f"Response keys: {list(response.keys())}")

        # Parse peer list
        if b'peers' in response:
            peer_data = response[b'peers']
            if isinstance(peer_data, bytes):
                # Compact format
                peers = parse_compact_peers(peer_data)
                print(f"\nFound {len(peers)} peers!")
                print(f"First 5 peers:")
                for peer in peers[:5]:
                    print(f"  {peer['ip']}:{peer['port']}")
            else:
                print("Non-compact peer format (not implemented)")

        if b'interval' in response:
            print(f"\nRe-announce interval: {response[b'interval']} seconds")

    except Exception as e:
        print(f"Error: {e}")           

