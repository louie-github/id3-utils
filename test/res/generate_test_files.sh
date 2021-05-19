#!/bin/sh

# TODO: Replace with pure Python solution
# In the future, let's just use a sample FLAC file and add metadata to it.
# I don't think it even matters if it's FLAC. as long as it's a file.

# Generate a stereo 1 second 512Hz sine wave WAV file at sample rate 48KHz
ffmpeg -loglevel info \
-f lavfi -i "sine=frequency=512:sample_rate=48000:duration=1" \
-c:a pcm_s16le -ac 2 \
input.wav

# Remove "LIST" chunk that FFMPEG generates for some reason...
# This doesn't affect the FLAC encoder, but let's try to keep things
# simple.
mv input.wav orig-input.wav
python remove_list_chunk.py orig-input.wav input.wav
rm orig-input.wav

# Generate FLAC files
flac --fast -T ENCODECOMMAND="flac --fast" -o input.flac input.wav
cp input.flac stripped.flac
cp input.flac v1-only.flac
cp input.flac v2-only.flac 
cp input.flac v1-and-v2.flac 

# Add metadata
id3v2 --id3v1-only --comment "ID3v1 only" v1-only.flac
id3v2 --id3v2-only --comment "ID3v2 only" v2-only.flac
id3v2 --comment "Both ID3v1 and ID3v2" v1-and-v2.flac
