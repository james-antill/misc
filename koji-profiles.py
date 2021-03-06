#! /usr/bin/python3

from __future__ import print_function

import os

import koji

interesting = set(('server', 'cert'))
def profiles(user_config=None):
    # /etc/koji.conf.d
    configs = ['/etc/koji.conf.d']

    # /etc/koji.conf
    configs.append('/etc/koji.conf')

    # User specific configuration
    if user_config:
        # Config file specified on command line
        # The existence will be checked
        configs.append((os.path.expanduser(user_config), True))
    else:
        # User config dir
        configs.append(os.path.expanduser("~/.koji/config.d"))
        # User config file
        configs.append(os.path.expanduser("~/.koji/config"))

    config = koji.read_config_files(configs)

    m = {}
    for s in sorted(config.sections()):
        for name, value in config.items(s):
            if name in interesting:
                m[name] = value
        yield s, m

if __name__ == "__main__":
    for s, m in profiles():
        print("[%s]" % s)
        for k in sorted(m):
            print("    %s: %s" % (k, m[k]))
