#!/usr/bin/python
# Taken from https://electro.club/f/50300 and modified a bit
from struct import pack, unpack

UPDKEY = b'\xFE\x80\x1C\xB2\xD1\xEF\x41\xA6\xA4\x17\x31\xF5\xA0\x68\x24\xF0'

def tea_encrypt_ecb(block, key):
    y, z = unpack('<LL', block)
    k = unpack('<LLLL', key)
    s = 0

    for i in range(32):
        s = (s + 0x9E3779B9) & 0xFFFFFFFF
        y = (y + (((z << 4) + k[0]) ^ (z + s) ^ ((z >> 5) + k[1]))) & 0xFFFFFFFF
        z = (z + (((y << 4) + k[2]) ^ (y + s) ^ ((y >> 5) + k[3]))) & 0xFFFFFFFF
    return pack('<LL', y, z)

def tea_decrypt_ecb(block, key):
    y, z = unpack('<LL', block)
    k = unpack('<LLLL', key)
    s = 0xC6EF3720

    for i in range(32):
        z = (z - (((y << 4) + k[2]) ^ (y + s) ^ ((y >> 5) + k[3]))) & 0xFFFFFFFF
        y = (y - (((z << 4) + k[0]) ^ (z + s) ^ ((z >> 5) + k[1]))) & 0xFFFFFFFF
        s = (s - 0x9E3779B9) & 0xFFFFFFFF
    return pack('<LL', y, z)

def xor(s1, s2):
    res = bytearray()
    for i in range(8):
        res.append(s1[i] ^ s2[i])
    return res

def checksum(data):
    s = 0
    for i in range(0, len(data), 4):
        s += unpack('<L', data[i:i+4])[0]
    return (((s >> 16) & 0xFFFF) | ((s & 0xFFFF) << 16)) ^ 0xFFFFFFFF

def pad(data):
    # The data which will be encrypted must be 8 byte aligned!
    # We also have to write a checksum to the last 4 bytes.
    # Zero pad for 4-byte aligning first:
    sz = len(data)
    if sz % 4:
        o = (4 - (sz % 4))
        data += b'\x00' * o
        sz += o

    # If we're 8-byte aligned now then add 4 zero pad bytes
    if (sz % 8) == 0:
        data += b'\x00\x00\x00\x00'

    # so we can add our 4 checksum bytes and be 8-byte aligned
    return data + pack('<L', checksum(data))

def unpad(data):
    chk = unpack('<L', data[-4:])[0]
    s = checksum(data[:-4])
    assert s == chk, 'checksum does not match!'
    return data[:-4]


class XiaoTea:
    def __init__(self):
        self.key = UPDKEY
        self.iv = b'\x00' * 8
        self.offset = 0

    def _UpdateKey(self):
        k = bytearray()
        for i in range(16):
            k.append((self.key[i] + i) & 0xFF)
        self.key = k

    def encrypt(self, data):
        data = pad(data)
        assert len(data) % 8 == 0, 'data must be 8 byte aligned!'
        res = bytearray()
        for i in range(0, len(data), 8):
            ct = tea_encrypt_ecb(xor(self.iv, data[i:i+8]), self.key)
            res += ct
            self.iv = ct
            self.offset += 8
            if (self.offset % 1024) == 0:
                self._UpdateKey()
        return res

    def decrypt(self, data):
        assert len(data) % 8 == 0, 'data must be 8 byte aligned!'
        res = bytearray()
        for i in range(0, len(data), 8):
            ct = data[i:i+8]
            res += xor(self.iv, tea_decrypt_ecb(ct, self.key))
            self.iv = ct
            self.offset += 8
            if (self.offset % 1024) == 0:
                self._UpdateKey()
        return unpad(res)
