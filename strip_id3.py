#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import logging
import os
import shlex

from pathlib import Path
from typing import BinaryIO, NamedTuple, Tuple

# From: https://id3.org/ID3v1
ID3v1_IDENTIFIER = b"TAG"
ID3v1_LENGTH = 128

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

# This script can currently only remove ID3v2.3.0 tags.
# I think the code can work with 2.4.0 too, but I'm not sure.
SUPPORTED_VERSIONS = [3]


class ID3v2Header(NamedTuple):
    major_version: int
    revision: int
    unsynchronisation: bool
    extended_header: bool
    experimental: bool
    other_flags: Tuple[int, ...]
    tag_size: int


class ID3v2HeaderError(ValueError):
    """A class to help differentiate ID3v2 header parsing errors from
    regular ValueErrors."""

    pass


def read_id3v2_header(fp: BinaryIO):
    old_position = fp.tell()
    fp.seek(0)

    identifier = fp.read(len(ID3v2_IDENTIFIER))
    if identifier != ID3v2_IDENTIFIER:
        raise ID3v2HeaderError("File does not contain an ID3v2 header.")

    major_version, revision = fp.read(ID3v2_VERSION_LENGTH)
    # "Version and revision will never be $FF."
    if major_version == 255 or revision == 255:
        raise ID3v2HeaderError("Encountered an invalid ID3v2 version.")

    flags = fp.read(ID3v2_FLAGS_LENGTH)
    # bin the inner integer, then remove the '0b' prefix, then zfill
    flags_bitstring = bin(flags[0])[2:].zfill(8)
    assert all(s == "0" or s == "1" for s in flags_bitstring)

    other_flags = tuple(int(i) for i in flags_bitstring[3:])
    if any(other_flags):
        logging.warning(
            "Some ID3v2 flags in the ID3v2 header are not cleared or "
            f"set to 0 (Other flags: {other_flags})"
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
            raise ID3v2HeaderError("Encountered an invalid ID3v2 size.")
        tag_size += byte
        tag_size <<= 7
    # Account for final bit shift
    tag_size >>= 7

    fp.seek(old_position)
    return ID3v2Header(
        major_version=major_version,
        revision=revision,
        unsynchronisation=unsynchronisation,
        extended_header=extended_header,
        experimental=experimental,
        other_flags=other_flags,
        tag_size=tag_size,
    )


def check_id3v1(fp: BinaryIO):
    old_position = fp.tell()
    offset = fp.seek(-ID3v1_LENGTH, os.SEEK_END)
    id3v1_identifier = fp.read(3)
    fp.seek(old_position)
    return (id3v1_identifier == ID3v1_IDENTIFIER, offset)


def strip_id3(in_fp: BinaryIO, out_fp: BinaryIO, bufsize: int = io.DEFAULT_BUFFER_SIZE):
    try:
        id3v2_header = read_id3v2_header(in_fp)
    except ID3v2HeaderError as err:
        has_id3v2 = False
        logging.debug(f"Error while searching for ID3v2 header: {err}")
    else:
        has_id3v2 = True

    if has_id3v2:
        logging.info(
            f"Found and read a complete ID3v2 header (version 2."
            f"{id3v2_header.major_version}.{id3v2_header.revision})."
        )
        logging.debug(f"ID3v2 header information: {repr(id3v2_header)}")
        if id3v2_header.major_version not in SUPPORTED_VERSIONS:
            versions = "/".join(str(i) for i in SUPPORTED_VERSIONS)
            raise ValueError(
                f"Only ID3v2.[{versions}].0 tags are currently "
                f"supported (got ID3v2.{id3v2_header.major_version}."
                f"{id3v2_header.revision}"
            )
        start_position = in_fp.seek(id3v2_header.tag_size + ID3v2_HEADER_LENGTH)
        assert start_position == (id3v2_header.tag_size + ID3v2_HEADER_LENGTH)
    else:
        logging.info("Could not find a valid ID3v2 header.")
        start_position = 0

    has_id3v1, end_position = check_id3v1(in_fp)
    if has_id3v1:
        logging.info("Found ID3v1 tag data.")
    else:
        logging.info("Could not find ID3v1 tag data.")

    # TODO: Add option not to error out here.
    if not (has_id3v1 or has_id3v2):
        raise ValueError("File does not contain either ID3v1 or ID3v2 metadata.")

    if has_id3v1:
        logging.debug(
            "Reading input file and writing to output file starting at "
            f"offset {start_position:_} bytes until {end_position:_} "
            "bytes."
        )
        # Write from start_offset until end_offset
        in_fp.seek(start_position)
        bytes_to_write = end_position - start_position
        buffer_cycles, last_bufsize = divmod(bytes_to_write, bufsize)
        cycles = 0
        bytes_written = 0
        while cycles < buffer_cycles:
            bytes_written += out_fp.write(in_fp.read(bufsize))
            cycles += 1
        else:
            bytes_written += out_fp.write(in_fp.read(last_bufsize))
    else:
        logging.debug(
            "Reading input file and writing to output file starting "
            f"at position {start_position} bytes until the end of the "
            "file."
        )
        # Write from start_offset until end of file
        in_fp.seek(start_position)
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

    quote = shlex.quote
    in_path = Path(parsed_args.input_file)
    logging.info(f"Input file: {quote(str(in_path))}")
    out_path = parsed_args.output_file
    if out_path is None:
        logging.warning(
            "No output file was specified. Falling back to adding a "
            "prefix to the input file."
        )
        out_path = in_path.parent / f"[STRIPPED] {in_path.name}"
    else:
        out_path = Path(out_path)
    logging.info(f"Output file: {quote(str(out_path))}")
    if out_path.exists():
        if parsed_args.overwrite:
            logging.info(
                f"Overwriting output file {quote(str(out_path))} "
                'without user confirmation. ("--overwrite" was '
                "specified)"
            )
        else:
            print(f"Output file already exists: {quote(str(out_path))}")
            user_confirmation = _get_user_confirmation(
                "Do you want to overwrite the file?", default=False
            )
            if user_confirmation:
                logging.info(
                    f"Overwriting output file {quote(str(out_path))} "
                    "after user confirmation."
                )
            else:
                logging.error("Not overwriting output file, exiting.")
                # EX_CANTCREAT: can't create (user) output file
                raise SystemExit(73)

    with open(in_path, "rb") as in_f:
        with open(out_path, "wb") as out_f:
            bytes_written = strip_id3(in_f, out_f)
    return bytes_written


if __name__ == "__main__":
    bytes_written = main()
    logging.info(f"Successfully wrote {bytes_written:_} bytes to output.")
