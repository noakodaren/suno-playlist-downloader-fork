import os
import shutil
from pathlib import Path
from rich.console import Console

# Configuration
DOWNLOADS_DIR = Path('./downloads') # Where Suno downloader puts files
ALBUMS_DIR = Path('albums/12_Days_of_Systems') # Where Video Gen needs them

console = Console()

def normalize_name(name):
    """Converts '01 - Garden' or 'Garden (v2)' to 'Garden' for matching."""
    # Simple logic: assume the track name in Suno contains the prompt filename
    # You might need to adjust this based on your exact Suno naming convention
    return name.lower().replace(" ", "_").strip()

def sync_audio():
    console.print(f"[bold blue]Syncing audio from {DOWNLOADS_DIR} to {ALBUMS_DIR}...[/bold blue]")
    
    if not DOWNLOADS_DIR.exists():
        console.print("[red]No downloads folder found![/red]")
        return

    # 1. Map existing tracks in the Album folder
    track_folders = {f.name: f for f in ALBUMS_DIR.iterdir() if f.is_dir()}
    
    # 2. Walk through downloaded Suno files
    for root, _, files in os.walk(DOWNLOADS_DIR):
        for file in files:
            if file.endswith(('.mp3', '.wav')):
                src_path = Path(root) / file
                
                # Loose matching logic
                # If Suno file is "Garden.mp3", match it to folder "Garden"
                # If Suno file is "Golden Age.mp3", match to "Golden_Age"
                
                clean_filename = file.replace(" ", "_").replace("-", "_")
                
                matched_track = None
                for track_name, track_path in track_folders.items():
                    # Check if the track name exists inside the filename
                    if track_name.lower() in clean_filename.lower():
                        matched_track = track_path
                        break
                
                if matched_track:
                    dest_path = matched_track / "audio.mp3" # Or preserve extension
                    
                    # Optional: Don't overwrite if it exists?
                    # For now, let's assume latest download = best version
                    shutil.copy2(src_path, dest_path)
                    console.print(f"[green]Matched:[/green] {file} -> [bold]{matched_track.name}[/bold]")
                else:
                    console.print(f"[yellow]Skipped (No match):[/yellow] {file}")

if __name__ == "__main__":
    sync_audio()
