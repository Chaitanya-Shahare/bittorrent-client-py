# BitTorrent Client in Python

A minimal BitTorrent client implementation in Python using only standard library (no external dependencies).

## Project Status

✅ **Completed Components:**
- Bencode encoder/decoder
- Torrent file parser
- HTTP tracker communication
- Peer wire protocol implementation
- Download manager with piece verification

## Files

- **bencode.py** - Bencode encoding/decoding
- **torrent_meta.py** - Torrent file loader
- **tracker_http.py** - HTTP tracker communication
- **peer_protocol.py** - BitTorrent peer wire protocol
- **download.py** - Main download logic

## Usage

```bash
# Test tracker communication
python3 tracker_http.py

# Download a file (auto-saves to downloads/ directory)
python3 download.py <torrent_file>

# Download with custom output path
python3 download.py <torrent_file> <output_file>

# Download only first N pieces (for testing)
python3 download.py <torrent_file> [output_file] <max_pieces>

# Examples:
python3 download.py ubuntu.torrent
# → Saves to: downloads/ubuntu-24.04.3-live-server-amd64.iso

python3 download.py ubuntu.torrent 5
# → Downloads first 5 pieces to: downloads/ubuntu-24.04.3-live-server-amd64.iso

python3 download.py ubuntu.torrent custom.iso
# → Saves to: custom.iso

python3 download.py ubuntu.torrent test.bin 5
# → Downloads first 5 pieces to: test.bin
```

## How It Works

1. **Parse torrent** - Load and decode .torrent file
2. **Contact tracker** - Get list of peers
3. **Connect to peers** - TCP handshake and protocol negotiation
4. **Download pieces** - Request 16KB blocks, verify SHA-1 hashes
5. **Save file** - Write verified pieces to disk

## Known Limitations

- No encryption support
- No DHT (only HTTP trackers)
- No magnet links
- Single-threaded (one peer at a time)
- Download-only (no seeding)

## Learning Resources

- [BitTorrent Protocol Specification](http://www.bittorrent.org/beps/bep_0003.html)
- [Unofficial BitTorrent Specification](https://wiki.theory.org/BitTorrentSpecification)
