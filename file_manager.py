# file_manager.py
#
# Handle both single-file and multi-file torrents.
#
# Single-file torrent structure:
#   info: {
#     name: "file.txt",
#     length: 12345,
#     ...
#   }
#
# Multi-file torrent structure:
#   info: {
#     name: "directory_name",
#     files: [
#       {path: ["subdir", "file1.txt"], length: 100},
#       {path: ["file2.txt"], length: 200},
#     ],
#     ...
#   }

import os
from pathlib import Path
from typing import List, Dict, Tuple


class FileManager:
    """
    Manages file I/O for both single-file and multi-file torrents.
    """

    def __init__(self, info: dict, base_output_dir: str = "downloads"):
        self.info = info
        self.base_output_dir = base_output_dir
        self.is_multi_file = b'files' in info

        if self.is_multi_file:
            self.root_name = info[b'name'].decode('utf-8')
            self.files = self._parse_file_list()
            self.total_length = sum(f['length'] for f in self.files)
        else:
            self.root_name = info[b'name'].decode('utf-8')
            self.files = [{
                'path': self.root_name,
                'length': info[b'length'],
                'offset': 0
            }]
            self.total_length = info[b'length']

    def _parse_file_list(self) -> List[Dict]:
        """
        Parse multi-file torrent file list.

        Returns list of dicts with:
        - path: Full path to file
        - length: File size
        - offset: Byte offset in the torrent
        """
        files = []
        current_offset = 0

        for file_info in self.info[b'files']:
            # Build path from components
            path_parts = [part.decode('utf-8') for part in file_info[b'path']]
            relative_path = os.path.join(*path_parts)

            # Full path including root directory
            full_path = os.path.join(self.root_name, relative_path)

            length = file_info[b'length']

            files.append({
                'path': full_path,
                'length': length,
                'offset': current_offset
            })

            current_offset += length

        return files

    def get_file_info(self) -> Dict:
        """Get summary information."""
        return {
            'is_multi_file': self.is_multi_file,
            'root_name': self.root_name,
            'total_length': self.total_length,
            'file_count': len(self.files),
            'files': self.files
        }

    def create_directories(self):
        """Create all necessary directories for the download."""
        if self.is_multi_file:
            # Create root directory
            root_dir = os.path.join(self.base_output_dir, self.root_name)
            Path(root_dir).mkdir(parents=True, exist_ok=True)

            # Create subdirectories for each file
            for file_info in self.files:
                file_path = os.path.join(self.base_output_dir, file_info['path'])
                file_dir = os.path.dirname(file_path)
                if file_dir:
                    Path(file_dir).mkdir(parents=True, exist_ok=True)
        else:
            # Just ensure base directory exists
            Path(self.base_output_dir).mkdir(parents=True, exist_ok=True)

    def write_pieces(self, pieces_data: Dict[int, bytes], piece_length: int):
        """
        Write downloaded pieces to appropriate files.

        Args:
        - pieces_data: Dict mapping piece index to piece data
        - piece_length: Length of each piece
        """
        self.create_directories()

        # Concatenate all pieces in order
        all_data = b""
        for piece_idx in sorted(pieces_data.keys()):
            all_data += pieces_data[piece_idx]

        # Write to files
        bytes_written = 0

        for file_info in self.files:
            file_path = os.path.join(self.base_output_dir, file_info['path'])
            file_length = file_info['length']
            file_offset = file_info['offset']

            # Extract data for this file
            file_data = all_data[file_offset:file_offset + file_length]

            # Write to file
            with open(file_path, 'wb') as f:
                f.write(file_data)

            bytes_written += len(file_data)
            print(f"  Wrote {len(file_data):,} bytes to {file_path}")

        return bytes_written

    def get_output_summary(self) -> str:
        """Get a summary string of where files were written."""
        if self.is_multi_file:
            root_path = os.path.join(self.base_output_dir, self.root_name)
            return f"{root_path}/ ({len(self.files)} files)"
        else:
            return os.path.join(self.base_output_dir, self.root_name)

    def print_file_list(self):
        """Print list of files in the torrent."""
        if self.is_multi_file:
            print(f"\nFiles in torrent ({len(self.files)} files):")
            for i, file_info in enumerate(self.files[:10], 1):
                size_mb = file_info['length'] / (1024 * 1024)
                print(f"  {i}. {file_info['path']} ({size_mb:.2f} MB)")
            if len(self.files) > 10:
                print(f"  ... and {len(self.files) - 10} more files")
        else:
            size_mb = self.total_length / (1024 * 1024)
            print(f"\nSingle file: {self.root_name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    # Test with single-file torrent structure
    print("=== Single-File Torrent Test ===")
    single_info = {
        b'name': b'test.txt',
        b'length': 1024
    }
    single_fm = FileManager(single_info)
    info = single_fm.get_file_info()
    print(f"Type: {'Multi' if info['is_multi_file'] else 'Single'} file")
    print(f"Root: {info['root_name']}")
    print(f"Total size: {info['total_length']} bytes")
    print(f"Files: {info['file_count']}")

    # Test with multi-file torrent structure
    print("\n=== Multi-File Torrent Test ===")
    multi_info = {
        b'name': b'my_folder',
        b'files': [
            {b'path': [b'file1.txt'], b'length': 100},
            {b'path': [b'subdir', b'file2.txt'], b'length': 200},
            {b'path': [b'subdir', b'file3.txt'], b'length': 300},
        ]
    }
    multi_fm = FileManager(multi_info)
    info = multi_fm.get_file_info()
    print(f"Type: {'Multi' if info['is_multi_file'] else 'Single'} file")
    print(f"Root: {info['root_name']}")
    print(f"Total size: {info['total_length']} bytes")
    print(f"Files: {info['file_count']}")
    multi_fm.print_file_list()

    print(f"\nOutput summary: {multi_fm.get_output_summary()}")
