from pathlib import Path
from bencode import decode

def load_torrent(path: str | Path) -> dict:
    """Load and decode a .torrent file."""
    path = Path(path)
    data = path.read_bytes()
    meta = decode(data)

    if not isinstance(meta, dict):
        raise ValueError("Torrent file did not decode to a dictionary")

    return meta

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <file.torrent>")
        raise SystemExit(1)

    torrent_path = sys.argv[1]
    meta = load_torrent(torrent_path)

    info = meta.get(b'info', {})

    print("announce:", meta.get(b"announce"))
    print("has announce-list:", b"announce-list" in meta)
    print("name:", info.get(b"name"))
    print("piece length:", info.get(b"piece length"))
    print("single-file length:", info.get(b"length"))
    print("multi-file:", b"files" in info)
