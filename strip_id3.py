#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import logging

from collections import namedtuple
from pathlib import Path
from typing import BinaryIO


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
    logging.debug(f"Reading the file starting at offset {id3v2_info.tag_size} bytes.")
    in_fp.seek(id3v2_info.tag_size, 1)
    # Start writing to output file
    buffer = in_fp.read(bufsize)
    bytes_written = 0
    while buffer:
        bytes_written += out_fp.write(buffer)
        buffer = in_fp.read(bufsize)
    return bytes_written


def main(args=None):
    parser = argparse.ArgumentParser(description="Strip ID3v2 metadata from a file.")
    parser.add_argument(
        "-v",
        "--verbose",
        help="Enable verbose output (useful for debugging)",
        action="store_true",
        dest="verbose",
    )
    parser.add_argument(
        "-f",
        "--overwrite",
        help="Overwrite output files if they already exist.",
        action="store_true",
        dest="overwrite",
    )
    parser.add_argument(
        "input_file",
        help="The name of the file to strip the metadata from. ",
    )
    parser.add_argument(
        "output_file",
        help="The name of the file to which the data will be written.",
        nargs="?",
        default=None,
    )
    if args is not None:
        parsed_args = parser.parse_args(args)
    else:
        parsed_args = parser.parse_args()

    if parsed_args.verbose:
        logging.basicConfig(
            level=logging.DEBUG, format="[{levelname}] {message}", style="{"
        )
    else:
        logging.basicConfig(
            level=logging.INFO, format="[{levelname}] {message}", style="{"
        )

    input_path = Path(parsed_args.input_file)
    logging.info(f"Input file: {input_path}")
    output_path = parsed_args.output_file
    if output_path is None:
        logging.warning(
            "No output file was specified. Falling back to adding a "
            "prefix to the input file."
        )
        output_path = input_path.parent / f"[STRIPPED] {input_path.name}"
    else:
        output_path = Path(output_path)
    logging.info(f"Output file: {output_path}")

    with open(input_path, "rb") as in_f:
        with open(output_path, "wb") as out_f:
            id3v2_info = get_id3v2_info(in_f)
            logging.debug(f"Read ID3v2 header: {repr(id3v2_info)}")
            logging.info(
                "Found an ID3v2 header (version 2."
                f"{id3v2_info.major_version}.{id3v2_info.revision})."
            )
            bytes_written = strip_id3v2(in_f, id3v2_info, out_f)
    return bytes_written


if __name__ == "__main__":
    bytes_written = main()
    logging.info(f"Successfully wrote {bytes_written} bytes to output.")
