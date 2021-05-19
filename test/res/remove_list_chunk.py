#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import os
import shutil
import sys

from functools import partial

input_file = sys.argv[1]
output_file = sys.argv[2]

err_log = partial(print, file=sys.stderr)
bytes_to_int = partial(int.from_bytes, byteorder="little", signed=False)
int_to_bytes = partial(int.to_bytes, byteorder="little", signed=False)

with open(input_file, "rb") as in_f, open(output_file, "wb") as out_f:
    in_f.seek(36)
    subchunk2_id = in_f.read(4)
    if subchunk2_id == b"data":
        shutil.copyfile(input_file, output_file)
        raise SystemExit("No LIST chunk detected. File was copied.")
    elif subchunk2_id == b"LIST":
        err_log("Found LIST subchunk.", end=" ")
    else:
        raise ValueError('Expected either "data" or "LIST" for subchunk 2')

    list_subchunk_size = bytes_to_int(in_f.read(4))
    # Account for "LIST" subchunk ID and size
    list_subchunk_total_size = list_subchunk_size + 8
    err_log(f"Reported subchunk size: {list_subchunk_size} bytes.")
    chunk_size = os.path.getsize(input_file) - list_subchunk_total_size - 8

    # Start writing output file
    in_f.seek(0)
    bufsize = io.DEFAULT_BUFFER_SIZE
    bytes_written = 0
    # RIFF header
    bytes_written += out_f.write(in_f.read(4))  # ChunkID
    bytes_written += out_f.write(int_to_bytes(chunk_size, 4))  # new ChunkSize
    in_f.seek(4, os.SEEK_CUR)  # skip old ChunkSize
    bytes_written += out_f.write(in_f.read(4))  # Format
    # Subchunk1
    bytes_written += out_f.write(in_f.read(24))
    # Skip "LIST" subchunk
    in_f.seek(list_subchunk_total_size, os.SEEK_CUR)

    # Write "data" subchunk
    buffer = in_f.read(4)
    assert buffer == b"data"
    while buffer:
        bytes_written += out_f.write(buffer)
        buffer = in_f.read(bufsize)

    err_log(f"Successfully wrote {bytes_written} bytes to output.")

if __debug__:
    with open(output_file, "rb") as out_f:
        # Verify that chunk IDs and sizes are what they should be
        def __read_at_offset(offset: int, size: int, whence: int = os.SEEK_SET):
            out_f.seek(offset, whence)
            return out_f.read(size)

        __file_size = out_f.seek(0, os.SEEK_END)
        assert bytes_written == __file_size
        __expected_chunk_size = __file_size - 8
        __expected_subchunk1_size = 16
        __expected_subchunk2_size = __file_size - 44

        __chunk_id = __read_at_offset(0, 4)
        __chunk_size = bytes_to_int(__read_at_offset(4, 4))
        __subchunk1_id = __read_at_offset(12, 4)
        __subchunk1_size = bytes_to_int(__read_at_offset(16, 4))
        __subchunk2_id = __read_at_offset(36, 4)
        __subchunk2_size = bytes_to_int(__read_at_offset(40, 4))

        assert __chunk_id == b"RIFF"
        assert __chunk_size == __expected_chunk_size
        assert __subchunk1_id == b"fmt "
        assert __subchunk1_size == __expected_subchunk1_size
        assert __subchunk2_id == b"data"
        assert __subchunk2_size == __expected_subchunk2_size
