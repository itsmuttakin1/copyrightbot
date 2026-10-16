#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
mkdir -p ffmpeg_bin
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ -C ffmpeg_bin --strip-components 1
chmod +x ffmpeg_bin/ffmpeg
chmod +x ffmpeg_bin/ffprobe
