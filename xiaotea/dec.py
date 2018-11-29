#!/usr/bin/python
from sys import argv, exit
from os.path import getsize
from xiaotea import XiaoTea

if len(argv) != 3:
    exit('Usage: ' + argv[0] + ' <infile> <outfile>')

fsize = getsize(argv[1])

if fsize % 8:
    exit('Wrong input file size !')

cry = XiaoTea()

hfi = open(argv[1], 'rb')
hfo = open(argv[2], 'wb')

hfo.write(cry.decrypt(hfi.read()))

hfo.close()
hfi.close()
