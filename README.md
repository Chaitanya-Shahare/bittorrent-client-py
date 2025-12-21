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

# Download a file
python3 download.py <torrent_file> <output_file> [max_pieces]

# Example: Download first 5 pieces
python3 download.py ubuntu.torrent test.bin 5
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
