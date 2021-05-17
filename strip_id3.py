#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import logging

from collections import namedtuple
from pathlib import Path
from typing import BinaryIO

# TODO: Add support for ID3v1 tags.

# Based on the informal standard for ID3v2.3.0 found at:
# https://id3.org/id3v2.3.0
ID3v2_IDENTIFIER = b"ID3"
ID3v2_VERSION_LENGTH = 2
ID3v2_FLAGS_LENGTH = 1
ID3v2_SIZE_LENGTH = 4
ID3v2_HEADER_LENGTH = (
    len(ID3v2_IDENTIFIER)
    + ID3v2_VERSION_LENGTH
    + ID3v2_FLAGS_LENGTH
    + ID3v2_SIZE_LENGTH
)
assert ID3v2_HEADER_LENGTH == 10

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

# This script can currently only remove ID3v2.3.0 tags.
# I think the code can work with 2.4.0 too, but I'm not sure.
SUPPORTED_VERSIONS = [3]


def get_id3v2_info(data: bytes):
    fp = io.BytesIO(data)
    fp.seek(0)

    identifier = fp.read(len(ID3v2_IDENTIFIER))
    if identifier != ID3v2_IDENTIFIER:
        raise ValueError("File does not contain an ID3v2 header.")

    major_version, revision = fp.read(ID3v2_VERSION_LENGTH)
    # "Version and revision will never be $FF."
    if major_version == 255 or revision == 255:
        raise ValueError("Encountered an invalid ID3v2 version.")

    flags = fp.read(ID3v2_FLAGS_LENGTH)
    # bin the inner integer, then remove the '0b' prefix, then zfill
    flags_bitstring = bin(flags[0])[2:].zfill(8)
    assert all(s == "0" or s == "1" for s in flags_bitstring)

    other_flags = [
        7 - indx for indx, val in enumerate(flags_bitstring[3:]) if val == "1"
    ]
    if other_flags:
        logging.warning(
            "Some ID3v2 flags in the ID3v2 header were not cleared "
            f"(set to 0). Bits {repr(other_flags)} were set to 1."
        )
        logging.warning(
            "The ID3v2 tag data might not be readable to ordinary "
            "parsers, or might not conform to the relevant ID3v2 "
            "standard. The program recommends that you manually check "
            "the ID3v2 tags in the file using an external application "
            "(especially if said ID3v2 data is specific to that "
            "application) to make sure that you do not lose any "
            "important data."
        )
        logging.warning("The program will attempt to continue normally.")

    unsynchronisation, extended_header, experimental = (
        bool(int(i)) for i in flags_bitstring[:3]
    )

    # "The ID3v2 tag size is the size of the complete tag after
    # unsynchronisation, including padding, excluding the header but not
    # excluding the extended header (total tag size - 10)."
    tag_size = 0
    for byte in fp.read(ID3v2_SIZE_LENGTH):
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
    in_fp: BinaryIO, out_fp: BinaryIO, bufsize: int = io.DEFAULT_BUFFER_SIZE
):
    id3v2_header = in_fp.read(ID3v2_HEADER_LENGTH)
    id3v2_info = get_id3v2_info(id3v2_header)
    logging.info(
        f"Found and read a complete ID3v2 header (version 2."
        f"{id3v2_info.major_version}.{id3v2_info.revision})."
    )
    logging.debug(f"ID3v2 header information: {repr(id3v2_info)}")
    if id3v2_info.major_version not in SUPPORTED_VERSIONS:
        versions = "/".join(str(i) for i in SUPPORTED_VERSIONS)
        raise ValueError(
            f"Only ID3v2.[{versions}].0 tags are currently supported "
            f"(got ID3v2.{id3v2_info.major_version}.{id3v2_info.revision}"
        )
    # Skip ahead of the ID3v2 data according to tag_size
    logging.debug(
        "Reading input file and writing to output file starting at "
        f"offset {id3v2_info.tag_size + ID3v2_HEADER_LENGTH} bytes."
    )
    in_fp.seek(id3v2_info.tag_size, 1)
    # Start writing to output file
    buffer = in_fp.read(bufsize)
    bytes_written = 0
    while buffer:
        bytes_written += out_fp.write(buffer)
        buffer = in_fp.read(bufsize)
    return bytes_written


def _get_user_confirmation(message, default=False):
    if default is True or (
        isinstance(default, str) and default.strip().casefold() == "y"
    ):
        default = True
        suffix = "[Y]/N:"
    elif default is False or (
        isinstance(default, str) and default.strip().casefold() == "n"
    ):
        default = False
        suffix = "Y/[N]:"
    else:
        default = None
        suffix = "Y/N:"
    message = f"{message} {suffix} "
    valid_inputs = {"y", "n", ""} if default is not None else {"y", "n"}
    user_input = input(message).strip().casefold()
    while user_input not in valid_inputs:
        user_input = input(f"Invalid input. {message}").strip().casefold()

    if user_input == "y":
        ret = True
    elif user_input == "n":
        ret = False
    else:
        ret = default
    return ret


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
    if output_path.exists():
        if parsed_args.overwrite:
            logging.info(
                f"Overwriting output file {repr(output_path)} without"
                "user confirmation (--overwrite was specified)."
            )
        else:
            print(f"Output file already exists: {output_path}")
            user_confirmation = _get_user_confirmation(
                "Do you wish to overwrite the file?", default=False
            )
            if user_confirmation:
                logging.info(
                    f"Overwriting output file {repr(output_path)} "
                    "after user confirmation."
                )
            else:
                logging.info("Not overwriting output file, exiting.")
                raise SystemExit

    with open(input_path, "rb") as in_f:
        with open(output_path, "wb") as out_f:
            bytes_written = strip_id3v2(in_f, out_f)
    return bytes_written


if __name__ == "__main__":
    bytes_written = main()
    logging.info(f"Successfully wrote {bytes_written} bytes to output.")
