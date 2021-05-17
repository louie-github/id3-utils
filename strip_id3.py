#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import logging

from collections import namedtuple
from typing import BinaryIO

# Change this if necessary.
logging.basicConfig(level=logging.DEBUG)

# Based on the informal standard for ID3v2.3.0 found at:
# https://id3.org/id3v2.3.0
ID3v2_IDENTIFIER = b"ID3"
ID3v2_VERSION_LENGTH = 2
IDv3_FLAGS_LENGTH = 1
IDv3_SIZE_LENGTH = 4

ID3v2Header = namedtuple(
    "ID3v2Header",
    [
        "major_version",
        "revision",
        "unsynchronisation",
        "extended_header",
        "experimental",
        "tag_size",
    ],
)

# This script can only remove ID3v2.3.0 files.
SUPPORTED_VERSIONS = [3]


def get_id3v2_info(fp: BinaryIO):
    fp.seek(0)

    identifier = fp.read(len(ID3v2_IDENTIFIER))
    if identifier != ID3v2_IDENTIFIER:
        raise ValueError("File does not contain an ID3v2 header.")

    major_version, revision = fp.read(ID3v2_VERSION_LENGTH)
    if major_version == 255 or revision == 255:
        raise ValueError("Encountered an invalid ID3v2 version.")

    flags = fp.read(IDv3_FLAGS_LENGTH)
    flags_bitstring = bin(flags[0])[2:].zfill(8)[:3]

    assert all(s == "0" or s == "1" for s in flags_bitstring)
    unsynchronisation, extended_header, experimental = (
        bool(int(i)) for i in flags_bitstring
    )

    # "The ID3v2 tag size is the size of the complete tag after
    # unsychronisation, including padding, excluding the header but not
    # excluding the extended header (total tag size - 10)."
    tag_size = 0
    for byte in fp.read(IDv3_SIZE_LENGTH):
        # Most significant bit must be 0 (each byte < $80 or 128)
        if byte > 128:
            raise ValueError("Encountered an invalid ID3v2 size.")
        tag_size += byte
        tag_size <<= 7
    # Account for final bit shift
    tag_size >>= 7

    return ID3v2Header(
        major_version=major_version,
        revision=revision,
        unsynchronisation=unsynchronisation,
        extended_header=extended_header,
        experimental=experimental,
        tag_size=tag_size,
    )


def strip_id3v2(
    in_fp: BinaryIO, id3v2_info, out_fp: BinaryIO, bufsize: int = io.DEFAULT_BUFFER_SIZE
):
    if id3v2_info.major_version not in SUPPORTED_VERSIONS:
        versions = "/".join(str(i) for i in SUPPORTED_VERSIONS)
        raise ValueError(
            f"Only ID3v2.[{versions}].0 tags are currently supported "
            f"(got ID3v2.{id3v2_info.major_version}.{id3v2_info.revision}"
        )
    if any(
        [
            id3v2_info.unsynchronisation,
            id3v2_info.extended_header,
            id3v2_info.experimental,
        ]
    ):
        raise ValueError(
            "Only blank ID3v2 flags (no flags set) are currently supported."
        )
    # Skip ahead of the ID3v2 data according to tag_size
    in_fp.seek(id3v2_info.tag_size, 1)
    # Start writing to output file
    buffer = in_fp.read(bufsize)
    bytes_written = 0
    while buffer:
        bytes_written += out_fp.write(buffer)
        buffer = in_fp.read(bufsize)
    return bytes_written


def main(args):
    in_fname = args[1]
    logging.debug(f"Input file: {in_fname}")

    try:
        out_fname = args[2]
    except IndexError:
        logging.warn(
            "No output file was specified. Falling back by adding a "
            "prefix to the input file."
        )
        out_fname = f"[STRIPPED] {in_fname}"
    logging.debug(f"Output file: {out_fname}")

    with open(in_fname, "rb") as in_f:
        with open(out_fname, "wb") as out_f:
            id3v2_info = get_id3v2_info(in_f)
            logging.info(f"Read ID3v2 header: {repr(id3v2_info)}")
            output = strip_id3v2(in_f, id3v2_info, out_f)
    return output


if __name__ == "__main__":
    import sys

    bytes_written = main(sys.argv)
    logging.debug(f"{bytes_written} bytes written")
