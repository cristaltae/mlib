try:
    import re2 as re
except ImportError:
    import re

import enum
from functools import wraps
from copy import deepcopy
import gzip as _gz
import errno
import signal
import os
import string
import StringIO
import random
import hashlib
import datetime
#import log
#log = log.get_logger(__name__)


def chunks(l, n): return [l[x: x + n] for x in xrange(0, len(l), n)]

def dostime_to_date(dosdate):
    date = dosdate >> 16;
    time = dosdate & 0xFFFF;
    y = ((date & 0xFE00) >> 9) + 1980;
    m = (date & 0x1E0) >> 5;
    d = date & 0x1F;
    h = (time & 0xF800) >> 11;
    mi = (time & 0x7E0) >> 5;
    s = (time & 0x1F) << 1;
    if s == 60:
        s = 59
    return datetime.datetime(year=y, month=m, day=d, hour=h, minute=mi, second=s)



BASEPATH = ''


def re_match(r, d, cstr):
    if cstr:
        r += '\x00'
    return map(lambda x: x.strip("\x00"), re.findall(r, d))


get_urls = lambda d, cstr=False: re_match("https?://[\x21-\x7e]{6,}", d, cstr)
get_strings = lambda d, cstr=False: re_match('[ -~]{3,}', d, cstr)
get_stringsW = lambda d, cstr=False: map(lambda x: x[0].decode('utf-16').strip("\x00"),re.findall(r'(([^\x00]\x00)+\x00\x00)', d + ("\x00\x00" if cstr else '')))

class E(enum.Enum):

    @classmethod
    def from_val(cls, val):
        for n, e in cls.__members__.items():
            if e.value == val:
                return e
        return None

# def generic_parse(_data):
#     try:
#         return _generic_parse(_data)
#     except:
#         print _data
#         raise Exception('asdf')

def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or '.') for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)


def generic_unparse(data, do_rest=False):
    cfg = deepcopy(data)
    r = ['INJECTS']
    r.append('=' * 80)
    for inj in cfg['injects']:

        r.append('Target: ' + inj['target'])
        inj['injects']
        for i in inj['injects']:
            if 'pre' in i:
                r.append('<data_before>')
                r.append(i['pre'])
                r.append('<data_end>')
            if 'post' in i:
                r.append('<data_after>')
                r.append(i['post'])
                r.append('<data_end>')
            if 'inj' in i:
                r.append('<data_inject>')
                r.append(i['inj'])
                r.append('<data_end>')

    r.append('\n\nACTIONS')
    r.append('=' * 80)
    for a in cfg.get('actions', []):
        r.append('Target: %s | Action: %s | Type: %s' %
                 (a['target'], a['action'], a['type']))
    r.append("\n")
    if do_rest:
        for el in cfg:
            if el in ['injects', 'actions']:
                continue

            r.append(el.upper())
            r.append('=' * 80)
            for e in cfg[el]:
                r.append(str(e))
        r.append("\n")
    return "\n".join(r)


def realpath(p):
    my_path = os.path.abspath(os.path.expanduser(p))
    if os.path.islink(my_path):
        my_path = os.readlink(my_path)
    return my_path


def realdir(p):
    my_path = realpath(p)
    return os.path.dirname(os.path.dirname(my_path))


def get_my_path():
    global BASEPATH
    if not BASEPATH:
        BASEPATH = realdir(__file__) + os.sep + __name__.split('.')[0]
    return BASEPATH


def ngrams(data, cnt=4):
    a = [data]
    for i in range(1, cnt):
        a.append(data[cnt:])
    return zip(*a)


def generic_parse(_data):

    if not _data:
        return None

    off = _data.find('set_url')
    off2 = 0
    ret = []
    while off < len(_data):
        off2 = _data.find('set_url', off + 7)
        if off2 == -1:
            ret.append(_process_ent(_data[off:]))
            break
        else:
            ret.append(_process_ent(_data[off:off2]))
        off = off2
    # print off
    return ret


def _process_ent(d):
    try:
        ret = {}
        __process_ent(d, ret)
    except Exception as e:
        import traceback
        print '-' * 20
        print d
        print '#' * 20
        print ret
        print '-' * 20
        traceback.print_exc()
    return ret


def __process_ent(d, ret):
    TRNSL = {'data_before': 'pre', 'data_after': 'post',
             'data_inject': 'inj', 'data_count': 'cnt'}
    d = d.strip()

#    try:
    trgt, rest = d.split("\n", 1)
#    except:
#        print '#'*20
#        print rest
#        raise Exception('e1')

    try:
        _, url, fl = trgt.strip().split(' ')
    except ValueError:
        if trgt.strip() == 'set_url':
            # huh target url in new line?
            url, rest = rest.split("\n", 1)
        else:
            _, url = trgt.strip().split(' ')

        fl = ''
    ret['flags'] = fl
    ret['target'] = url
    ret['injects'] = []

    r = {}

    while rest:
        # skip comments?
        if rest.startswith(';') or rest.startswith('#'):
            o = rest.find("\n")
            if o == -1:
                return ret

            rest = rest[o + 1:]
            continue


#        try:
        tag, rest2 = rest.split("\n", 1)
        # except:
        #     print '#'*20
        #     print `rest`
        #     raise Exception('e2')

        rest = rest2
        tag = tag.strip()
        if not tag:
            continue

        if tag == 'data_end':
            #log.error('fucked up config... skip it...')
            print '[-] fucked up config... skip it...'
            continue

        _end = rest.find('data_end')
        r[TRNSL[tag]] = rest[:_end].strip().decode('unicode-escape')

        if tag == 'data_after':
            ret['injects'].append(r)
            r = {}
        rest = rest[_end + 8:].strip()


def load_dll(path):
    import ctypes
    p = get_my_path()
    return ctypes.cdll.LoadLibrary(os.path.join(p, path))


def get_thread_pool(c):
    from multiprocessing.pool import ThreadPool
    return ThreadPool(processes=c)
