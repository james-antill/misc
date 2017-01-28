#! /usr/bin/python

import argparse
import requests
import json
try:
    import fedora.client.bodhi as bodhi
except:
    bodhi = None
# import fedmsg

# import fedmsg.config

import logging
try:
    # Python2.7 and later
    from logging.config import dictConfig
except ImportError:
    # For Python2.6, we rely on a third party module.
    from logutils.dictconfig import dictConfig

import locale
_used_locale = False
def _ui_lnum(num):
    global _used_locale
    if not _used_locale:
        locale.setlocale(locale.LC_ALL, '')
        _used_locale = True
    return locale.format("%d", int(num), True)

def _ui_num_s(num, sec):
    val = num / sec
    if val <= 10:
        return ("%7.7f" % (float(num) / sec))[:7]
    return _ui_num(val)
def _ui_num(num):
    num = int(num)
    if num < 1000:
        return "%7s" % num

    end = ["K", "M", "G", "T", "P", "E", "Z", "Y"]
    suffix = 0

    while num > (1000*1000):
        num /= 1000
        suffix += 1

    if suffix >= len(end):
        return _ui_lnum(num)

    num = str(num)
    if len(num) ==  4:
        return "  %s.%s%s" % (num[0],   num[1:3], end[suffix])
    if len(num) ==  5:
        return  " %s.%s%s" % (num[0:2], num[2:4], end[suffix])
    if len(num) ==  6:
        return   "%s.%s%s" % (num[0:3], num[3:5], end[suffix])

    assert False
    return num


# Progress:
# Unicode Block Elements
# http://www.fileformat.info/info/unicode/block/block_elements/utf8test.htm
_filblok_left2right = (
        '\xe2\x96\x8f',
        '\xe2\x96\x8e',
        '\xe2\x96\x8d',
        '\xe2\x96\x8c',
        '\xe2\x96\x8b',
        '\xe2\x96\x8a',
        '\xe2\x96\x89',
        '\xe2\x96\x88')
_filblok_shade = (
        '\xe2\x96\x91',
        '\xe2\x96\x92',
        '\xe2\x96\x93',
        '\xe2\x96\x88')
_filblok_down2up = (
        '\xe2\x96\x81',
        '\xe2\x96\x82',
        '\xe2\x96\x83',
        '\xe2\x96\x84',
        '\xe2\x96\x85',
        '\xe2\x96\x86',
        '\xe2\x96\x87',
        '\xe2\x96\x88')
_filblok_ascii = ('-', '=')

def _term_add_bar(bar_max_length, pc):
    if pc < 0: pc = 0
    if pc > 1: pc = 1

    blen = bar_max_length
    num = int(blen * pc)

    if sys.stdout.encoding == 'UTF-8':
        fil = _filblok_left2right
        # fil = _filblok_down2up
        # fil = _filblok_shade
    else:
        fil = _filblok_ascii

    bar  = fil[-1] * num
    rem = (blen * pc) - int(blen * pc)
    # rem is between 0 and 1, Eg. 0.1234
    # See how many elements of fil we can use, should be between 0 and len-1.
    rem = int(rem / (1.0 / len(fil)))
    if rem:
        bar += fil[rem-1]
        num += 1
    bar += ' ' * (blen - num)

    return '[%s]' % bar

def shorten_text(text, size):
    if len(text) <= size:
        return text
    half = size / 2

    size -= half
    el = "..."
    els = 3
    if sys.stdout.encoding == 'UTF-8':
        el = '\xe2\x80\xa6'
        els = 1
    if half > els:
        half -= els
        return text[:half] + el + text[-size:]
    return text[:half] + text[-size:]

class Prog:
    def __init__(self, prefix, total, output_func=None, every=1, elapse=0.25):
        self.prefix = prefix
        self.total  = total
        self.output_func = output_func
        self.every = every
        self.elapse = elapse

        self._tm_beg  = time.time()
        self._tm_last = self._tm_beg + 0.1

        self._last_num = 0
        self._last_tm  = 0

        if self.output_func is None:
            self.output_func = lambda x: x

    def _chk(self, num):
        if num == self.total:
            self._last_num = num
            self._last_tm  = time.time()
            return True

        if num - self._last_num < self.every:
            return False

        now = time.time()
        if now - self._last_tm < self.elapse:
          return False

        self._last_num = num
        self._last_tm  = now
        return True

    def progress_up(self, num, val):
        if not self._chk(num):
            return
        text = self.output_func(val)

        mnum = max(3, len(_ui_num(num)))
        left = 79 - (len(self.prefix) + mnum + 3 + mnum + 1)
        text = shorten_text(text, left)
        secs = self._last_tm - self._tm_beg
        print '%s%*s/s %*s %-*s\r' % (self.prefix, mnum, _ui_num_s(num, secs),
                                      mnum, _ui_num(num), left, text),
        sys.stdout.flush()

    def progress(self, num, val):
        if not self._chk(num):
            return
        text = self.output_func(val)

        ui_tot = _ui_num(num) # self.total)
        mnum = len(ui_tot)
        left = 79 - (len(self.prefix) + mnum + 3 + mnum + 1 + 3 + 2 + 18 + 1)
        text = shorten_text(text, left)
        perc = float(num) / float(self.total)
        textperc = _term_add_bar(16, perc)
        perc = int(100 * perc)
        secs = self._last_tm - self._tm_beg

        print '%s%*s/s %*s %3u%% %s %-*s\r' % (self.prefix,
                                               mnum, _ui_num_s(num, secs), mnum,
                                               ui_tot, perc,
                                               textperc, left, text),
        sys.stdout.flush()


    def end(self):
        print ' ' * 79, '\r',
        sys.stdout.flush()
        self._last_num = 0
        self._last_tm  = 0


log = logging.getLogger("fedmsg-srch")

DG_URL = "https://apps.fedoraproject.org/datagrepper/"
DG_DEF_TOPIC = "org.fedoraproject.prod.bodhi.errata.publish"

def fedmsg_get_messages(datagrepper_url=None, topic=None, msg_id=None, rows=None):
    """ Retrieves messages from datagrepper. """


    if rows is None:
        rows = 100
    rows_per_page = rows

    if datagrepper_url is None:
        datagrepper_url = DG_URL

    def _load_page(page):
        param = {
            'delta': 60*60*24*35, # Hack
            'topic': topic,
            'order': 'desc',
            'page': page,
            'rows_per_page': rows_per_page,
        }

        response = requests.get(datagrepper_url + 'raw/', params=param)
        return json.loads(response.text)

    if msg_id is not None:
        param = {
            'id': msg_id,
        }

        response = requests.get(datagrepper_url + 'id/', params=param)
        data = json.loads(response.text)

        yield data
        return

    if topic is None:
        topic = DG_DEF_TOPIC
    elif not topic.startswith("org."):
        topic = "org.fedoraproject.prod." + topic

    print "JDBG:", "INIT:"
    # Make an initial query just to get the number of pages
    data = _load_page(page=1)
    if 'raw_messages' not in data:
        pprint.pprint(data)
        sys.exit(1)
    pages = data.get('pages', 1)

    print "JDBG:", "Pages:", pages

    for page in range(1, pages+1):
        log.info("Requesting page %i of %i from datagrepper" %
                 (page, pages))
        if page != 1:
            data = _load_page(page)
        for message in data['raw_messages']:
            yield message

# From rpmdev-vercmp from yum etc.
def stringToEVR(verstring):
    if verstring in (None, ''):
        return ('', '', '')
    i = verstring.find(':')
    if i == -1:
        epoch = ''
    else:
        epoch = verstring[:i]
    i += 1
    j = verstring.find('-', i)
    if j == -1:
        version = verstring[i:]
        release = ''
    else:
        version = verstring[i:j]
        release = verstring[j + 1:]
    return (epoch, version, release)

def _parse_rpmps(fname):
    fo = open(fname)
    dist = fo.readline()
    dist = dist.rstrip()
    rel = fo.readline()
    rel = str(int(rel))
    pkgs = {} # Just latest of each name, Eg. kernel.
    for line in fo:
        pkg = line.rstrip()
        nevr = pkg.rsplit('.', 1)[0]
        (n, ev, r) = nevr.rsplit('-', 2)
        if ':' in ev:
            e = ev[:ev.find(':')]
            v = ev[ev.find(':')+1:]
        else:
            e = '0'
            v = ev
        if n not in pkgs or newer((e, v, r), pkgs[n][2:]):
            pkgs[n] = (pkg, n, e, v, r)
    return dist, rel, sorted(pkgs.values())

import os
import tempfile
import pwd
import glob
import urllib
import stat
def getCacheDir(tmpdir='/var/tmp', reuse=True, prefix='dumpsterfire-'):
    """return a path to a valid and safe cachedir - only used when not running
       as root or when --tempcache is set"""
    
    uid = os.geteuid()
    try:
        usertup = pwd.getpwuid(uid)
        username = usertup[0]
        # we prefer ascii-only paths
        username = urllib.quote(username)
    except KeyError:
        return None # if it returns None then, well, it's bollocksed

    if reuse:
        # check for /var/tmp/yum-username-* - 
        prefix = '%s%s-' % (prefix, username)
        dirpath = '%s/%s*' % (tmpdir, prefix)
        cachedirs = sorted(glob.glob(dirpath))
        for thisdir in cachedirs:
            stats = os.lstat(thisdir)
            if stat.S_ISDIR(stats[0]) and stat.S_IMODE(stats[0]) == 448 and stats[4] == uid:
                return thisdir

    # make the dir (tempfile.mkdtemp())
    cachedir = tempfile.mkdtemp(prefix=prefix, dir=tmpdir)
    return cachedir

_DEF_EXPIRATION_TIME = 2*24*60*60
import time
def _within_cache(myfile, expiration_time=None):
    if not os.path.exists(myfile):
        return False

    if expiration_time is None:
        expiration_time = _DEF_EXPIRATION_TIME

    val = False
    cookie_info = os.stat(myfile)
    if cookie_info[8] + expiration_time > time.time():
        val = True
    # WE ARE FROM THE FUTURE!!!!
    elif cookie_info[8] > time.time():
        val = False

    return val


import pickle
_bd_cachedir = getCacheDir()
def _cache_save_ids(data):
    dname = _bd_cachedir + '/' + ".id"
    for update in data['updates']:
        fname = dname + '/' + update['updateid']
        pickle.dump(update, open(fname + '.tmp', 'w'))
        os.rename(fname + '.tmp', fname)

def _cached_bd_id(bd, bdid, cache=True):
    dname = _bd_cachedir + '/' + ".id"
    fname = dname + '/' + bdid
    if cache and _within_cache(fname):
        return { 'updates' : [pickle.load(open(fname))] }
    kwargs = {}
    kwargs['updateid'] = bdid
    data = bd.send_request('updates/', verb='GET', params=kwargs)
    if not os.path.exists(dname):
        os.makedirs(dname)
    _cache_save_ids(data)
    return data

def _cached_bd_query(bd, package, release, cache=True):
    dname = _bd_cachedir + '/' + release
    fname = dname + '/' + package
    if cache and _within_cache(fname):
        return pickle.load(open(fname))
    data = bd.query(package=package, release=release, timeout=30)
    if not os.path.exists(dname):
        os.makedirs(dname)
    _cache_save_ids(data)
    pickle.dump(data, open(fname + '.tmp', 'w'))
    os.rename(fname + '.tmp', fname)
    return data

def _bd_recheck(bd, cache=False):
    cachedir = _bd_cachedir + '/'
    if cache:
        prog = Prog("Refresh: ", 0)
    else:
        prog = Prog("Recheck: ", 0)
    fnames = []
    for release in os.listdir(cachedir):
        try:
            int(release)
        except:
            continue
        for package in os.listdir(cachedir + '/' + release):
            fnames.append((package, release))
            prog.progress_up(len(fnames), release + '/' + package)
    prog.end()
    if cache:
        prog = Prog("Refresh: ", len(fnames))
    else:
        prog = Prog("Recheck: ", len(fnames))
    num = 0
    for package, release in fnames:
        num += 1
        prog.progress(num, release + '/' + package)
        _cached_bd_query(bd, package, release, cache=cache)
    prog.end()

def _bd_clean():
    cachedir = _bd_cachedir + '/'
    for release in os.listdir(cachedir):
        for package in os.listdir(cachedir + '/' + release):
            os.remove(cachedir + '/' + release + '/' + package)
        os.remove(cachedir + '/' + release)

def _bd_summary():
    cachedir = _bd_cachedir + '/'
    num  = 0
    size = 0
    for release in os.listdir(cachedir):
        for package in os.listdir(cachedir + '/' + release):
            num += 1
            size += os.path.getsize(cachedir + '/' + release + '/' + package)
    print "Num :", num
    print "Size:", size

def parse_args():
    parser = argparse.ArgumentParser()
    if False: # FEDMSG stuff...
        parser.add_argument("--id", dest="msg_id", default=None,
                            help="Process the specified message")
        parser.add_argument("--topic", dest="topic", default=None,
                            help="Process the specified topic")
        parser.add_argument("--rows", dest="rows", default=None,
                            help="Process the specified rows")
        parser.add_argument("--release", dest="rel", default=None,
                            help="Process the specified release only")
    parser.add_argument("--cache-timeout", default=None,
                        help="Set cache timeout.")
    parser.add_argument("cmds", default=None, nargs='*',
                        help="Args.")

    return parser.parse_args()

import rpm
def newer(evr1, evr2):
    return (rpm.labelCompare(evr1, evr2) > 0)

class Pkg2up(object):
    def __init__(self, update):
        self._update = update

    @property
    def bugs(self):
        return sorted((bug['bug_id'] for bug in self._update['bugs']))

# RPM print system
def rpmps_cmds():
    return "cut -d: -f4 /etc/system-release-cpe; cut -d: -f5 /etc/system-release-cpe; rpm --nodigest --nosignature -qa --qf \"%{nevra}\n\" | sort"

# This is disgusting, sorry.
# Using import docker would make it a bit better. Allows querying images etc.
def rpmps_from_container(image, fname):
    os.system("echo '" + rpmps_cmds() +
              "' | sudo docker run -i '" + image + "' bash > '" +
              fname + "'.rpmps")
def rpmps_from_localhost(fname="localhost"):
    os.system(rpmps_cmds() +
              " > '" +
              fname + "'.rpmps")

def update2pkg(pkg, pkgtup, update):
    n, e, v, r = pkgtup
    for build in update['builds']:
        bn, bv, br = build['nvr'].rsplit('-', 2)
        if n == bn and newer((None, bv, br), (None, v, r)):
            return (n, bv, br)

    return None

def prnt_update(up, pkgtup, update):
    n, e, v, r = pkgtup

    if False and update['status'] == 'testing':
        print ' *  Test:', update['alias']
    elif update['status'] == 'stable':
        print ' *  ID  :', update['alias']
    else:
        print ' *  ID  :', update['alias'], '(', update['status'], ')'
    if update['type'] == 'security':
        print '    Type:', '*'*8, update['type'], '*'*8
    else:
        print '    Type:', update['type']

    bugs = [bug['bug_id'] for bug in update['bugs']]
    if bugs:
        print '    Bugs:', ", ".join(map(str, sorted(bugs)))
    if up is not None:
        (_, bv, br) = up
        print '    Pkg :', '%s-%s-%s' % (n, bv, br)

def stats_init():
    td = {'bugs' : 0, 'sec' : 0, 'feat' : 0,
          'Tbugs' : 0, 'Tsec' : 0, 'Tfeat' : 0}
    return td
def stats_update(td, update, prefix=''):
    if update['type'] == 'security':
        td[prefix + 'sec']  += 1
    elif update['type'] == 'enhancement':
        td[prefix + 'feat'] += 1
    else:
        td[prefix + 'bugs'] += 1

def stats_prnt(fd):
    print ' Enhancements: %s unapplied, %s issued' % (_ui_num(fd['feat']), _ui_num(fd['Tfeat']))
    print '         Bugs: %s unapplied, %s issued' % (_ui_num(fd['bugs']), _ui_num(fd['Tbugs']))
    print 'Security Bugs: %s unapplied, %s issued' % (_ui_num(fd['sec']),  _ui_num(fd['Tsec']))

_DEF_IGNORE_STATUS = ('obsolete', 'pending', 'unpushed') # testing?

import pprint
import sys
def main():
    opts = parse_args()

    if opts.cache_timeout is not None:
        ct = opts.cache_timeout
        multi = 1
        if False: pass
        elif ct.endswith("s"):
            ct = ct[:-1]
        elif ct.endswith("m"):
            ct = ct[:-1]
            multi = 60
        elif ct.endswith("h"):
            ct = ct[:-1]
            multi = 60*60
        elif ct.endswith("d"):
            ct = ct[:-1]
            multi = 24*60*60
        elif ct.endswith("w"):
            ct = ct[:-1]
            multi = 7*24*60*60
        global _DEF_EXPIRATION_TIME
        _DEF_EXPIRATION_TIME = int(ct) * multi

    log.info("Starting fedmsg-errata")

    # fedmsg.init(**config)
    if bodhi is None:
        print "Using fedmsg is too slow, install fedora.client.bodhi."
        sys.exit(1)

    if False: pass
    elif opts.cmds and opts.cmds[0] == 'localhost':
        print "Saving rpms from current machine to: %s.rpmps" % ("localhost",)
        rpmps_from_localhost()
        sys.exit(0)
    elif opts.cmds and opts.cmds[0] == 'image':
        for cmd in opts.cmds[1:]:
            out = cmd.replace('/', '_')
            print "Saving rpms from docker image %s to: %s.rpmps" % (cmd,out)
            rpmps_from_container(cmd, out)
        sys.exit(0)
    elif opts.cmds and opts.cmds[0] in ('statistics', 'stats'):
        bd = bodhi.Bodhi2Client()
        td = stats_init()
        for cmd in opts.cmds[1:]:
            dist, rel, pkgs = _parse_rpmps(cmd)
            if dist != 'fedora':
                print "Can't use file '%s', as only fedora dist. supported (was: %s)" % (cmd, dist)
                continue
            fd = stats_init()
            prog = Prog("Pkgs: ", len(pkgs))
            num = 0
            for pkg, n, e, v, r in pkgs:
                prog.progress(num, pkg)
                data = _cached_bd_query(bd, package=n, release=rel)
                num += 1
                prog.progress(num, pkg)
                pkgtup = n, e, v, r
                for update in data['updates']:
                    if update['status'] in _DEF_IGNORE_STATUS:
                        continue # Included testing?
                    stats_update(fd, update, 'T')
                    stats_update(td, update, 'T')
                    if update2pkg(pkg, pkgtup, update) is None:
                        continue
                    stats_update(fd, update)
                    stats_update(td, update)
            prog.end()
            stats_prnt(fd)
        if len(opts.cmds) > 2:
            print ''
            print 'Total'
            print ''
            stats_prnt(td)
    elif opts.cmds and opts.cmds[0] in ('list', 'print'):
        bd = bodhi.Bodhi2Client()
        T = 'bugs'
        fnames = opts.cmds[1:]
        if fnames[0] in ('bugs', 'all', 'security'):
            T = fnames.pop(0)
        for cmd in fnames:
            dist, rel, pkgs = _parse_rpmps(cmd)
            if dist != 'fedora':
                print "Can't use file '%s', as only fedora dist. supported (was: %s)" % (cmd, dist)
                continue
            datas = {}
            prog = Prog("Pkgs: ", len(pkgs))
            num = 0
            for pkg, n, e, v, r in pkgs:
                num += 1
                prog.progress(num, pkg)
                datas[pkg] = _cached_bd_query(bd, package=n, release=rel)
            prog.end()
            for pkg, n, e, v, r in pkgs:
                data = datas[pkg]
                done = False
                pkgtup = n, e, v, r
                for update in data['updates']:
                    if update['status'] in _DEF_IGNORE_STATUS:
                        continue
                    if T != 'all' and update['type'] == 'enhancement':
                        continue
                    if T != 'all' and update['type'] == 'testing':
                        continue
                    if update['type'] != 'security' and T == 'security':
                        continue
                    up = update2pkg(pkg, pkgtup, update)
                    if up is None:
                        continue
                    if not done:
                        print pkg
                    done = True
                    prnt_update(up, pkgtup, update)
    elif opts.cmds and opts.cmds[0] == 'id':
        # No caching ... do we care?
        bd = bodhi.Bodhi2Client()
        for cmd in opts.cmds[1:]:
            data = _cached_bd_id(bd, cmd)
            for update in data['updates']:
                update['comments'] = []
                print bd.update_str(update).encode("UTF-8")

    elif opts.cmds and opts.cmds[0] == 'cache':
        cmd = 'summary'
        if len(opts.cmds) > 1:
            cmd = opts.cmds[1]
        if False: pass
        elif cmd == 'summary':
            _bd_summary()
        elif cmd == 'refresh':
            bd = bodhi.Bodhi2Client()
            _bd_recheck(bd, cache=True)
        elif cmd == 'recheck':
            bd = bodhi.Bodhi2Client()
            _bd_recheck(bd)
        elif cmd == 'clean':
            _bd_clean()
        else:
            print >>sys.stderr, "Sub-commands: summary|recheck|refresh|clean"
            sys.exit(1)
    else:
        print >>sys.stderr, "Format: fedora-errata image|list|stats|localhost|cache|id"
        sys.exit(1)
    sys.exit(0)

    # -----------------------------------------------------------------------
    # ==== FEDMSG attempt ====
    # -----------------------------------------------------------------------
    messages = fedmsg_get_messages(topic=opts.topic, msg_id=opts.msg_id, rows=opts.rows)
    num = 0
    for message in messages:
        msg = message['msg']
        num += 1
        print num
        for build in msg['update']['builds']:
            if build['nvr'].startswith("bash-"):
                break
            if build['nvr'].startswith("fish-"):
                break
            if build['nvr'].startswith("cinnamon-"):
                break
            if build['nvr'].startswith("zsh-"):
                break
            if msg['update']['type'] == 'security':
                break
        else:
            continue
        if opts.rel is not None and msg['update']['release']['version'] != opts.rel:
            continue

        print "=" * 79
        print "Msg-Id:", num, message.get('msg_id', None)
        # pprint.pprint(msg)
        print "  Type:", msg['update']['release']['version'], '/', msg['update']['type'], '/', msg['update']['severity']
        print "  Testing:", msg['update']['date_testing']
        print "  Stable:", msg['update']['date_stable']
        if msg['update']['bugs']:
            print "  Bugs:",
            for bug in msg['update']['bugs']:
                if bug['security']:
                    print '%s:%u' % ('*', bug['bug_id']),
                else:
                    print bug['bug_id'],
            print ''
        if False and msg['update'].get('cves', []):
            print "  CVEs:",
            for bug in msg['update']['cves']:
                    print bug,
            print ''
        print "  Pkgs:",
        for build in msg['update']['builds']:
            print "%u:%s" % (build['epoch'], build['nvr']),
        print ''
        if False and msg['update']['type'] == 'security':
            pprint.pprint(msg)
        print "-" * 79


main()
