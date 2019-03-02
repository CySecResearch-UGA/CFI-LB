"""
# Project: Adaptive Control Flow Integrity with Look Back and Multi-scope CFG Generation
# Author: Mustakimur Rahman Khandaker (mrk15e@my.fsu.edu)
# Florida State University
# Supervised: Dr. Zhi Wang
"""

import r2pipe
import sys
import copy
import pprint

# file generated by intel bin contain (method_name, function_entry, function_size)
bin_proc = "elf_extract.bin"
visited_proc = "tracked_func.bin"
# path to target binary
binary = str(sys.argv[1])

# read procedure information from file
with open(bin_proc) as f:
    lines = f.readlines()

search_ccfi = 0x0

# container for procedure information read from file
# key: function_entry as decimal
# value: touple as (method_name, function_size)
proc_dict = dict()
search_string = ""

for line in lines:
    line = line.strip('\n')

    # prepare search to look for call ccfi_verify instruction inside binary
    if (line.split('\t')[0] == 'cfilb_reference_monitor'):
        search_ccfi = line.split('\t')[1]
        search_string = '/c call ' + hex(int(search_ccfi, 10))

    proc_dict[int(line.split('\t')[1], 10)] = (
        line.split('\t')[0], int(line.split('\t')[2], 10))

lines = ""
# read procedure information from visited file
with open(visited_proc) as f:
    lines = f.readlines()

# container for visited procedure entry address read from visited file
# key: function_entry as decimal
# value: touple as (method_name, bool)
visited_dict = dict()

for line in lines:
    line = line.strip('\n')
    visited_dict[int(line, 10)] = True

# open the binary as readable
r2 = r2pipe.open(binary)
r2.cmd("aaa")

# search for all 'call ccfi_verify'
query_set = r2.cmd(search_string)
res_set = query_set.split('\n')

# container for child_function_entry
res_list = []

for query in res_set:
    ccfi = int(query.split(' ')[0], 16)
    for key, val in proc_dict.iteritems():
        # check which function has this instruction
        if (ccfi >= key and ccfi <= key + val[1]):
            res_list.append((key, ccfi))
            flag = False
            break

temp = []
for item in res_list:
    if(not item[0] in temp):
        temp.append(item[0])

# a dictionary which connected a destination[key] with its sources[list items]
part_cfg = dict()

# following iteratively retrieve the caller for each function we come up
for item in temp:
    tcall = r2.cmd('/c call ' + hex(item))
    tcall_arr = tcall.split('\n')
    part_cfg[item] = []
    for tcallins in tcall_arr:
        if(len(tcallins) > 0):
            tfunc = int(tcallins.split(' ')[0], 16)
            for key, val in proc_dict.iteritems():
                # check which function has this instruction
                if (tfunc >= key and tfunc <= key + val[1] and (not (key, 1) in part_cfg[item])):
                    part_cfg[item].append((key, 1))

deep = 2

temp_part_cfg = dict()
while(deep < 7):
    temp_part_cfg.clear()
    temp_part_cfg = copy.deepcopy(part_cfg)
    for key, val in part_cfg.iteritems():
        for item in set(val):
            if(not item[0] in part_cfg):
                tcall = r2.cmd('/c call ' + hex(item[0]))
                tcall_arr = tcall.split('\n')
                temp_part_cfg[item[0]] = []
                for tcallins in tcall_arr:
                    if(len(tcallins) > 0):
                        tfunc = int(tcallins.split(' ')[0].strip(), 16)
                        for key, val in proc_dict.iteritems():
                            # check which function has this instruction
                            if (tfunc >= key and tfunc <= key + val[1] and (not (key, deep) in temp_part_cfg[item[0]])):
                                temp_part_cfg[item[0]].append((key, deep))
    part_cfg.clear()
    part_cfg = copy.deepcopy(temp_part_cfg)
    deep += 1

# a dictionaly that have monitor[key] and connected 2-tuple (caller function, isFunctionTracked and isFunctionDepthSatisfied) list
adaptive_cfg = dict()
for item in res_list:
    adaptive_cfg[item[1]] = []
    adaptive_cfg[item[1]].append((item[0], 0))
    func_list = []
    temp_list = []
    func_list.append((item[0], 0))
    temp_list.append((item[0], 0))
    while(1):
        for func in func_list:
            if(func[0] in part_cfg):
                for f in part_cfg[func[0]]:
                    if(not f in adaptive_cfg[item[1]]):
                        temp_list.append(f)
                        adaptive_cfg[item[1]].append(f)
        del func_list[:]
        if(temp_list):
            func_list = copy.deepcopy(temp_list)
        else:
            break
        del temp_list[:]

caller_callee_dict = dict()
call_monitor_dict = dict()

for key, val in adaptive_cfg.iteritems():
    caller_callee_dict[key] = []
    call_monitor_dict[key] = []
    for item in val:
        if(not item[0] in caller_callee_dict[key]):
            caller_callee_dict[key].append(item[0])
        if (item[1] >= 3 and item[0] in visited_dict):
            call_monitor_dict[key].append(item[0])

# write the 3-tuple in a file for symbolic emulator code coverage
symFile = "sym_monitor.bin"
tFile = open(symFile, "w")
for key, val in call_monitor_dict.iteritems():
    for item in set(val):
        tFile.write(str(key) + '\t' +
                    str(item) + '\n')

symFile = "sym_helper.bin"
tFile.close()

tFile = open(symFile, "w")
for key, val in caller_callee_dict.iteritems():
    for item in set(val):
        tFile.write(str(key) + '\t' +
                    str(item) + '\n')
tFile.close()

# radare2 close
r2.quit()
