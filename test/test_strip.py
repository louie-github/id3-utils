#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import filecmp

# TODO: Import whole module once the scripts are properly packaged
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from strip_id3 import strip_id3  # noqa: E402

RESOURCES_DIR = Path(__file__).parent / "res"
V1_ONLY = RESOURCES_DIR / "v1-only.flac"
V1_ONLY_OUTPUT = RESOURCES_DIR / "v1-stripped-py.flac"
V2_ONLY = RESOURCES_DIR / "v2-only.flac"
V2_ONLY_OUTPUT = RESOURCES_DIR / "v2-stripped-py.flac"
V1_AND_V2 = RESOURCES_DIR / "v1-and-v2.flac"
V1_AND_V2_OUTPUT = RESOURCES_DIR / "v1-and-v2-stripped-py.flac"
V1_ONLY_STRIPPED = V2_ONLY_STRIPPED = V1_AND_V2_STRIPPED = (
    RESOURCES_DIR / "stripped.flac"
)


def strip_and_compare(input_file, output_file, reference_file):
    with open(input_file, "rb") as in_fp, open(output_file, "wb") as out_fp:
        strip_id3(in_fp, out_fp)
    return filecmp.cmp(output_file, reference_file, shallow=False)


class TestStrip(unittest.TestCase):
    def test_v1(self):
        self.assertTrue(
            strip_and_compare(
                input_file=V1_ONLY,
                output_file=V1_ONLY_OUTPUT,
                reference_file=V1_ONLY_STRIPPED,
            )
        )

    def test_v2(self):
        self.assertTrue(
            strip_and_compare(
                input_file=V2_ONLY,
                output_file=V2_ONLY_OUTPUT,
                reference_file=V2_ONLY_STRIPPED,
            )
        )

    def test_v1_and_v2(self):
        self.assertTrue(
            strip_and_compare(
                input_file=V1_AND_V2,
                output_file=V1_AND_V2_OUTPUT,
                reference_file=V1_AND_V2_STRIPPED,
            )
        )


if __name__ == "__main__":
    unittest.main()
