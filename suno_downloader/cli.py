#!/usr/bin/env python3
"""Main downloader CLI.

Supports:
- Playlist IDs from CLI override config
- If no CLI IDs, processes playlists from config.yaml
- Optional Bitwarden integration for credentials
"""
import argparse
import yaml
import os
import csv
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from pathlib import Path

from .api import SunoAPI
from .utils import sanitize_filename, download_with_retries


def find_config_file(config_path: Optional[str] = None) -> Path:
    """Find config file in standard locations."""
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # Search standard locations
    locations = [
        Path.cwd() / "config.yaml",
        Path.home() / ".config" / "suno-downloader" / "config.yaml",
        Path.home() / ".suno-downloader.yaml",
    ]
    
    for loc in locations:
        if loc.exists():
            return loc
    
    raise FileNotFoundError(
        "No config.yaml found. Create one with: suno-download --init"
    )


def init_config():
    """Create a template config.yaml in the current directory."""
    template = """# Suno Downloader Configuration
# DO NOT commit this file with real credentials!

# Authentication (can be overridden by Bitwarden)
auth_source: config  # or 'bitwarden'
token: "REPLACE_WITH_YOUR_BEARER_TOKEN"
device_id: "REPLACE_WITH_YOUR_DEVICE_ID"

# Bitwarden settings (if auth_source: bitwarden)
bitwarden:
  item_name: "Suno API"
  # Set BW_SESSION environment variable or run 'bw unlock' first

# Downloader behavior
download_workers: 4
output_root: "./downloads"

# Optional: list playlist IDs (overridden by CLI arguments)
playlists: []
  # - id: "f1485f8c-c27f-4bb9-bc8e-aff0665715df"

# Retry & timeouts
http_timeout_seconds: 30
download_retry_attempts: 3
download_retry_backoff_seconds: 2

# Manifest and logging
manifest_json: true
manifest_csv: true

# Rate-limiting
delay_between_downloads_seconds: 0.5
"""
    config_path = Path.cwd() / "config.yaml"
    if config_path.exists():
        response = input(f"{config_path} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    config_path.write_text(template)
    print(f"Created config template: {config_path}")
    print("Edit this file and add your credentials before running.")


def load_config(path: Path) -> dict:
    """Load and validate configuration."""
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Handle Bitwarden authentication if configured
    if cfg.get('auth_source') == 'bitwarden':
        try:
            from .bw_helper import get_item_fields
            
            bw_config = cfg.get('bitwarden', {})
            item_name = bw_config.get('item_name', 'Suno API')
            
            fields = get_item_fields(item_name)
            if not fields:
                raise RuntimeError(
                    f"Bitwarden item '{item_name}' not found. "
                    "Run 'suno-auth' to set up credentials."
                )
            
            cfg['token'] = fields.get('token')
            cfg['device_id'] = fields.get('device_id')
            
            if not cfg['token'] or not cfg['device_id']:
                raise RuntimeError(
                    f"Bitwarden item '{item_name}' missing token or device_id fields"
                )
                
        except ImportError:
            raise RuntimeError(
                "Bitwarden integration requires bw CLI. "
                "Install it or change auth_source to 'config'"
            )
    
    return cfg


def ensure_playlist_list(cfg: dict) -> List[str]:
    """Extract playlist IDs from config."""
    pl = cfg.get('playlists') or []
    ids = []
    for p in pl:
        if isinstance(p, dict) and 'id' in p:
            ids.append(p['id'])
        elif isinstance(p, str):
            ids.append(p)
    return ids


def process_playlist(api: SunoAPI, playlist_id: str, cfg: dict):
    """Download all clips from a single playlist."""
    print(f"Processing playlist {playlist_id}")
    playlist_data = api.get_playlist(playlist_id)
    
    playlist_title = (
        playlist_data.get('title') or 
        playlist_data.get('name') or 
        playlist_id
    )

    clips = playlist_data.get('playlist_clips') or playlist_data.get('clips') or playlist_data.get('items') or []

    out_root = cfg.get('output_root', './downloads')
    playlist_folder = os.path.join(out_root, f"{sanitize_filename(playlist_title)}_{playlist_id}")
    os.makedirs(playlist_folder, exist_ok=True)

    manifest = []
    workers = cfg.get('download_workers', 4)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        
        for clip in clips:
            clip = clip.get('clip')
            clip_id = clip.get('id') if isinstance(clip, dict) else clip
            title = clip.get('title') if isinstance(clip, dict) else clip_id
            safe_title = sanitize_filename(title)

            try:
                signed = api.request_download_url(clip_id)
            except Exception as e:
                print(f"Failed to request download url for {clip_id}: {e}")
                raise

            ext = os.path.splitext(signed.split('?')[0])[1] or '.wav'
            out_path = os.path.join(playlist_folder, f"{safe_title}_{clip_id}{ext}")

            futures[ex.submit(
                download_with_retries,
                signed,
                out_path,
                cfg.get('http_timeout_seconds', 30),
                cfg.get('download_retry_attempts', 3),
                cfg.get('download_retry_backoff_seconds', 2)
            )] = {
                'clip_id': clip_id,
                'title': title,
                'path': out_path,
                'url': signed,
            }

            if cfg.get('delay_between_downloads_seconds', 0):
                time.sleep(cfg['delay_between_downloads_seconds'])

        for fut in as_completed(futures):
            info = futures[fut]
            fut.result()
            print(f"Downloaded: {info['title']}")
            manifest.append({
                'playlist_id': playlist_id,
                'clip_id': info['clip_id'],
                'title': info['title'],
                'file_path': info['path'],
                'download_url': info['url'],
            })

    # Save manifests
    if cfg.get('manifest_json', True):
        with open(
            os.path.join(playlist_folder, 'manifest.json'), 
            'w', 
            encoding='utf-8'
        ) as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    if cfg.get('manifest_csv', True) and manifest:
        keys = manifest[0].keys()
        with open(
            os.path.join(playlist_folder, 'manifest.csv'), 
            'w', 
            newline='', 
            encoding='utf-8'
        ) as f:
            writer = csv.DictWriter(f, keys)
            writer.writeheader()
            writer.writerows(manifest)

    print(f"Finished playlist {playlist_id}. Files saved in {playlist_folder}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Suno playlist downloader',
        epilog='For more info: https://github.com/yourusername/suno-playlist-downloader'
    )
    parser.add_argument(
        '--config', 
        help='Path to config.yaml (searches standard locations if not provided)'
    )
    parser.add_argument(
        '--init', 
        action='store_true',
        help='Create a template config.yaml in the current directory'
    )
    parser.add_argument(
        'playlist_ids', 
        nargs='*', 
        help='Playlist IDs to download (overrides config)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    args = parser.parse_args()

    if args.init:
        init_config()
        return 0

    try:
        config_file = find_config_file(args.config)
        cfg = load_config(config_file)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    bearer = cfg.get('token')
    device_id = cfg.get('device_id')
    
    if not bearer or not device_id:
        print(
            'Error: token and device_id are required.\n'
            'Either set them in config.yaml or use Bitwarden integration.\n'
            'Run "suno-auth" to set up authentication.',
            file=sys.stderr
        )
        return 1

    api = SunoAPI(
        bearer, 
        device_id, 
        timeout=cfg.get('http_timeout_seconds', 30)
    )

    # Determine playlists to process
    to_process = args.playlist_ids or ensure_playlist_list(cfg)

    if not to_process:
        print(
            'Error: No playlist IDs provided.\n'
            'Specify IDs on command line or in config.yaml',
            file=sys.stderr
        )
        return 1

    for pid in to_process:
        try:
            process_playlist(api, pid, cfg)
        except Exception as e:
            print(f"Error processing playlist {pid}: {e}", file=sys.stderr)
            raise

    return 0


if __name__ == '__main__':
    sys.exit(main())
