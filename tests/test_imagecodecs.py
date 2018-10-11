# -*- coding: utf-8 -*-
# test_imagecodecs.py

# Copyright (c) 2018, Christoph Gohlke
# Copyright (c) 2018, The Regents of the University of California
# Produced at the Laboratory for Fluorescence Dynamics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of the copyright holders nor the names of any
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""Unittests for the imagecodecs package.

:Author:
  `Christoph Gohlke <https://www.lfd.uci.edu/~gohlke/>`_

:Organization:
  Laboratory for Fluorescence Dynamics. University of California, Irvine

:Version: 2018.10.10

"""

from __future__ import division, print_function

import os
import sys
import glob

import pytest
import numpy
from numpy.testing import assert_array_equal, assert_allclose

import imagecodecs
import imagecodecs.imagecodecs as imagecodecs_py

from imagecodecs.imagecodecs import lzma, zlib, bz2, zstd, lz4, lzf

try:
    from imagecodecs import _imagecodecs  # noqa
except ImportError:
    pytest.exit('the _imagecodec Cython extension module could not be found')


def test_version():
    # assert imagecodecs versions match docstrings
    from imagecodecs import __version__, version

    ver = ':Version: ' + __version__
    assert ver in __doc__
    assert ver in imagecodecs.__doc__
    assert ver in imagecodecs_py.__doc__

    assert version().startswith('imagecodecs-')
    assert version(dict)['zlib'].startswith('1.')


def test_none():
    from imagecodecs import none_encode as encode
    from imagecodecs import none_decode as decode
    data = b'None'
    assert encode(data) is data
    assert decode(data) is data


def test_bitorder():
    from imagecodecs import bitorder_encode as encode  # noqa
    from imagecodecs import bitorder_decode as decode

    data = b'\x01\x00\x9a\x02'
    reverse = b'\x80\x00Y@'
    # return new string
    assert decode(data) == reverse
    assert data == b'\x01\x00\x9a\x02'
    # provide output
    out = bytearray(len(data))
    decode(data, out=out)
    assert out == reverse
    assert data == b'\x01\x00\x9a\x02'
    # inplace
    decode(data, out=data)
    assert data == reverse
    # bytes range
    assert BYTES == decode(readfile('bytes.bitorder.bin'))


def test_bitorder_ndarray():
    from imagecodecs import bitorder_encode as encode  # noqa
    from imagecodecs import bitorder_decode as decode

    data = numpy.array([1, 666], dtype='uint16')
    reverse = numpy.array([128, 16473], dtype='uint16')
    # return new array
    assert_array_equal(decode(data), reverse)
    # inplace
    decode(data, out=data)
    assert_array_equal(data, numpy.array([128, 16473], dtype='uint16'))
    # array view
    data = numpy.array([[1, 666, 1431655765, 62],
                        [2, 667, 2863311530, 32],
                        [3, 668, 1431655765, 30]], dtype='uint32')
    reverse = numpy.array([[1, 666, 1431655765, 62],
                           [2, 16601, 1431655765, 32],
                           [3, 16441, 2863311530, 30]], dtype='uint32')
    assert_array_equal(decode(data[1:, 1:3]), reverse[1:, 1:3])
    # array view inplace
    decode(data[1:, 1:3], out=data[1:, 1:3])
    assert_array_equal(data, reverse)


def test_packints_decode():
    from imagecodecs import packints_decode as decode

    decoded = decode(b'', 'B', 1)
    assert len(decoded) == 0

    decoded = decode(b'a', 'B', 1)
    assert tuple(decoded) == (0, 1, 1, 0, 0, 0, 0, 1)

    decoded = decode(b'ab', 'B', 2)
    assert tuple(decoded) == (1, 2, 0, 1, 1, 2, 0, 2)

    decoded = decode(b'abcd', 'B', 3)
    assert tuple(decoded) == (3, 0, 2, 6, 1, 1, 4, 3, 3, 1)

    decoded = decode(numpy.frombuffer(b'abcd', dtype='uint8'), 'B', 3)
    assert tuple(decoded) == (3, 0, 2, 6, 1, 1, 4, 3, 3, 1)


PACKBITS_DATA = [
    (b'', b''),
    (b'X', b'\x00X'),
    (b'123', b'\x02123'),
    (b'112112', b'\xff1\x002\xff1\x002'),
    (b'1122', b'\xff1\xff2'),
    (b'1' * 126, b'\x831'),
    (b'1' * 127, b'\x821'),
    (b'1' * 128, b'\x811'),
    (b'1' * 127 + b'foo', b'\x821\x00f\xffo'),
    (b'12345678' * 16,  # literal 128
     b'\x7f1234567812345678123456781234567812345678123456781234567812345678'
     b'1234567812345678123456781234567812345678123456781234567812345678'),
    (b'12345678' * 17,
     b'~1234567812345678123456781234567812345678123456781234567812345678'
     b'123456781234567812345678123456781234567812345678123456781234567\x08'
     b'812345678'),
    (b'1' * 128 + b'12345678' * 17,
     b'\x821\xff1~2345678123456781234567812345678123456781234567812345678'
     b'1234567812345678123456781234567812345678123456781234567812345678'
     b'12345678\x0712345678'),
    (b'\xaa\xaa\xaa\x80\x00\x2a\xaa\xaa\xaa\xaa\x80\x00'
     b'\x2a\x22\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa',
     b'\xfe\xaa\x02\x80\x00\x2a\xfd\xaa\x03\x80\x00\x2a\x22\xf7\xaa')]


@pytest.mark.parametrize('data', range(len(PACKBITS_DATA)))
@pytest.mark.parametrize('codec', ['encode', 'decode'])
def test_packbits(codec, data):
    from imagecodecs import packbits_encode as encode
    from imagecodecs import packbits_decode as decode
    uncompressed, compressed = PACKBITS_DATA[data]
    if codec == 'decode':
        assert decode(compressed) == uncompressed
    elif codec == 'encode':
        try:
            assert encode(uncompressed) == compressed
        except AssertionError:
            # roundtrip
            assert decode(encode(uncompressed)) == uncompressed


def test_packbits_nop():
    from imagecodecs import packbits_decode as decode
    assert decode(b'\x80') == b''
    assert decode(b'\x80\x80') == b''


@pytest.mark.parametrize('output', [None, 'array'])
@pytest.mark.parametrize('codec', ['encode', 'decode'])
def test_packbits_array(codec, output):
    from imagecodecs import packbits_encode as encode
    from imagecodecs import packbits_decode as decode
    uncompressed, compressed = PACKBITS_DATA[-1]
    shape = (2, 7, len(uncompressed))
    data = numpy.empty(shape, dtype='uint8')
    data[..., :] = numpy.frombuffer(uncompressed, dtype='uint8')
    compressed = compressed * (shape[0] * shape[1])
    if codec == 'encode':
        if output == 'array':
            out = numpy.empty(data.size, data.dtype)
            assert_array_equal(encode(data, out=out),
                               numpy.frombuffer(compressed, dtype='uint8'))
        else:
            assert encode(data) == compressed
    else:
        if output == 'array':
            out = numpy.empty(data.size, data.dtype)
            assert_array_equal(decode(compressed, out=out), data.flat)
        else:
            assert decode(compressed) == data.tobytes()


@pytest.mark.parametrize('output', ['new', 'out', 'inplace'])
@pytest.mark.parametrize('codec', ['encode', 'decode'])
@pytest.mark.parametrize(
    'kind', ['u1', 'u2', 'u4', 'u8', 'i1', 'i2', 'i4', 'i8', 'f4', 'f8', 'B',
             pytest.param('b', marks=pytest.mark.skipif(
                 sys.version_info[0] == 2, reason='Python 2'))])
@pytest.mark.parametrize('func', ['delta', 'xor'])
def test_delta(output, kind, codec, func):
    if func == 'delta':
        from imagecodecs import delta_encode as encode
        from imagecodecs import delta_decode as decode
        from imagecodecs.imagecodecs import delta_encode as encode_py
        from imagecodecs.imagecodecs import delta_decode as decode_py
    elif func == 'xor':
        from imagecodecs import xor_encode as encode
        from imagecodecs import xor_decode as decode
        from imagecodecs.imagecodecs import xor_encode as encode_py
        from imagecodecs.imagecodecs import xor_decode as decode_py

    bytetype = bytearray
    if kind == 'b':
        bytetype = bytes
        kind = 'B'

    axis = -2  # do not change
    dtype = numpy.dtype(kind)
    if kind[0] in 'iuB':
        low = numpy.iinfo(dtype).min
        high = numpy.iinfo(dtype).max
        data = numpy.random.randint(low, high, size=33*31*3,
                                    dtype=dtype).reshape(33, 31, 3)
    else:
        low, high = -1e5, 1e5
        data = numpy.random.randint(low, high, size=33*31*3,
                                    dtype='i4').reshape(33, 31, 3)
        data = data.astype(dtype)

    data[16, 14] = [0, 0, 0]
    data[16, 15] = [low, high, low]
    data[16, 16] = [high, low, high]
    data[16, 17] = [low, high, low]
    data[16, 18] = [high, low, high]
    data[16, 19] = [0, 0, 0]

    if kind == 'B':
        # data = data.reshape(-1)
        data = data.tostring()
        diff = encode_py(data, axis=0)
        if output == 'new':
            if codec == 'encode':
                encoded = encode(data, out=bytetype)
                assert encoded == diff
            elif codec == 'decode':
                decoded = decode(diff, out=bytetype)
                assert decoded == data
        elif output == 'out':
            if codec == 'encode':
                encoded = bytetype(len(data))
                encode(data, out=encoded)
                assert encoded == diff
            elif codec == 'decode':
                decoded = bytetype(len(data))
                decode(diff, out=decoded)
                assert decoded == data
        elif output == 'inplace':
            if codec == 'encode':
                encoded = bytetype(data)
                encode(encoded, out=encoded)
                assert encoded == diff
            elif codec == 'decode':
                decoded = bytetype(diff)
                decode(decoded, out=decoded)
                assert decoded == data
    else:
        # if func == 'xor' and kind in ('f4', 'f8'):
        #      with pytest.raises(ValueError):
        #          encode(data, axis=axis)
        #      pytest.skip("XOR codec not implemented for float data")
        diff = encode_py(data, axis=-2)

        if output == 'new':
            if codec == 'encode':
                encoded = encode(data, axis=axis)
                assert_array_equal(encoded, diff)
            elif codec == 'decode':
                decoded = decode(diff, axis=axis)
                assert_array_equal(decoded, data)
        elif output == 'out':
            if codec == 'encode':
                encoded = numpy.zeros_like(data)
                encode(data, axis=axis, out=encoded)
                assert_array_equal(encoded, diff)
            elif codec == 'decode':
                decoded = numpy.zeros_like(data)
                decode(diff, axis=axis, out=decoded)
                assert_array_equal(decoded, data)
        elif output == 'inplace':
            if codec == 'encode':
                encoded = data.copy()
                encode(encoded, axis=axis, out=encoded)
                assert_array_equal(encoded, diff)
            elif codec == 'decode':
                decoded = diff.copy()
                decode(decoded, axis=axis, out=decoded)
                assert_array_equal(decoded, data)


@pytest.mark.parametrize('output', ['new', 'out'])
@pytest.mark.parametrize('codec', ['encode', 'decode'])
@pytest.mark.parametrize('endian', ['le', 'be'])
@pytest.mark.parametrize('planar', ['rgb', 'rrggbb'])
def test_floatpred(planar, endian, output, codec):
    from imagecodecs import floatpred_encode as encode
    from imagecodecs import floatpred_decode as decode

    data = numpy.fromfile(
        datafiles('rgb.bin'), dtype='<f4').reshape(33, 31, 3)

    if planar == 'rgb':
        axis = -2
        if endian == 'le':
            encoded = numpy.fromfile(
                datafiles('rgb.floatpred_le.bin'), dtype='<f4')
            encoded = encoded.reshape(33, 31, 3)
            if output == 'new':
                if codec == 'decode':
                    assert_array_equal(decode(encoded, axis=axis), data)
                elif codec == 'encode':
                    assert_array_equal(encode(data, axis=axis), encoded)
            elif output == 'out':
                out = numpy.empty_like(data)
                if codec == 'decode':
                    decode(encoded, axis=axis, out=out)
                    assert_array_equal(out, data)
                elif codec == 'encode':
                    out = numpy.empty_like(data)
                    encode(data, axis=axis, out=out)
                    assert_array_equal(out, encoded)
        elif endian == 'be':
            data = data.astype('>f4')
            encoded = numpy.fromfile(
                datafiles('rgb.floatpred_be.bin'), dtype='>f4')
            encoded = encoded.reshape(33, 31, 3)
            if output == 'new':
                if codec == 'decode':
                    assert_array_equal(decode(encoded, axis=axis), data)
                elif codec == 'encode':
                    assert_array_equal(encode(data, axis=axis), encoded)
            elif output == 'out':
                out = numpy.empty_like(data)
                if codec == 'decode':
                    decode(encoded, axis=axis, out=out)
                    assert_array_equal(out, data)
                elif codec == 'encode':
                    out = numpy.empty_like(data)
                    encode(data, axis=axis, out=out)
                    assert_array_equal(out, encoded)
    elif planar == 'rrggbb':
        axis = -1
        data = numpy.ascontiguousarray(numpy.moveaxis(data, 2, 0))
        if endian == 'le':
            encoded = numpy.fromfile(
                datafiles('rrggbb.floatpred_le.bin'), dtype='<f4')
            encoded = encoded.reshape(3, 33, 31)
            if output == 'new':
                if codec == 'decode':
                    assert_array_equal(decode(encoded, axis=axis), data)
                elif codec == 'encode':
                    assert_array_equal(encode(data, axis=axis), encoded)
            elif output == 'out':
                out = numpy.empty_like(data)
                if codec == 'decode':
                    decode(encoded, axis=axis, out=out)
                    assert_array_equal(out, data)
                elif codec == 'encode':
                    out = numpy.empty_like(data)
                    encode(data, axis=axis, out=out)
                    assert_array_equal(out, encoded)
        elif endian == 'be':
            data = data.astype('>f4')
            encoded = numpy.fromfile(
                datafiles('rrggbb.floatpred_be.bin'), dtype='>f4')
            encoded = encoded.reshape(3, 33, 31)
            if output == 'new':
                if codec == 'decode':
                    assert_array_equal(decode(encoded, axis=axis), data)
                elif codec == 'encode':
                    assert_array_equal(encode(data, axis=axis), encoded)
            elif output == 'out':
                out = numpy.empty_like(data)
                if codec == 'decode':
                    decode(encoded, axis=axis, out=out)
                    assert_array_equal(out, data)
                elif codec == 'encode':
                    out = numpy.empty_like(data)
                    encode(data, axis=axis, out=out)
                    assert_array_equal(out, encoded)


@pytest.mark.parametrize('output', ['new', 'out', 'size', 'excess', 'trunc'])
@pytest.mark.parametrize('length', [0, 2, 31*33*3])
@pytest.mark.parametrize('codec', ['encode', 'decode'])
@pytest.mark.parametrize('module', [
    'zlib', 'bz2',
    pytest.param('lzma', marks=pytest.mark.skipif(lzma is None,
                                                  reason='import lzma')),
    pytest.param('zstd', marks=pytest.mark.skipif(zstd is None,
                                                  reason='import zstd')),
    pytest.param('lzf', marks=pytest.mark.skipif(lzf is None,
                                                 reason='import lzf')),
    pytest.param('lz4', marks=pytest.mark.skipif(lz4 is None,
                                                 reason='import lz4')),
    pytest.param('lz4h', marks=pytest.mark.skipif(lz4 is None,
                                                  reason='import lz4'))])
def test_compressors(module, codec, output, length):
    if length:
        data = numpy.random.randint(255, size=length, dtype='uint8').tostring()
    else:
        data = b''

    if module == 'zlib':
        from imagecodecs import zlib_encode as encode
        from imagecodecs import zlib_decode as decode
        level = 5
        encoded = zlib.compress(data, level)
    elif module == 'lzma':
        from imagecodecs import lzma_encode as encode
        from imagecodecs import lzma_decode as decode
        level = 6
        encoded = lzma.compress(data)
    elif module == 'zstd':
        from imagecodecs import zstd_encode as encode
        from imagecodecs import zstd_decode as decode
        level = 5
        if length == 0:
            # bug in zstd.compress?
            encoded = encode(data, level)
        else:
            encoded = zstd.compress(data, level)
    elif module == 'lzf':
        from imagecodecs import lzf_encode as encode
        from imagecodecs import lzf_decode as decode
        level = 1
        encoded = lzf.compress(data)
        if encoded is None:
            pytest.skip("lzf can't compress empty input")
    elif module == 'lz4':
        from imagecodecs import lz4_encode as encode
        from imagecodecs import lz4_decode as decode
        level = 1
        encoded = lz4.block.compress(data, store_size=False)
    elif module == 'lz4h':
        from imagecodecs import lz4_encode
        from imagecodecs import lz4_decode

        def encode(*args, **kwargs):
            return lz4_encode(*args, header=True, **kwargs)

        def decode(*args, **kwargs):
            return lz4_decode(*args, header=True, **kwargs)

        level = 1
        encoded = lz4.block.compress(data, store_size=True)
    elif module == 'bz2':
        from imagecodecs import bz2_encode as encode
        from imagecodecs import bz2_decode as decode
        level = 9
        encoded = bz2.compress(data, compresslevel=level)
    else:
        raise ValueError(module)

    if codec == 'encode':
        size = len(encoded)
        if output == 'new':
            assert encoded == encode(data, level)
        elif output == 'size':
            ret = encode(data, level, out=size)
            assert encoded == ret
        elif output == 'out':
            if module == 'zstd':
                out = bytearray(max(size, 64))
            elif module == 'lzf':
                out = bytearray(size + 1)  # bug in liblzf ?
            else:
                out = bytearray(size)
            ret = encode(data, level, out=out)
            assert encoded == out[:size]
            assert encoded == ret
        elif output == 'excess':
            out = bytearray(size + 1021)
            ret = encode(data, level, out=out)
            assert encoded == out[:size]
            assert encoded == ret
        elif output == 'trunc':
            size = max(0, size - 1)
            out = bytearray(size)
            with pytest.raises(RuntimeError):
                encode(data, level, out=out)
        else:
            raise ValueError(output)
    elif codec == 'decode':
        size = len(data)
        if output == 'new':
            assert data == decode(encoded)
        elif output == 'size':
            ret = decode(encoded, out=size)
            assert data == ret
        elif output == 'out':
            out = bytearray(size)
            ret = decode(encoded, out=out)
            assert data == out
            assert data == ret
        elif output == 'excess':
            out = bytearray(size + 1021)
            ret = decode(encoded, out=out)
            assert data == out[:size]
            assert data == ret
        elif output == 'trunc':
            size = max(0, size - 1)
            out = bytearray(size)
            if length > 0 and module in ('zlib', 'zstd', 'lzf', 'lz4', 'lz4h'):
                with pytest.raises(RuntimeError):
                    decode(encoded, out=out)
            else:
                decode(encoded, out=out)
                assert data[:size] == out
        else:
            raise ValueError(output)
    else:
        raise ValueError(codec)


@pytest.mark.parametrize('output', ['new', 'size', 'ndarray', 'bytearray'])
def test_lzw_decode(output):
    # LZW with horizontal differencing
    from imagecodecs import lzw_decode as decode
    from imagecodecs import delta_decode

    data = readfile('bytes.lzw_horizontal.bin')
    decoded_size = len(BYTES)

    if output == 'new':
        decoded = decode(data)
        decoded = numpy.frombuffer(decoded, 'uint8').reshape(16, 16)
        delta_decode(decoded, out=decoded, axis=-1)
        assert_array_equal(BYTESIMG, decoded)
    elif output == 'size':
        decoded = decode(data, out=decoded_size)
        decoded = numpy.frombuffer(decoded, 'uint8').reshape(16, 16)
        delta_decode(decoded, out=decoded, axis=-1)
        assert_array_equal(BYTESIMG, decoded)
        with pytest.raises(RuntimeError):
            decode(data, buffersize=32, out=decoded_size)
    elif output == 'ndarray':
        decoded = numpy.empty_like(BYTESIMG)
        decode(data, out=decoded.reshape(-1))
        delta_decode(decoded, out=decoded, axis=-1)
        assert_array_equal(BYTESIMG, decoded)
    elif output == 'bytearray':
        decoded = bytearray(decoded_size)
        decode(data, out=decoded)
        decoded = numpy.frombuffer(decoded, 'uint8').reshape(16, 16)
        delta_decode(decoded, out=decoded, axis=-1)
        assert_array_equal(BYTESIMG, decoded)


def test_lzw_decode_image_noeoi():
    # test LZW compressed string without EOI 512x512u2
    from imagecodecs import lzw_decode as decode

    fname = datafiles('image_noeoi.lzw.bin')
    with open(fname, 'rb') as fh:
        encoded = fh.read()
    fname = datafiles('image_noeoi.bin')
    with open(fname, 'rb') as fh:
        decoded_known = fh.read()
    # new output
    decoded = decode(encoded)
    assert decoded == decoded_known
    # provide output
    decoded = bytearray(len(decoded))
    decode(encoded, out=decoded)
    assert decoded == decoded_known
    # truncated output
    decoded = bytearray(100)
    decode(encoded, out=decoded)
    assert len(decoded) == 100


@pytest.mark.parametrize('output', ['new', 'out'])
def test_jpeg8_decode(output):
    from imagecodecs import jpeg8_decode as decode

    data = readfile('bytes.jpeg8.bin')
    tables = readfile('bytes.jpeg8_tables.bin')

    if output == 'new':
        decoded = decode(data, tables)
    elif output == 'out':
        decoded = numpy.empty_like(BYTESIMG)
        decode(data, tables, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(BYTESIMG.size * BYTESIMG.itemsize)
        decoded = decode(data, out=decoded)
    assert_array_equal(BYTESIMG, decoded)


@pytest.mark.parametrize('output', ['new', 'out', 'bytearray'])
def test_jpeg12_decode(output):
    from imagecodecs import jpeg12_decode as decode

    data = readfile('words.jpeg12.bin')
    tables = readfile('words.jpeg12_tables.bin')

    if output == 'new':
        decoded = decode(data, tables)
    elif output == 'out':
        decoded = numpy.empty_like(WORDSIMG)
        decode(data, tables, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(WORDSIMG.size * WORDSIMG.itemsize)
        decoded = decode(data, out=decoded)

    assert numpy.max(numpy.abs(WORDSIMG.astype('int32') -
                               decoded.astype('int32'))) < 2


@pytest.mark.parametrize('output', ['new', 'out', 'bytearray'])
def test_jxr_decode(output):
    from imagecodecs import jxr_decode as decode

    image = readfile('sample.bin')
    image = numpy.frombuffer(image, dtype='uint8').reshape(100, 100, -1)
    data = readfile('sample.jxr')

    if output == 'new':
        decoded = decode(data)
    elif output == 'out':
        decoded = numpy.empty_like(image)
        decode(data, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(image.size * image.itemsize)
        decoded = decode(data, out=decoded)
    assert_array_equal(image, decoded)


@pytest.mark.parametrize('output', ['new', 'out', 'bytearray'])
def test_j2k(output):
    from imagecodecs import j2k_decode as decode

    data = readfile('int8.j2k')
    dtype = 'int8'
    shape = 256, 256

    if output == 'new':
        decoded = decode(data, verbose=2)
    elif output == 'out':
        decoded = numpy.empty(shape, dtype)
        decode(data, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(shape[0]*shape[1])
        decoded = decode(data, out=decoded)

    assert decoded.dtype == dtype
    assert decoded.shape == shape
    assert decoded[0, 0] == -6
    assert decoded[-1, -1] == 2


@pytest.mark.parametrize('output', ['new', 'out', 'bytearray'])
def test_jp2(output):
    from imagecodecs import j2k_decode as decode

    data = readfile('rgb.jp2')
    dtype = 'uint8'
    shape = 400, 400, 3

    if output == 'new':
        with pytest.warns(UserWarning):
            decoded = decode(data, verbose=2)
    elif output == 'out':
        decoded = numpy.empty(shape, dtype)
        decode(data, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(shape[0]*shape[1]*shape[2])
        decoded = decode(data, out=decoded)

    decoded = decode(data)
    assert decoded.dtype == dtype
    assert decoded.shape == shape
    assert decoded[70, 140, 0] == 255
    assert decoded[180, 140, 1] == 255
    assert decoded[275, 140, 2] == 255


def test_j2k_ycbc():
    # subsampling not supported
    from imagecodecs import j2k_decode as decode
    data = readfile('ycbc.j2k')
    with pytest.raises(RuntimeError):
        decode(data)


@pytest.mark.parametrize('output', ['new', 'out', 'bytearray'])
def test_webp_decode(output):
    from imagecodecs import webp_decode as decode

    data = readfile('rgba.webp')
    dtype = 'uint8'
    shape = 50, 50, 3

    if output == 'new':
        decoded = decode(data)
    elif output == 'out':
        decoded = numpy.empty(shape, dtype)
        decode(data, out=decoded)
    elif output == 'bytearray':
        decoded = bytearray(shape[0]*shape[1]*shape[2])
        decoded = decode(data, out=decoded)

    assert decoded.dtype == dtype
    assert decoded.shape == shape
    assert decoded[25, 25, 1] == 122
    assert decoded[-1, -1, -1] == 43


@pytest.mark.parametrize('level', [None, 5, -1])
@pytest.mark.parametrize('deout', ['new', 'out', 'view', 'bytearray'])
@pytest.mark.parametrize('enout', ['new', 'out', 'bytearray'])
@pytest.mark.parametrize('input', ['rgb', 'rgba', 'view', 'gray', 'graya'])
@pytest.mark.parametrize('dtype', ['uint8', 'uint16'])
@pytest.mark.parametrize('codec', ['webp', 'png'])
def test_webpng(codec, dtype, input, enout, deout, level):
    """ """
    if codec == 'webp':
        from imagecodecs import webp_decode as decode
        from imagecodecs import webp_encode as encode
        if dtype != 'uint8' or input.startswith('gray'):
            pytest.skip("webp doesn't support dtype or grayscale")
    elif codec == 'png':
        from imagecodecs import png_decode as decode
        from imagecodecs import png_encode as encode
    else:
        raise ValueError()

    shape = {
        'gray': (32, 31, 1),
        'graya': (32, 31, 2),
        'rgb': (32, 31, 3),
        'rgba': (32, 31, 4),
        'view': (32, 31, 3)
        }[input]

    dtype = numpy.dtype(dtype)
    itemsize = dtype.itemsize

    data = numpy.random.randint(0, 255*dtype.itemsize,
                                size=shape[0]*shape[1]*shape[2],
                                dtype=dtype).reshape(*shape)
    if input == 'view':
        temp = numpy.empty((shape[0]+5, shape[1]+5, shape[2]), dtype)
        temp[2:2+shape[0], 3:3+shape[1], :] = data
        data = temp[2:2+shape[0], 3:3+shape[1], :]

    if enout == 'new':
        encoded = encode(data, level=level)
    elif enout == 'out':
        encoded = numpy.empty(2*shape[0]*shape[1]*shape[2]*itemsize, 'uint8')
        encode(data, level=level, out=encoded)
    elif enout == 'bytearray':
        encoded = bytearray(2*shape[0]*shape[1]*shape[2]*itemsize)
        encode(data, level=level, out=encoded)

    if deout == 'new':
        decoded = decode(encoded)
    elif deout == 'out':
        decoded = numpy.empty(shape, dtype)
        decode(encoded, out=numpy.squeeze(decoded))
    elif deout == 'view':
        temp = numpy.empty((shape[0]+5, shape[1]+5, shape[2]), dtype)
        decoded = temp[2:2+shape[0], 3:3+shape[1], :]
        decode(encoded, out=numpy.squeeze(decoded))
    elif deout == 'bytearray':
        decoded = bytearray(shape[0]*shape[1]*shape[2]*itemsize)
        decoded = decode(encoded, out=decoded)
        decoded = numpy.asarray(decoded, dtype=dtype).reshape(shape)

    if input == 'gray':
        decoded = decoded.reshape(shape)

    if codec == 'webp' and (level != -1 or input == 'rgba'):
        # RGBA roundtip doesn't work for A=0
        assert_allclose(data, decoded, atol=255)
    else:
        assert_array_equal(data, decoded, verbose=True)


def datafiles(pathname, base=None):
    """Return path to data file(s)."""
    if base is None:
        base = os.path.dirname(__file__)
    path = os.path.join(base, *pathname.split('/'))
    if any(i in path for i in '*?'):
        return glob.glob(path)
    return path


def readfile(fname):
    with open(datafiles(fname), 'rb') as fh:
        return fh.read()


SIZE = 2**15 + 3
BYTES = readfile('bytes.bin')
BYTESIMG = numpy.frombuffer(BYTES, 'uint8').reshape(16, 16)
WORDS = readfile('words.bin')
WORDSIMG = numpy.frombuffer(WORDS, 'uint16').reshape(36, 36, 3)


if __name__ == '__main__':
    import warnings
    # warnings.simplefilter('always')  # noqa
    warnings.filterwarnings('ignore', category=ImportWarning)  # noqa
    argv = sys.argv
    argv.append('-vv')
    pytest.main(argv)
