#! /usr/bin/python

"""Given a koji tag return a checksum, like rpmdb checksum."""

from __future__ import print_function

import hashlib
from optparse import OptionParser


import koji

class nvr2pkg(object):
    def __init__(self, nvr, epoch=None):
        n, v, r = nvr.rsplit('-', 2)
        self.name = n
        self.version = v
        self.release = r

        self.arch = 'src'
        if epoch is None:
            self.epoch = '0'
        else:
            self.epoch = str(epoch)

    def __lt__(self, o):
        if self.name != o.name:
            return self.name < o.name
        if self.nvr != o.nvr:
            return self.nvr < o.nvr
        if self.arch != o.arch:
            return self.arch < o.arch
        return False

    @property
    def nvr(self):
        return self.name + '-' + self.version + '-' + self.release
    @property
    def nvra(self):
        return self.nvr + '.' + self.arch
    @property
    def envra(self):
        return self.epoch + ':' + self.nvr + '.' + self.arch
    @property
    def ui_envra(self):
        if self.epoch == '0': return self.nvra
        return self.envra

_koji_max_query = 2000
def koji_archpkgs2sigs(kapi, pkgs):
    if len(pkgs) > _koji_max_query:
        for i in range(0, len(pkgs), _koji_max_query):  
            koji_archpkgs2sigs(kapi, pkgs[i:i + _koji_max_query])
        return

    # Get unsigned packages
    kapi.multicall = True
    # Query for the specific key we're looking for, no results means
    # that it isn't signed and thus add it to the unsigned list
    for pkg in pkgs:
        kapi.queryRPMSigs(rpm_id=pkg._koji_rpm_id)

    results = kapi.multiCall()
    for ([result], pkg) in zip(results, pkgs):
        pkg.sighash = []
        pkg.signed = []
        # print("JDBG:", result)
        for res in result:
            if not res['sigkey']:
                continue
            pkg.signed.append(res['sigkey'])
            pkg.sighash.append(res['sighash'])
        if len(pkg.signed) == 0:
            pkg.signed = ''
            pkg.sighash = ''
        if len(pkg.signed) == 1:
            pkg.signed = pkg.signed[0]
            pkg.sighash = pkg.sighash[0]

def koji_pkgs2archsigs(kapi, pkgs, filter=None):
    if len(pkgs) > _koji_max_query:
        ret = []
        for i in range(0, len(pkgs), _koji_max_query):
            npkgs = pkgs[i:i + _koji_max_query]
            ret.extend(koji_pkgs2archsigs(kapi, npkgs, filter))
        return ret

    if filter is None:
        filter = lambda x: False

    kapi.multicall = True
    for pkg in pkgs:
        kapi.listRPMs(buildID=pkg._koji_build_id)

    ret = []
    results = kapi.multiCall()
    for ([rpms], bpkg) in zip(results, pkgs):
        for rpm in rpms:
            pkg = nvr2pkg(rpm['nvr'], rpm['epoch'])
            pkg.arch = rpm['arch']
            pkg._koji_rpm_id = rpm['id']
            pkg._koji_build_id = bpkg._koji_build_id
            if filter(pkg):
                continue
            ret.append(pkg)

    koji_archpkgs2sigs(kapi, ret)
    return ret


# Stupid py3...
def b(x):
    return str(x).encode('utf-8')

def koji_tag2checksum(kapi, tag, checksum='sha1', srpms=False):
    """
    Return a checksum of all rpms.
    """

    binfos = kapi.listTagged(tag, inherit=True, latest=True)

    pkgs = []
    for binfo in binfos:
        # print("JDBG:", binfo)
        pkg = nvr2pkg(binfo['nvr'], binfo['epoch'])
        pkg._koji_build_id = binfo['build_id']
        pkgs.append(pkg)

    f = None
    if srpms:
        f = lambda x: x.arch != 'src'
    pkgs = koji_pkgs2archsigs(kapi, pkgs, filter=f)

    num = 0
    ret = hashlib.new(checksum)
    for pkg in sorted(pkgs):
        num += 1
        ret.update(b(pkg.envra))
        ret.update(b(' '))
        ret.update(b(pkg.sighash))
        ret.update(b('\n'))

    return str(num) + ":" + ret.hexdigest()


def main():
    parser = OptionParser()
    parser.add_option("", "--koji-host", dest="koji_host",
                      help="Host to connect to", default="https://koji.mbox.centos.org/kojihub")
    parser.add_option("", "--checksum",
                      help="Checksum to use", default="sha1")
    parser.add_option("", "--tag",
                      help="Koji tag to get the checksum for", default="dist-c8-stream")
    parser.add_option("", "--srpms", action="store_true",
                      help="Just look at the srpms", default=False)


    (options, args) = parser.parse_args()

    kapi = koji.ClientSession(options.koji_host)

    csum = koji_tag2checksum(kapi, options.tag, options.checksum, options.srpms)
    if options.srpms:
        csum = 's' + csum
    print(csum)

# Badly written but working python script
if __name__ == "__main__":
    main()

