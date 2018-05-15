#!/usr/bin/python3
from binascii import hexlify
import struct
import keystone

# https://web.eecs.umich.edu/~prabal/teaching/eecs373-f10/readings/ARMv7-M_ARM.pdf
MOVW_T3_IMM = [*[None]*5, 11, *[None]*6, 15, 14, 13, 12, None, 10, 9, 8, *[None]*4, 7, 6, 5, 4, 3, 2, 1, 0]
MOVS_T1_IMM = [*[None]*8, 7, 6, 5, 4, 3, 2, 1, 0]

def PatchImm(data, ofs, size, imm, signature):
    assert size % 2 == 0, 'size must be power of 2!'
    assert len(signature) == size * 8, 'signature must be exactly size * 8 long!'
    imm = int.from_bytes(imm, 'little')
    sfmt = '<' + 'H' * (size // 2)

    sigs = [signature[i:i + 16][::-1] for i in range(0, len(signature), 16)]
    orig = data[ofs:ofs+size]
    words = struct.unpack(sfmt, orig)

    patched = []
    for i, word in enumerate(words):
        for j in range(16):
            imm_bitofs = sigs[i][j]
            if imm_bitofs is None:
                continue

            imm_mask = 1 << imm_bitofs
            word_mask = 1 << j

            if imm & imm_mask:
                word |= word_mask
            else:
                word &= ~word_mask
        patched.append(word)

    packed = struct.pack(sfmt, *patched)
    data[ofs:ofs+size] = packed
    return (orig, packed)


def FindPattern(data, signature, mask=None, start=None, maxit=None):
    sig_len = len(signature)
    if start is None:
        start = 0
    stop = len(data)
    if maxit is not None:
        stop = start + maxit

    if mask:
        assert sig_len == len(mask), 'mask must be as long as the signature!'
        for i in range(sig_len):
            signature[i] &= mask[i]

    for i in range(start, stop):
        matches = 0

        while signature[matches] is None or signature[matches] == (data[i + matches] & (mask[matches] if mask else 0xFF)):
            matches += 1
            if matches == sig_len:
                return i

    raise Exception('Pattern not found!')


class FirmwarePatcher():
    def __init__(self, data):
        self.data = bytearray(data)
        self.ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)

    def kers_min_speed(self, kmh):
        val = struct.pack('<H', int(kmh * 345))
        sig = [0x25, 0x68, 0x40, 0xF6, 0x16, 0x07, 0xBD, 0x42]
        ofs = FindPattern(self.data, sig) + 2
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        return [(ofs, pre, post)]

    def normal_max_speed(self, kmh):
        val = struct.pack('<B', int(kmh))
        sig = [0x04, 0xE0, 0x21, 0x85, 0x1C, 0x21, 0xE1, 0x83]
        ofs = FindPattern(self.data, sig) + 4
        pre, post = PatchImm(self.data, ofs, 2, val, MOVS_T1_IMM)
        return [(ofs, pre, post)]

    def eco_max_speed(self, kmh):
        val = struct.pack('<B', int(kmh))
        sig = [0x00, 0xE0, 0x22, 0x85, 0x16, 0x22, 0xE2, 0x83]
        ofs = FindPattern(self.data, sig) + 4
        pre, post = PatchImm(self.data, ofs, 2, val, MOVS_T1_IMM)
        return [(ofs, pre, post)]

    # all CFWs have this patch and I don't know what it actually does
    def idk_what_this_does(self):
        sig = [0x40, 0xF2, 0xA5, 0x61, 0xA0, 0xF6, 0x28, 0x20, 0x88, 0x42]
        ofs = FindPattern(self.data, sig)
        val = struct.pack('<H', 0xA28)
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        return [(ofs, pre, post)]

    def motor_start_speed(self, kmh):
        val = struct.pack('<H', int(kmh * 345))
        sig = [0xF0, 0xB4, None, 0x4C, 0x26, 0x68, 0x40, 0xF2, 0xBD, 0x67]
        ofs = FindPattern(self.data, sig) + 6
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        return [(ofs, pre, post)]

    # lower value = more power
    # original = 51575 (~500 Watt)
    # DYoC = 40165 (~650 Watt)
    # CFW W = 27877 (~850 Watt)
    # CFW = 25787 (~1000 Watt)
    def motor_power_constant(self, val):
        val = struct.pack('<H', int(val))
        ret = []
        sig = [0x31, 0x68, 0x2A, 0x68, 0x09, 0xB2, 0x09, 0x1B, 0x12, 0xB2, 0xD3, 0x1A, 0x4C, 0xF6, 0x77, 0x12]
        ofs = FindPattern(self.data, sig) + 12
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append((ofs, pre, post))
        ofs += 4

        ofs += 4
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append((ofs, pre, post))

        sig = [0xD3, 0x1A, 0x4C, 0xF6, 0x77, 0x12]
        ofs = FindPattern(self.data, sig, None, ofs, 100) + 2
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append((ofs, pre, post))
        ofs += 4

        ofs += 4
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append((ofs, pre, post))

        sig = [0xC9, 0x1B, 0x4C, 0xF6, 0x77, 0x13]
        ofs = FindPattern(self.data, sig, None, ofs, 100) + 2
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append((ofs, pre, post))
        return ret

    def instant_eco_switch(self):
        ret = []
        sig = [0x2C, 0xF0, 0x02, 0x0C, 0x81, 0xF8, 0x00, 0xC0, 0x01, 0x2A, 0x0A, 0xD0]
        ofs = FindPattern(self.data, sig) + 8
        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        ofs += 2

        pre, post = self.data[ofs:ofs+2], bytearray((0x0A, 0xE0))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))

        sig = [0x4C, 0xF0, 0x02, 0x0C, 0x81, 0xF8, 0x00, 0xC0, 0x01, 0x2A, 0x06, 0xD1, 0x2B, 0xB9]
        ofs = FindPattern(self.data, sig, None, ofs, 100) + 8
        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        ofs += 2

        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        ofs += 2

        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))

        sig = [0x85, 0xF8, 0x34, 0x60, 0x02, 0xE0, 0x0B, 0xB9]
        ofs = FindPattern(self.data, sig, None, ofs, 100) + 6
        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        return ret

    def boot_with_eco(self):
        ret = []
        sig = [0xB4, 0xF8, 0xEA, 0x20, 0x01, 0x2A, 0x02, 0xD1, 0x00, 0xF8, 0x34, 0x1F, 0x01, 0x72]
        ofs = FindPattern(self.data, sig)
        pre, post = self.data[ofs:ofs+4], bytearray((0xA4, 0xF8, 0xEA, 0x10))
        self.data[ofs:ofs+4] = post
        ret.append((ofs, pre, post))
        ofs += 4

        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        ofs += 2

        pre, post = self.data[ofs:ofs+2], bytearray((0x00, 0xBF))
        self.data[ofs:ofs+2] = post
        ret.append((ofs, pre, post))
        return ret

    def cruise_control_delay(self, delay):
        delay = int(delay * 200)
        assert delay.bit_length() <= 12, 'bit length overflow'
        sig = [0x35, 0x48, 0xB0, 0xF8, 0xF8, 0x10, 0x34, 0x4B, 0x4F, 0xF4, 0x7A, 0x70, 0x01, 0x29]
        ofs = FindPattern(self.data, sig) + 8
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('MOV.W R0, #{:n}'.format(delay))[0])
        self.data[ofs:ofs+4] = post
        return [(ofs, pre, post)]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        eprint("Usage: {0} <orig-firmware.bin> <target.bin>".format(sys.argv[0]))
        exit(1)

    with open(sys.argv[1], 'rb') as fp:
        data = fp.read()

    cfw = FirmwarePatcher(data)

    cfw.kers_min_speed(35)
    cfw.normal_max_speed(31)
    cfw.eco_max_speed(26)
    cfw.idk_what_this_does()
    cfw.motor_start_speed(3)
    cfw.motor_power_constant(40165)
    cfw.instant_eco_switch()
    #cfw.boot_with_eco()
    #cfw.cruise_control_delay(5)

    with open(sys.argv[2], 'wb') as fp:
        fp.write(cfw.data)
