# peer_manager.py
#
# Advanced peer management with choking/unchoking algorithms.
#
# Key concepts:
# - Choking: Refusing to upload to a peer (we're "choking" them)
# - Unchoking: Allowing uploads to a peer
# - Optimistic unchoking: Periodically try new peers to find better ones
# - Tit-for-tat: Prefer peers who upload to us (reciprocation)
#
# Strategy:
# 1. Track download/upload rates for each peer
# 2. Unchoke top 4 peers based on download rate (tit-for-tat)
# 3. Optimistically unchoke 1 random peer every 30 seconds
# 4. This reduces bandwidth waste while maintaining good throughput

import time
import threading
from collections import defaultdict
from typing import List, Dict, Optional


class PeerStats:
    """Track statistics for a single peer."""

    def __init__(self, peer_ip: str, peer_port: int):
        self.ip = peer_ip
        self.port = peer_port
        self.downloaded = 0  # Total bytes downloaded
        self.uploaded = 0    # Total bytes uploaded
        self.last_download_time = time.time()
        self.last_upload_time = time.time()
        self.download_rate = 0.0  # Bytes per second
        self.upload_rate = 0.0    # Bytes per second
        self.is_choked_by_us = True   # Are we choking them?
        self.is_choking_us = True     # Are they choking us?
        self.is_interested_in_us = False
        self.we_are_interested = False
        self.connection_time = time.time()

    def update_downloaded(self, bytes_count: int):
        """Update download stats."""
        current_time = time.time()
        time_diff = current_time - self.last_download_time

        self.downloaded += bytes_count

        if time_diff > 0:
            # Calculate download rate (exponential moving average)
            instant_rate = bytes_count / time_diff
            self.download_rate = 0.8 * self.download_rate + 0.2 * instant_rate

        self.last_download_time = current_time

    def update_uploaded(self, bytes_count: int):
        """Update upload stats."""
        current_time = time.time()
        time_diff = current_time - self.last_upload_time

        self.uploaded += bytes_count

        if time_diff > 0:
            instant_rate = bytes_count / time_diff
            self.upload_rate = 0.8 * self.upload_rate + 0.2 * instant_rate

        self.last_upload_time = current_time

    def get_peer_id(self) -> str:
        """Get unique identifier for this peer."""
        return f"{self.ip}:{self.port}"

    def __repr__(self):
        return (f"Peer({self.ip}:{self.port}, "
                f"down={self.downloaded}, up={self.uploaded}, "
                f"rate={self.download_rate:.0f} B/s)")


class PeerManager:
    """
    Manages multiple peers with choking/unchoking algorithm.

    Implements BitTorrent's tit-for-tat strategy:
    - Unchoke the 4 best peers (highest download rates)
    - Optimistically unchoke 1 random peer every 30 seconds
    - Choke all other peers to save bandwidth
    """

    def __init__(self, max_unchoked_peers: int = 4):
        self.peers: Dict[str, PeerStats] = {}
        self.max_unchoked_peers = max_unchoked_peers
        self.optimistic_unchoke_interval = 30  # seconds
        self.last_optimistic_unchoke = time.time()
        self.lock = threading.Lock()

        # Statistics
        self.total_downloaded = 0
        self.total_uploaded = 0
        self.start_time = time.time()

    def add_peer(self, ip: str, port: int) -> PeerStats:
        """Add a new peer to manage."""
        peer_id = f"{ip}:{port}"

        with self.lock:
            if peer_id not in self.peers:
                self.peers[peer_id] = PeerStats(ip, port)
            return self.peers[peer_id]

    def get_peer(self, ip: str, port: int) -> Optional[PeerStats]:
        """Get stats for a peer."""
        peer_id = f"{ip}:{port}"
        return self.peers.get(peer_id)

    def update_download(self, ip: str, port: int, bytes_count: int):
        """Update download statistics."""
        peer = self.get_peer(ip, port)
        if peer:
            peer.update_downloaded(bytes_count)
            with self.lock:
                self.total_downloaded += bytes_count

    def update_upload(self, ip: str, port: int, bytes_count: int):
        """Update upload statistics."""
        peer = self.get_peer(ip, port)
        if peer:
            peer.update_uploaded(bytes_count)
            with self.lock:
                self.total_uploaded += bytes_count

    def recalculate_choking(self) -> List[PeerStats]:
        """
        Recalculate which peers to choke/unchoke.

        Returns list of peers that should be unchoked.

        Algorithm:
        1. Sort peers by download rate (highest first)
        2. Unchoke top N peers
        3. Every 30 seconds, optimistically unchoke a random peer
        4. Choke everyone else
        """
        with self.lock:
            current_time = time.time()

            # Get all interested peers (those who want our data)
            interested_peers = [p for p in self.peers.values()
                              if p.is_interested_in_us and not p.is_choking_us]

            if not interested_peers:
                # No interested peers, return empty list
                return []

            # Sort by download rate (tit-for-tat: prefer peers uploading to us)
            sorted_peers = sorted(interested_peers,
                                key=lambda p: p.download_rate,
                                reverse=True)

            # Unchoke top N-1 peers
            unchoked = sorted_peers[:self.max_unchoked_peers - 1]

            # Optimistic unchoking: every 30 seconds, try a random peer
            if current_time - self.last_optimistic_unchoke > self.optimistic_unchoke_interval:
                # Find peers not in top N-1
                other_peers = [p for p in interested_peers if p not in unchoked]
                if other_peers:
                    import random
                    optimistic_peer = random.choice(other_peers)
                    unchoked.append(optimistic_peer)
                    self.last_optimistic_unchoke = current_time
            else:
                # Use the Nth peer from sorted list
                if len(sorted_peers) >= self.max_unchoked_peers:
                    unchoked.append(sorted_peers[self.max_unchoked_peers - 1])

            # Update choke status
            unchoked_ids = {p.get_peer_id() for p in unchoked}
            for peer in self.peers.values():
                peer.is_choked_by_us = peer.get_peer_id() not in unchoked_ids

            return unchoked

    def get_best_peers_for_download(self, count: int = 5) -> List[PeerStats]:
        """
        Get best peers to request pieces from.

        Prefer peers that:
        1. Are not choking us
        2. Have high download rates
        3. Are unchoked by us (reciprocal relationship)
        """
        with self.lock:
            available = [p for p in self.peers.values()
                        if not p.is_choking_us]

            # Sort by download rate
            sorted_peers = sorted(available,
                                key=lambda p: p.download_rate,
                                reverse=True)

            return sorted_peers[:count]

    def get_statistics(self) -> Dict:
        """Get overall statistics."""
        with self.lock:
            elapsed = time.time() - self.start_time

            return {
                'total_downloaded': self.total_downloaded,
                'total_uploaded': self.total_uploaded,
                'download_rate': self.total_downloaded / elapsed if elapsed > 0 else 0,
                'upload_rate': self.total_uploaded / elapsed if elapsed > 0 else 0,
                'num_peers': len(self.peers),
                'unchoked_peers': sum(1 for p in self.peers.values()
                                     if not p.is_choked_by_us),
                'elapsed_time': elapsed
            }

    def print_statistics(self):
        """Print peer statistics."""
        stats = self.get_statistics()

        print("\n=== Peer Manager Statistics ===")
        print(f"Total Downloaded: {stats['total_downloaded']:,} bytes "
              f"({stats['total_downloaded'] / (1024*1024):.2f} MB)")
        print(f"Total Uploaded: {stats['total_uploaded']:,} bytes "
              f"({stats['total_uploaded'] / (1024*1024):.2f} MB)")
        print(f"Download Rate: {stats['download_rate'] / 1024:.2f} KB/s")
        print(f"Upload Rate: {stats['upload_rate'] / 1024:.2f} KB/s")
        print(f"Peers: {stats['num_peers']} (unchoked: {stats['unchoked_peers']})")
        print(f"Elapsed: {stats['elapsed_time']:.1f} seconds")

        with self.lock:
            print("\nTop Peers:")
            sorted_peers = sorted(self.peers.values(),
                                key=lambda p: p.downloaded,
                                reverse=True)
            for i, peer in enumerate(sorted_peers[:5], 1):
                status = "unchoked" if not peer.is_choked_by_us else "choked"
                print(f"  {i}. {peer.ip}:{peer.port} - "
                      f"{peer.downloaded:,} bytes, "
                      f"{peer.download_rate / 1024:.2f} KB/s ({status})")


if __name__ == "__main__":
    # Test peer manager
    manager = PeerManager(max_unchoked_peers=4)

    # Simulate some peers
    peer1 = manager.add_peer("192.168.1.1", 6881)
    peer2 = manager.add_peer("192.168.1.2", 6881)
    peer3 = manager.add_peer("192.168.1.3", 6881)
    peer4 = manager.add_peer("192.168.1.4", 6881)
    peer5 = manager.add_peer("192.168.1.5", 6881)

    # Mark them as interested
    for peer in [peer1, peer2, peer3, peer4, peer5]:
        peer.is_interested_in_us = True
        peer.is_choking_us = False

    # Simulate downloads with different rates
    manager.update_download("192.168.1.1", 6881, 100000)  # Fast
    manager.update_download("192.168.1.2", 6881, 50000)   # Medium
    manager.update_download("192.168.1.3", 6881, 80000)   # Fast
    manager.update_download("192.168.1.4", 6881, 20000)   # Slow
    manager.update_download("192.168.1.5", 6881, 10000)   # Slow

    # Recalculate choking
    unchoked = manager.recalculate_choking()

    print("Unchoked peers:")
    for peer in unchoked:
        print(f"  {peer}")

    print("\nChoked peers:")
    for peer in manager.peers.values():
        if peer.is_choked_by_us:
            print(f"  {peer}")

    manager.print_statistics()
