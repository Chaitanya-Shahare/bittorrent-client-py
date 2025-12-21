# download.py
#
# Complete BitTorrent file download implementation.
#
# Strategy:
# 1. Get peers from tracker
# 2. Connect to peer and handshake
# 3. Exchange protocol messages
# 4. Download pieces in 16KB blocks
# 5. Verify piece hashes
# 6. Write to file

import socket
import hashlib
import time
from peer_protocol import *
from tracker_http import *
from torrent_meta import load_torrent


BLOCK_SIZE = 16384  # 16 KB - standard block size


def download_piece(peer_ip: str, peer_port: int, info_hash: bytes,
                   peer_id: bytes, piece_index: int, piece_length: int,
                   timeout: int = 30) -> bytes:
    """
    Download a single piece from a peer.

    Steps:
    1. TCP connect
    2. Send/receive handshake
    3. Wait for bitfield
    4. Send interested
    5. Wait for unchoke
    6. Request blocks
    7. Receive piece data

    Returns: piece data as bytes
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        print(f"  Connecting to {peer_ip}:{peer_port}...")
        sock.connect((peer_ip, peer_port))

        # Send handshake
        handshake = create_handshake(info_hash, peer_id)
        sock.sendall(handshake)

        # Receive handshake response (may need multiple recv calls)
        response = b""
        while len(response) < 68:
            data = sock.recv(68 - len(response))
            if not data:
                raise Exception(f"Connection closed during handshake (got {len(response)} bytes)")
            response += data

        peer_info = parse_handshake(response)
        print(f"  Handshake OK with peer {peer_info['peer_id'][:8].hex()}")

        # Read messages
        buffer = b""
        bitfield_received = False
        unchoked = False

        # Wait for bitfield (or unchoke if peer doesn't send bitfield)
        print("  Waiting for bitfield...")
        timeout_counter = 0
        while not bitfield_received and timeout_counter < 5:
            try:
                data = sock.recv(4096)
                if not data:
                    raise Exception("Connection closed before bitfield")
                buffer += data

                # Try to parse all messages in buffer
                while True:
                    msg_id, payload, consumed = parse_message(buffer)
                    if consumed == 0:
                        break  # Need more data

                    buffer = buffer[consumed:]

                    if msg_id == MSG_BITFIELD:
                        print("  Received bitfield")
                        bitfield_received = True
                        break
                    elif msg_id == MSG_UNCHOKE:
                        print("  Received unchoke (no bitfield sent)")
                        bitfield_received = True  # Skip bitfield
                        unchoked = True
                        break
                    elif msg_id is not None:
                        print(f"  Received message ID: {msg_id}")

                if bitfield_received:
                    break

            except socket.timeout:
                timeout_counter += 1
                print(f"  Timeout {timeout_counter}/5...")
                continue

        # Send interested (if not already unchoked)
        if not unchoked:
            sock.sendall(create_message(MSG_INTERESTED))
            print("  Sent interested")

            # Wait for unchoke
            print("  Waiting for unchoke...")
            while not unchoked:
                data = sock.recv(4096)
                if not data:
                    raise Exception("Connection closed before unchoke")
                buffer += data

                while True:
                    msg_id, payload, consumed = parse_message(buffer)
                    if consumed == 0:
                        break

                    buffer = buffer[consumed:]

                    if msg_id == MSG_UNCHOKE:
                        print("  Received unchoke - ready to download!")
                        unchoked = True
                        break
                    elif msg_id is not None:
                        print(f"  Received message ID: {msg_id}")

                if unchoked:
                    break
        else:
            print("  Already unchoked - ready to download!")

        # Request and download blocks
        piece_data = b""
        offset = 0

        while offset < piece_length:
            block_size = min(BLOCK_SIZE, piece_length - offset)

            # Send request
            request = create_request(piece_index, offset, block_size)
            sock.sendall(request)
            print(f"  Requested block at offset {offset} ({block_size} bytes)")

            # Receive piece
            received_block = False
            while not received_block:
                data = sock.recv(32768)  # Larger buffer for block data
                if not data:
                    raise Exception(f"Connection closed while downloading block at {offset}")
                buffer += data

                msg_id, payload, consumed = parse_message(buffer)
                if consumed > 0:
                    buffer = buffer[consumed:]

                    if msg_id == MSG_PIECE:
                        piece_msg = parse_piece_message(payload)

                        # Verify it's the block we requested
                        if piece_msg['index'] == piece_index and piece_msg['begin'] == offset:
                            piece_data += piece_msg['block']
                            print(f"  Received block at offset {offset} ({len(piece_msg['block'])} bytes)")
                            received_block = True
                        else:
                            print(f"  Warning: unexpected piece message (idx={piece_msg['index']}, begin={piece_msg['begin']})")

            offset += block_size

        print(f"  Piece {piece_index} downloaded completely ({len(piece_data)} bytes)")
        return piece_data

    finally:
        sock.close()


def verify_piece(piece_data: bytes, expected_hash: bytes) -> bool:
    """Verify piece SHA-1 hash matches expected."""
    actual_hash = hashlib.sha1(piece_data).digest()
    return actual_hash == expected_hash


def download_file(torrent_path: str, output_path: str, max_pieces: int = None):
    """
    Download complete file from torrent.

    Args:
    - torrent_path: Path to .torrent file
    - output_path: Where to save downloaded file
    - max_pieces: Limit number of pieces to download (for testing)
    """
    print(f"=== BitTorrent Downloader ===\n")

    # Load torrent metadata
    print("Loading torrent file...")
    meta = load_torrent(torrent_path)
    info = meta[b'info']

    # Extract metadata
    info_hash = calculate_info_hash(info)
    peer_id = generate_peer_id()

    file_name = info[b'name'].decode('utf-8')
    total_length = info[b'length']
    piece_length = info[b'piece length']
    pieces_hashes = info[b'pieces']  # Concatenated 20-byte SHA-1 hashes

    print(f"File: {file_name}")
    print(f"Size: {total_length:,} bytes ({total_length / (1024*1024):.2f} MB)")
    print(f"Piece length: {piece_length:,} bytes")
    print(f"Info hash: {info_hash.hex()}")

    # Calculate number of pieces
    num_pieces = (total_length + piece_length - 1) // piece_length
    print(f"Total pieces: {num_pieces}")

    if max_pieces:
        num_pieces = min(num_pieces, max_pieces)
        print(f"Limiting to first {num_pieces} pieces for testing")

    # Get peers from tracker (try announce-list if available)
    peers = []
    trackers = []

    if b'announce-list' in meta:
        for tier in meta[b'announce-list']:
            for tracker in tier:
                trackers.append(tracker.decode('utf-8'))
    else:
        trackers.append(meta[b'announce'].decode('utf-8'))

    print(f"\nTrying {len(trackers)} tracker(s)...")
    for tracker in trackers:
        try:
            print(f"  Contacting: {tracker}")
            tracker_url = build_tracker_url(tracker, info_hash, peer_id, total_length)
            response = request_peers(tracker_url)
            if b'peers' in response:
                new_peers = parse_compact_peers(response[b'peers'])
                peers.extend(new_peers)
                print(f"  Got {len(new_peers)} peers")
        except Exception as e:
            print(f"  Failed: {e}")

    print(f"Found {len(peers)} peers:")
    for i, peer in enumerate(peers[:10]):
        print(f"  {i+1}. {peer['ip']}:{peer['port']}")
    if len(peers) > 10:
        print(f"  ... and {len(peers) - 10} more")

    # Download pieces
    print(f"\n=== Downloading {num_pieces} pieces ===\n")
    downloaded_pieces = []

    for piece_idx in range(num_pieces):
        # Get expected hash for this piece
        expected_hash = pieces_hashes[piece_idx * 20:(piece_idx + 1) * 20]

        # Calculate piece size (last piece might be smaller)
        if piece_idx == num_pieces - 1 and max_pieces is None:
            current_piece_length = total_length - (piece_idx * piece_length)
        else:
            current_piece_length = piece_length

        print(f"Piece {piece_idx + 1}/{num_pieces} ({current_piece_length:,} bytes)")

        # Try peers until successful
        piece_data = None
        for peer_idx, peer in enumerate(peers):
            try:
                piece_data = download_piece(
                    peer['ip'], peer['port'],
                    info_hash, peer_id,
                    piece_idx, current_piece_length
                )

                # Verify hash
                if verify_piece(piece_data, expected_hash):
                    print(f"  ✓ Piece {piece_idx} hash verified!\n")
                    break
                else:
                    print(f"  ✗ Piece {piece_idx} hash mismatch!\n")
                    piece_data = None

            except Exception as e:
                print(f"  Error with peer {peer['ip']}: {e}\n")
                if peer_idx < len(peers) - 1:
                    print(f"  Trying next peer...\n")
                continue

        if piece_data is None:
            raise Exception(f"Failed to download piece {piece_idx} from any peer")

        downloaded_pieces.append(piece_data)

        # Progress update
        downloaded_bytes = sum(len(p) for p in downloaded_pieces)
        if max_pieces:
            progress = (piece_idx + 1) / num_pieces * 100
            print(f"Progress: {piece_idx + 1}/{num_pieces} pieces ({progress:.1f}%)\n")
        else:
            progress = downloaded_bytes / total_length * 100
            print(f"Progress: {downloaded_bytes:,}/{total_length:,} bytes ({progress:.1f}%)\n")

    # Write to file
    print(f"Writing to {output_path}...")
    with open(output_path, 'wb') as f:
        for piece in downloaded_pieces:
            f.write(piece)

    final_size = sum(len(p) for p in downloaded_pieces)
    print(f"\n✓ Download complete!")
    print(f"  File: {output_path}")
    print(f"  Size: {final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python download.py <torrent_file> [output_file] [max_pieces]")
        print("\nExample:")
        print("  python download.py ubuntu.torrent ubuntu.iso")
        print("  python download.py ubuntu.torrent test.bin 5  # Download only first 5 pieces")
        sys.exit(1)

    torrent_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "downloaded_file.bin"
    max_pieces = int(sys.argv[3]) if len(sys.argv) > 3 else None

    try:
        download_file(torrent_file, output_file, max_pieces)
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
