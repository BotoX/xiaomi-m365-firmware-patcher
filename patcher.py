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

    def voltage_limit(self, volts):
        val = struct.pack('<H', int(volts * 100) - 2600)
        sig = [0x40, 0xF2, 0xA5, 0x61, 0xA0, 0xF6, 0x28, 0x20, 0x88, 0x42]
        ofs = FindPattern(self.data, sig)
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


    def russian_throttle(self):
        ret = dict()
        # Find address of eco mode, part 1 find base addr
        sig = [0x91, 0x42, 0x01, 0xD2, 0x08, 0x46, 0x00, 0xE0, 0x10, 0x46, 0xA6, 0x4D]
        ofs = FindPattern(self.data, sig)
        ofs += 10
        imm = struct.unpack('<H', self.data[ofs:ofs + 2])[0] & 0xFF
        ofsa = ofs + imm * 4 + 4 # ZeroExtend '00' + align?
        eco_addr = struct.unpack('<L', self.data[ofsa:ofsa + 4])[0]

        ret['eco_base'] = {'ofs': ofs, 'imm': imm, 'ofsa': ofsa, 'addr': hex(eco_addr)}

        # part 2, find offset of base addr
        sig = [0x85, 0xF8, 0x34, 0x60] # STRB.W  R6, [R5, #imm12]
        mask = [0xFF, 0xFF, 0x00, 0x0F] # mask imm12
        ofs = FindPattern(self.data, sig, mask, ofs, 100)
        imm = struct.unpack('<HH', self.data[ofs:ofs + 4])[1] & 0x0FFF
        eco_addr += imm

        ret['eco_addr'] = {'ofs': ofs, 'imm': imm, 'addr': hex(eco_addr)}


        sig = [0xF0, 0xB5, 0x25, 0x4A, 0x00, 0x24, 0xA2, 0xF8, 0xEC, 0x40, 0x24, 0x49, 0x4B, 0x79, 0x00, 0x2B,
               0x3E, 0xD1, 0x23, 0x4D, 0x2F, 0x68, 0x23, 0x4E, 0x23, 0x4B, 0x00, 0x2F, 0x39, 0xDB, None, 0x64,
               0x01, 0x24, 0x74, 0x82, 0x32, 0x38, 0x01, 0xD5, 0x00, 0x20, 0x02, 0xE0, 0x7D, 0x28, 0x00, 0xDD,
               0x7D, 0x20, 0xB2, 0xF8, 0xEC, 0x60, 0x7D, 0x24, 0x26, 0xB1, 0xB2, 0xF8, 0xEC, 0x20, 0x01, 0x2A,
               0x0B, 0xD0, 0x13, 0xE0, 0xD1, 0xE9, None, 0x21, 0x52, 0x1A, 0x42, 0x43, 0x92, 0xFB, 0xF4, 0xF0,
               0x08, 0x44, 0x29, 0x68, 0x02, 0xF0, None, 0xFB, 0x08, 0xE0, 0x4A, 0x8C, 0x89, 0x8C, 0x52, 0x1A,
               0x42, 0x43, 0x92, 0xFB, 0xF4, 0xF0, 0x40, 0x18, 0x00, 0xD5, 0x00, 0x20, 0x19, 0x68, 0x09, 0x1A,
               0x19, 0x68, 0x01, 0xD5, 0x41, 0x1A, 0x00, 0xE0, 0x09, 0x1A, 0x4F, 0xF4, 0x96, 0x72, 0x91, 0x42,
               0x05, 0xDD, 0x19, 0x68, 0x81, 0x42, 0x00, 0xDD, 0x52, 0x42, 0x18, 0x68, 0x10, 0x44, 0x18, 0x60,
               0xF0, 0xBD, 0x1C, 0x60, 0x74, 0x82, 0xF0, 0xBD, *[None] * 4 * 5]
        ofs = FindPattern(self.data, sig)

        ofsa = ofs + len(sig) - (4 * 5)
        addr1, addr2, addr3, addr4, addr5 = struct.unpack('<LLLLL', self.data[ofsa:ofsa + 20])

        # STRH.W (T2)  Rt, [Rn, #imm12]
        addr1_ofs1 = struct.unpack('<H', self.data[ofs + 6 + 2:ofs + 6 + 2 + 2])[0] & 0xFFF

        # LDRB (T1)  Rt, [Rn, #imm5]
        addr2_ofs1 = (struct.unpack('<H', self.data[ofs + 12:ofs + 12 + 2])[0] >> 6) & 0x1F

        # STR (T1)  Rt, [Rn, #imm5]
        addr2_ofs2 = (struct.unpack('<H', self.data[ofs + 30:ofs + 30 + 2])[0] >> 6) & 0x1F
        addr2_ofs2 *= 4 # ZeroExtend '00'

        # STRH (T1)  Rt, [Rn, #imm5]
        addr4_ofs1 = (struct.unpack('<H', self.data[ofs + 34:ofs + 34 + 2])[0] >> 6) & 0x1F
        addr4_ofs1 *= 2 # ZeroExtend '0'

        ret['addrs'] = {
                        '1': [hex(addr1), hex(addr1 + addr1_ofs1)],
                        '2': [hex(addr2), hex(addr2 + addr2_ofs1), hex(addr2 + addr2_ofs2)],
                        '3': [hex(addr3)],
                        '4': [hex(addr4), hex(addr4 + addr4_ofs1)],
                        '5': [hex(addr5)]
                        }

        asm = f'''
                LDR    R3, ={hex(addr2 + addr2_ofs1)}
                LDRB   R3, [R3]
                CBNZ   R3, loc_ret
                AND    R2, R3, #0xFF
                LDR    R3, ={hex(addr3)}
                LDR    R1, [R3]
                CMP    R1, #0
                BLT    loc_1
                PUSH   {{R4, R5}}
                LDR    R1, ={hex(addr4 + addr4_ofs1)}
                LDR    R5, ={hex(addr2 + addr2_ofs2)}
                MOVS   R4, #1
                SUBS   R0, #0x32
                STR    R2, [R5]
                STRH   R4, [R1]
                BMI    loc_3
                LDR    R2, ={hex(eco_addr)}
                CMP    R0, #0x7D
                LDRB   R2, [R2]
                IT     GE
                MOVGE  R0, #0x7D
                CMP    R2, R4
                BEQ    loc_2
                MOVS   R3, #0x96
                MUL    R3, R3, R0
                LDR    R2, ={hex(addr5)}
                STR    R3, [R2]

                loc_popret:
                POP    {{R4, R5}}

                loc_ret:
                BX     LR

                loc_1:
                LDR    R1, ={hex(addr5)}
                ADD.W  R3, R3, #0x1580
                ADDS   R3, #0x12
                STR    R2, [R1]
                STRH   R2, [R3]
                BX     LR

                loc_2:
                MOVW   R4, #0x1AF4
                MOVS   R2, #0x64
                MUL    R2, R2, R0
                LDR    R1, ={hex(addr5)}
                STR    R2, [R1]
                LDR    R2, [R3]
                CMP    R2, R4
                BLE    loc_popret
                LDR    R3, [R3]
                LDR    R2, [R1]
                SUB.W  R3, R3, #0x1AE0
                SUBS   R3, #0x14
                ADD.W  R3, R3, R3, LSL#2
                SUB.W  R3, R2, R3, LSL#1
                STR    R3, [R1]
                B      loc_popret

                loc_3:
                LDR    R3, ={hex(addr5)}
                MVN    R2, #0x9
                STR    R2, [R3]
                B      loc_popret
        '''

        res = self.ks.asm(asm)
        assert len(res[0]) <= len(sig), 'new code larger than old code, this won\'t work'
        assert len(res[0]) == 164, 'hardcoded size safety check, if you haven\'t changed the ASM then something is wrong'

        # pad with zero for no apparent reason
        padded = bytes(res[0]).ljust(len(sig), b'\x00')

        ret['len_sig'] = len(sig)
        ret['len_res'] = len(res[0])
        ret['res_inst'] = res[1]

        self.data[ofs:ofs+len(padded)] = bytes(padded)

        return ret


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
    cfw.voltage_limit(52)
    cfw.motor_start_speed(3)
    cfw.motor_power_constant(40165)
    cfw.instant_eco_switch()
    cfw.boot_with_eco()
    cfw.cruise_control_delay(5)
    #cfw.russian_throttle()

    with open(sys.argv[2], 'wb') as fp:
        fp.write(cfw.data)
