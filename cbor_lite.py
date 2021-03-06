#
# crc32.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

# From: https://bitbucket.org/isode/cbor-lite/raw/6c770624a97e3229e3f200be092c1b9c70a60ef1/include/cbor-lite/codec.h

# This file is part of CBOR-lite which is copyright Isode Limited
# and others and released under a MIT license. For details, see the
# COPYRIGHT.md file in the top-level folder of the CBOR-lite software
# distribution.

from enum import Enum
from utils import dotdict

Flag = dotdict({
    'none' : 0,
    'requireMinimalEncoding' : 1 << 0
})    


Tag = dotdict({
    'Major': dotdict(
        {
            'unsignedInteger': 0,
            'negativeInteger' : 1 << 5,
            'byteString' : 2 << 5,
            'textString' : 3 << 5,
            'array' : 4 << 5,
            'map' : 5 << 5,
            'semantic' : 6 << 5,
            'floatingPoint' : 7 << 5,
            'simple' : 7 << 5,
            'mask' : 0xe0,
        }
    ),
    'Minor': dotdict(
        {
            'length1' : 24,
            'length2' : 25,
            'length4' : 26,
            'length8' : 27,

            'false' : 20,
            'true' : 21,
            'null' : 22,
            'undefined' : 23,
            'halfFloat' : 25, # not implemented
            'singleFloat' : 26,
            'doubleFloat' : 27,

            'dataTime' : 0,
            'epochDataTime' : 1,
            'positiveBignum' : 2,
            'negativeBignum' : 3,
            'decimalFraction' : 4,
            'bigfloat' : 5,
            'convertBase64Url' : 21,
            'convertBase64' : 22,
            'convertBase16' : 23,
            'cborEncodedData' : 24,
            'uri' : 32,
            'base64Url' : 33,
            'base64' : 34,
            'regex' : 35,
            'mimeMessage' : 36,
            'selfDescribeCbor' : 55799,
            'mask' : 0x1f
        }
    ),
    'undefined': (6 << 5) + 23
})

class TagMisc(Enum):
    undefined = Tag.Major.semantic + Tag.Minor.undefined

def get_byte_length(value):
    if value < 24:
        return 0
    
    return (value.bit_length() + 7) // 8

class CBOREncoder:
    def __init__(self):
        self.buf = bytearray()

    def get_bytes(self):
        return self.buf

    def encodeTagAndAdditional(self, tag, additional):
        self.buf.append(tag + additional)
        return 1

    def encodeTagAndValue(self, tag, value):
        length = get_byte_length(value)

        # 5-8 bytes required, use 8 bytes
        if length >= 5 and length <= 8:
            self.encodeTagAndAdditional(tag, Tag.Minor.length8)
            self.buf.append((value >> 56) & 0xff)
            self.buf.append((value >> 48) & 0xff)
            self.buf.append((value >> 40) & 0xff)
            self.buf.append((value >> 32) & 0xff)
            self.buf.append((value >> 24) & 0xff)
            self.buf.append((value >> 16) & 0xff)
            self.buf.append((value >> 8) & 0xff)
            self.buf.append(value & 0xff)

        # 3-4 bytes required, use 4 bytes
        elif length == 3 or length == 4:
            self.encodeTagAndAdditional(tag, Tag.Minor.length4)
            self.buf.append((value >> 24) & 0xff)
            self.buf.append((value >> 16) & 0xff)
            self.buf.append((value >> 8) & 0xff)
            self.buf.append(value & 0xff)

        elif length == 2:
            self.encodeTagAndAdditional(tag, Tag.Minor.length2)
            self.buf.append((value >> 8) & 0xff)
            self.buf.append(value & 0xff)

        elif length == 1:
            self.encodeTagAndAdditional(tag, Tag.Minor.length1)
            self.buf.append(value & 0xff)

        elif length == 0:
            self.encodeTagAndAdditional(tag, value)

        else:
            raise Exception("Unsupported byte length of {} for value in encodeTagAndValue()".format(length))

        encoded_size = 1 + length
        return encoded_size

    def encodeUnsigned(self, value):
        return self.encodeTagAndValue(Tag.Major.unsignedInteger, value)

    def encodeNegative(self, value):
        return self.encodeTagAndValue(Tag.Major.negativeInteger, value)

    def encodeInteger(self, value):
        if value >= 0:
            return self.encodeUnsigned(value)
        else:
            return self.encodeNegative(value)

    def encodeBool(self, value):
        return self.encodeTagAndValue(Tag.Major.simple, Tag.Minor.true if value else Tag.Minor.false)

    def encodeBytes(self, value):
        length = self.encodeTagAndValue(Tag.Major.byteString, len(value))
        self.buf += value
        return length + len(value)

    def encodeEncodedBytesPrefix(self, value):
        length = self.encodeTagAndValue(Tag.Major.semantic, Tag.Minor.cborEncodedData)
        return length + self.encodeTagAndAdditional

    def encodeEncodedBytes(self, value):
        length = self.encodeTagAndValue(Tag.Major.semantic, Tag.Minor.cborEncodedData)
        return length + self.encodeBytes(value)

    def encodeText(self, value):
        str_len = len(value)
        length = self.encodeTagAndValue(Tag.Major.textString, str_len)
        self.buf.append(bytes(value, 'utf8'))
        return length + str_len

    def encodeArraySize(self, value):
        return self.encodeTagAndValue(Tag.Major.array, value)

    def encodeMapSize(self, value):
        return self.encodeTagAndValue(Tag.Major.map, value)


class CBORDecoder:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0

    def decodeTagAndAdditional(self, flags=Flag.none):
        if self.pos == len(self.buf):
            raise Exception("Not enough input")
        octet = self.buf[self.pos]
        self.pos += 1
        tag = octet & Tag.Major.mask
        additional = octet & Tag.Minor.mask
        return (tag, additional, 1)

    def decodeTagAndValue(self, flags):
        end = len(self.buf)

        if self.pos == end:
            raise Exception("Not enough input")        

        (tag, additional, length) = self.decodeTagAndAdditional(flags)
        if additional < Tag.Minor.length1:
            value = additional
            return (tag, value, length)

        value = 0
        if additional == Tag.Minor.length8:
            if end - self.pos < 8:
                raise Exception("Not enough input")            
            for shift in [56, 48, 40, 32, 24, 16, 8, 0]:
                value |= self.buf[self.pos] << shift
                self.pos += 1
            if ((flags & Flag.requireMinimalEncoding) and value == 0):
                raise Exception("Encoding not minimal")
            return (tag, value, self.pos)
        elif additional == Tag.Minor.length4:
            if end - self.pos < 4:
                raise Exception("Not enough input")            
            for shift in [24, 16, 8, 0]:
                value |= self.buf[self.pos] << shift
                self.pos += 1
            if ((flags & Flag.requireMinimalEncoding) and value == 0):
                raise Exception("Encoding not minimal")
            return (tag, value, self.pos)
        elif additional == Tag.Minor.length2:
            if end - self.pos < 2:
                raise Exception("Not enough input")            
            for shift in [8, 0]:
                value |= self.buf[self.pos] << shift
                self.pos += 1
            if ((flags & Flag.requireMinimalEncoding) and value == 0):
                raise Exception("Encoding not minimal")
            return (tag, value, self.pos)
        elif additional == Tag.Minor.length1:
            if end - self.pos < 1:
                raise Exception("Not enough input")            
            value |= self.buf[self.pos]
            self.pos += 1
            if ((flags & Flag.requireMinimalEncoding) and value == 0):
                raise Exception("Encoding not minimal")
            return (tag, value, self.pos)

        raise Exception("Bad additional value")

    def decodeUnsigned(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.unsignedInteger:
            raise Exception("Expected Tag.Major.unsignedInteger ({}), but found {}".format(Tag.Major.unsignedInteger, tag))
        return (value, length)

    def decodeNegative(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.negativeInteger:
            raise Exception("Expected Tag.Major.negativeInteger, but found {}".format(tag))
        return (value, length)

    def decodeInteger(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)
        if tag == Tag.Major.unsignedInteger:
            return (value, length)
        elif tag == Tag.Major.negativeInteger:
            return (-1 - value, length)  # TODO: Check that this is the right way -- do we need to use struct.unpack()?

    def decodeBool(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)
        if tag == Tag.Major.simple:
            if value == Tag.Minor.true:
                return (True, length)
            elif value == Tag.Minor.false:
                return (False, length)
            raise Exception("Not a Boolean")
        raise Exception("Not Simple/Boolean")

    def decodeBytes(self, flags=Flag.none):
        # First value is the length of the bytes that follow
        (tag, byte_length, size_length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.byteString:
            raise Exception("Not a byteString")

        end = len(self.buf)
        if end - self.pos < byte_length:
            raise Exception("Not enough input")

        value = bytes(self.buf[self.pos : self.pos + byte_length])
        self.pos += byte_length
        return (value, size_length + byte_length)

    def decodeEncodedBytesPrefix(self, flags=Flag.none):
        (tag, value, length1) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.semantic or value != Tag.Minor.cborEncodedData:
            raise Exception("Not CBOR Encoded Data")

        (tag, value, length2) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.byteString:
            raise Exception("Not byteString")

        return (tag, value, length1 + length2)

    def decodeEncodedBytes(self, flags=Flag.none):
        (tag, minor_tag, tag_length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.semantic or minor_tag != Tag.Minor.cborEncodedData:
            raise Exception("Not CBOR Encoded Data")

        (value, length) = self.decodeBytes(flags)
        return (value, tag_length + length)

    def decodeText(self, flags=Flag.none):
        # First value is the length of the bytes that follow
        (tag, byte_length, size_length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.textString:
            raise Exception("Not a textString")

        end = len(self.buf)
        if end - self.pos < byte_length:
            raise Exception("Not enough input")

        value = bytes(self.buf[self.pos : self.pos + byte_length])
        self.pos += byte_length
        return (value, size_length + byte_length)

    def decodeArraySize(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)

        if tag != Tag.Major.array:
            raise Exception("Expected Tag.Major.array, but found {}".format(tag))
        return (value, length)

    def decodeMapSize(self, flags=Flag.none):
        (tag, value, length) = self.decodeTagAndValue(flags)
        if tag != Tag.Major.mask:
            raise Exception("Expected Tag.Major.map, but found {}".format(tag))
        return (value, length)
