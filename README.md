# Suno Playlist Downloader

Download audio files from Suno playlists using the undocumented Suno API.

## Installation
Install python and some dependencies with `pip install dependency`.

Run the program first with `python -m suno_downloader --init` (in for example
powershell or another terminal). Edit then `config.yaml`, especially `token`
(look for BEARER under the authentication header under the network tab in
chrome developer tools) and `playlists` (the id:s can be found in the url of a
playlist). Run then the program as `python -m suno_downloader`.

