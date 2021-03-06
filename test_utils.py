#
# test_utils.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from xoshiro256 import Xoshiro256
from cbor_lite import CBOREncoder
from ur import UR

def make_message(length, seed = "Wolf"):
    rng = Xoshiro256.from_string(seed)
    return rng.next_data(length)

def make_message_ur(length, seed = "Wolf"):
    message = make_message(length, seed)
    encoder = CBOREncoder()
    encoder.encodeBytes(message)
    
    return UR("bytes", encoder.get_bytes())

