#!/bin/bash
set -e

echo "🚀 Finalizing Suno Playlist Downloader setup..."

# Create missing structure
mkdir -p suno_downloader
touch suno_downloader/__init__.py suno_downloader/__main__.py suno_downloader/bw_helper.py suno_downloader/config.yaml.example

# Move files to package (if not already done)
[ -f "init.py" ] && mv init.py suno_downloader/__init__.py
[ -f "main.py" ] && mv main.py suno_downloader/__main__.py
[ -f "cli.py" ] && mv cli.py suno_downloader/cli.py
[ -f "auth_fetch.py" ] && mv auth_fetch.py suno_downloader/auth_fetch.py

# Quick test install
pip install -e .[auth]

# Git setup
git init
git add .
git commit -m "feat: initial suno-playlist-downloader package [skip ci]"

echo "✅ Package structure ready!"
echo ""
echo "Choose Git option:"
echo "1. GitHub CLI (fastest): gh repo create suno-playlist-downloader --public --push"
echo "2. Manual: git remote add origin URL && git push -u origin main"
echo "3. Test locally: suno-download --init"
