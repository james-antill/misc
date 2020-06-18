#! /usr/bin/python

from __future__ import print_function

import os
import sys
import json
import time
import urllib

from optparse import OptionParser

# Try to work out good values for these...
conf_baseurl= ""
conf_apiurl = ""

cff__baseurl= "https://kojipkgs.fedoraproject.org/packages/"
cff__apiurl = "https://koji.fedoraproject.org/kojihub"

cfc__baseurl= "https://koji.mbox.centos.org/pkgs/packages/"
cfc__apiurl = "https://koji.mbox.centos.org/kojihub"

cfr__baseurl= "http://download.eng.bos.redhat.com/brewroot/vol/rhel-8/packages/"
cfr__apiurl = "http://brewhub.engineering.redhat.com/brewhub"

def autoconf(name):
    global conf_baseurl
    global conf_apiurl

    if False: pass
    elif name == "auto":
        if False: pass
        elif os.path.exists("/etc/koji.conf.d/brewkoji.conf"):
            autoconf("redhat")
        elif os.path.exists("/etc/koji.conf.d/mbox.conf"):
            autoconf("centos")
        else:
            autoconf("fedora")
    elif name == "centos":
        conf_baseurl= cfc__baseurl
        conf_apiurl = cfc__apiurl
    elif name == "fedora":
        conf_baseurl= cff__baseurl
        conf_apiurl = cff__apiurl
    elif name == "redhat":
        conf_baseurl= cfr__baseurl
        conf_apiurl = cfr__apiurl
    else:
        print("Bad autoconf name:", name)
        sys.exit(2)

try:
    import koji
except:
    koji = None

class Nevra(object):
    __slots__ = ['name', 'arch',
                 'version', 'release', 'epoch']

    def __eq__(self, other):
        for k in ('name', 'epoch', 'version', 'release', 'arch'):
            if getattr(self, k) != getattr(other, k):
                return False
        return True

    def ui_nevra(self):
        if self.epoch == '0':
            return self.nvra()
        else:
            return self.nevra()
    def ui_nevr(self):
        if self.epoch == '0':
            return self.nvr()
        else:
            return self.nevr()

    def nvr(self):
        return '%s-%s-%s' % (self.name, self.version, self.release)
    def nvra(self):
        return '%s-%s-%s.%s' % (self.name, self.version,self.release, self.arch)
    def nevr(self):
        return '%s-%s:%s-%s' % (self.name, self.epoch,self.version,self.release)
    def nevra(self):
        return '%s-%s:%s-%s.%s' % (self.name,
                                   self.epoch, self.version, self.release,
                                   self.arch)


def nevra_from_string(nevrastr):
    """Take a full nevra string and return a Nevra(). """
    n, ev, ra = nevrastr.rsplit('-', 2)
    if ':' in ev:
        e, v = ev.split(':', 1)
    else:
        e, v = '0', ev
    r, a = ra.rsplit('.', 1)

    nevra = Nevra()
    nevra.name = n
    nevra.epoch = e
    nevra.version = v
    nevra.release = r
    nevra.arch = a
    return nevra

def _data_url(url):
    try:
        if hasattr(urllib, "urlopen"):
            response = urllib.urlopen(url)
        else: # python3 imcompatibile
            import urllib.request as u2
            response = u2.urlopen(url)
    except IOError: # Py2
        return ""
    except OSError: # Py3+
        return ""
    data = response.read()
    return data

def _json_url(url):
    data = _data_url(url)
    try:
        data = json.loads(data)
    except ValueError:
        return None
    return data

# This is mostly copied and pasted from: koji_cli/commands.py rpminfo
def koji_name2srpm(session, nvra):
    info = session.getRPM(nvra)
    if info is None:
        print("No such koji rpm: %s\n" % nvra)
        return None

    if info['epoch'] is None:
        info['epoch'] = ""
    else:
        info['epoch'] = str(info['epoch']) + ":"

    if info.get('external_repo_id'):
        repo = session.getExternalRepo(info['external_repo_id'])
        print("External Repository: %(name)s [%(id)i]" % repo)
        print("External Repository url: %(url)s" % repo)
        return None

    buildinfo = session.getBuild(info['build_id'])
    buildinfo['name'] = buildinfo['package_name']
    buildinfo['arch'] = 'src'
    epoch = buildinfo['epoch']
    if buildinfo['epoch'] is None:
        buildinfo['epoch'] = ""
        epoch = '0'
    else:
        buildinfo['epoch'] = str(buildinfo['epoch']) + ":"

    if False:
            print("RPM Path: %s" %
                  os.path.join(koji.pathinfo.build(buildinfo), koji.pathinfo.rpm(info)))
            print("SRPM: %(epoch)s%(name)s-%(version)s-%(release)s [%(id)d]" % buildinfo)
            print("SRPM Path: %s" %
                  os.path.join(koji.pathinfo.build(buildinfo), koji.pathinfo.rpm(buildinfo)))
    else:
        srpm = Nevra()
        srpm.epoch = epoch
        srpm.name = buildinfo['name']
        srpm.version = buildinfo['version']
        srpm.release = buildinfo['release']
        srpm.arch = 'src'
        return srpm

def main():

    autoconf("auto")

    usage = "Usage: %prog cloud-init/19.4/4.el8|<url>/root.log pkgname..."
    usage += "\n Given a nvr/root.log search for the NVRs of package names given."
    usage += "\n Also converts nvr to .src.rpm name if koji import is abailable."
    parser = OptionParser(usage)

    parser.add_option("", "--koji-host", dest="koji_host",
                      help="Host to connect to", default=conf_apiurl)

    (options, args) = parser.parse_args()

    if len(args) < 2:
        parser.error("incorrect number of arguments")
        # print("Usage: name2srpm [NVRA|<url>/root.log] pkgname...")
        # print(" Given a root.log search for the NVRs of package names given.")
        sys.exit(1)

    kh = options.koji_host
    if kh in ("koji", "fedora", "mbox", "centos", "brew", "redhat"):
        m =  {"koji": "fedora", "mbox": "centos", "brew": "redhat"}
        kh = m.get(kh, kh)
        autoconf(kh)
        kh = conf_apiurl

    if koji is None:
        print("Warning: No koji module, so can't convert binary nvr to source nvr")
    else:
        kapi = koji.ClientSession(kh)

    # Eg.
    # https://kojipkgs.fedoraproject.org//packages/zsh/5.8/1.eln100.0/data/logs/x86_64/root.log
    # http://download.eng.bos.redhat.com/brewroot/vol/rhel-8/packages/cloud-init/19.4/4.el8/data/logs/noarch/root.log
    url = args[0]
    upkg = None
    if not url.startswith("http"):
        if '/' not in url:
            upkg = nevra_from_string(url)
            url = '%s/%s/%s' % (upkg.name, upkg.version, upkg.release)
        url = conf_baseurl + url
    if not url.endswith("root.log"):
        if upkg is not None:
            url += "/data/logs/%s/root.log" % upkg.arch
        else:
            url += "/data/logs/noarch/root.log"
    print("Trying:", url)
    data = _data_url(url)
    if data == "":
        print("Failed:", url)
        return
    lines = data.split('\n')
    pkgs = {}
    found = False
    lastlen = 0
    for line in lines:
        if line.endswith("Installed:"):
            found = True
            continue
        if not found:
            continue
        if line.endswith("Complete!"):
            found = False
            continue

        vals = line.split()
        if len(vals) not in (3, 4):
            print("Bad pkg line between installed/complete:", line, vals)
            break
        if lastlen == 0:
            lastlen = len(vals)
        if lastlen != len(vals):
            print("Different pkg line between installed/complete:", line, vals)
            break

        if len(vals) == 3: # New format
            nevra = nevra_from_string(vals[2])
        else:
            na = vals[2]
            vr = vals[3]
            n, a = na.rsplit('.', 1)
            v, r = vr.rsplit('-', 1)
            e = '0' # Eh.

            nevra = Nevra()
            nevra.name = n
            nevra.epoch = e
            nevra.version = v
            nevra.release = r
            nevra.arch = a

        pkgs[nevra.name] = nevra

    def prnt_pkg(bpkg):
        print("%s.src.rpm" % bpkg.nvr())
        if koji is not None:
            srpm = koji_name2srpm(kapi, bpkg.nvra())
            if srpm.nvr() != bpkg.nvr():
                print("  src %s.rpm" % srpm.nvra())

    if len(args) == 2 and args[1] == '*':
        for pkg in sorted(pkgs.values()):
            prnt_pkg(pkg)
        sys.exit(0)

    for pkg in args[1:]:
        if pkg in pkgs:
            prnt_pkg(pkgs[pkg])


if __name__ == '__main__':
    main()
