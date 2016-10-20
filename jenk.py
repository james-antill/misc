#! /usr/bin/python -tt

__version__ = '0.1.2'
import sys
import fnmatch

import jenkins

# server = jenkins.Jenkins('http://jenkins.fedorainfracloud.org/job/pungi-modularity/19/console', username='myuser', password='mypassword')
server = jenkins.Jenkins('http://jenkins.fedorainfracloud.org/')

from pprint import pprint
import time
def _ui_time(tm, nospc=False):
    if nospc:
        return time.strftime("%Y-%m-%d--%H%MZ", time.gmtime(tm))
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(tm))
def _ui_age(num):
    ret = ""

    weeks = num / (60 * 60 * 24 * 7)
    num %= (60 * 60 * 24 * 7)
    if weeks:
        ret +=  "%u week(s)" % weeks
        if num:
            ret +=  " "

    days = num / (60 * 60 * 24)
    num %= (60 * 60 * 24)
    if days:
        ret +=  "%u day(s)" % days
        if num:
            ret +=  " "

    if not num:
        return ret

    hours = num / (60 * 60)
    num %= (60 * 60)

    minutes = num / (60)
    num %= (60)

    ret +=  "%02u:%02u:%02u" % (hours, minutes, num)
    return ret

def _get_job_info(server, name):
    try:
        return server.get_job_info(name)
    except jenkins.NotFoundException, e:
        return None

def _get_params(jobii, values=False):
    params = ''
    if 'actions' in jobii and jobii['actions']:
        for act in jobii['actions']:
            if 'parameters' not in act:
                continue
            if values:
                params = ['%s[%s]' % (d['name'], d['value']) for d in act['parameters'] if d['value']]
            else:
                params = [d['name'] for d in act['parameters'] if d['value']]
            params = ", ".join(sorted(params))
            break
    return params

def _prnt_build_list(server, name, limitnum=None, _debug=False):
    for jobi in _arg2wildjobi(server, name):
        count = 0
        print "Name: ", jobi['name']
        for build in jobi['builds']:
            count += 1
            num = build['number']
            jobii = server.get_build_info(jobi['name'], num)
            if _debug:
                print '-' * 79
                pprint(jobii)
                print '-' * 79

            print ' ',

            msg = "%s %6u on %s at %s for %s%s"
            if jobii['result'] != 'SUCCESS':
                res = '* Failed:'
            else:
                res = '         '
            params = _get_params(jobii)
            if params:
                params = "P: " + params
            print msg % (res,
                         jobii['number'], jobii['builtOn'],
                         _ui_time(jobii['timestamp'] / 1000),
                         _ui_age(jobii['duration'] / 1000), params)

            if limitnum is not None and count >= limitnum:
                break

def _data_job_params_(server, jobi, limitnum=None, _debug=False):
    mast_s = None
    mast_f = None
    branches = {}
    mast_num = 0
    for build in jobi['builds']:
        num = build['number']
        jobii = server.get_build_info(jobi['name'], num)
        if ((mast_num > 2) and 
            (int(time.time() * 1000) - jobii['timestamp'] > (60*60*24*8*1000))):
            break
        if _debug:
            print '-' * 79
            pprint(jobii)
            print '-' * 79

        data = [num, jobi, jobii]
        params = _get_params(jobii, values=True)
        if params == '':
            mast_num += 1
            if jobii['result'] != 'SUCCESS':
                if mast_f is None:
                    mast_f = data
            elif mast_s is None:
                mast_s = data
            continue
        if params in branches:
            continue
        branches[params] = data

    # Now we have the latest data for mast and each branch/param-build
    ret = [jobi['name']]

    if False: pass
    elif mast_s is None:
        ret.append(None)
    elif mast_f is not None and mast_f[0] > mast_s[0]:
        ret.append((False, mast_f, mast_s))
    else:
        ret.append((True,  mast_f, mast_s))

    pret = []
    if True:
        for params in sorted(branches, reverse=True, key=lambda x: branches[x][0]):
            num, jobi, jobii = branches[params]
            pret.append((num, params, jobi, jobii))
    ret.append(pret)
    return ret

def _prnt_job_params_(server, jobi, limitnum=None, _debug=False):
    data = _data_job_params_(server, jobi, limitnum, _debug)

    # Now we have the latest data for mast and each branch/param-build
    print data[0]
    print ' ',

    if False: pass
    elif data[1] is None:
        print ' ', "Master never succeeded."
    elif not data[1][0]:
        mast_f = data[1][1]
        mast_s = data[1][2]
        print "Current master is FAIL", mast_f[0], "it worked at", mast_s[0]
    else:
        mast_f = data[1][1]
        mast_s = data[1][2]
        print "Master is FINE", mast_s[0]
        if False and mast_f is not None:
            print "Master last FAILed", mast_f[0]

    if True:
        for num, params, jobi, jobii in data[2]:
            print ' ',' ',
            if jobii['result'] != 'SUCCESS':
                print "Proposed PR FAIL:", num, "P:", params
            else:
                print "Proposed PR success:", num, "P:", params

def _prnt_job_params(server, name, limitnum=None, _debug=False):
    for jobi in _arg2wildjobi(server, name):
        _prnt_job_params_(server, jobi, limitnum, _debug)

def _html_jobs_params(server, names, limitnum=None, _debug=False):
    row_names = set()
    rows = []
    for name in names:
        for jobi in _arg2wildjobi(server, name):
            if jobi['name'] in row_names:
                continue
            row_names.add(jobi['name'])
            data = _data_job_params_(server, jobi, limitnum, _debug)
            rows.append(data)

    from mako.template import Template
    import re
    tmpl = """\
    % for row in rows:
        ${tableidx(row)}
    % endfor
    % for row in rows:
        ${tabledata(row)}
    % endfor

<%def name="tableidx(data)">
</%def>

<%def name="tabledata(data)">
<h2 id="${data[0]}"><a href="https://jenkins.fedorainfracloud.org/job/${data[0]}">${data[0]}</a></h2>
<table>
    % if False:
        
    % elif data[1] is None:
    <tr> <td><b>Master</b> </td> <td style="color: red; font-weight: bold">NEVER PASSED </td> <td> </td>
    </tr>
    % elif not data[1][0]:
    <tr> <td><b>Master</b> </td> <td style="color: red; font-weight: bold">FAILURE </td> <td> ${buildnum(data[0], data[1][1][0], data[1][1][2]['timestamp'] / 1000)} last worked ${buildnum(data[0], data[1][2][0], data[1][2][2]['timestamp'] / 1000)} </td>
    </tr>
    % else:
    <tr> <td>Master </td> <td style="color: green">SUCCESS</td> <td> ${buildnum(data[0], data[1][2][0], data[1][2][2]['timestamp'] / 1000)} </td>
    </tr>
    % endif

    % for num, params, jobi, jobii in data[2]:
    <tr>
    %        if jobii['result'] != 'SUCCESS':
         <td>&nbsp;** PR </td> <td style="color: red; font-weight: bold"> FAIL </td> <td>${buildnum(data[0], num, jobii['timestamp'] / 1000)}: ${mungeparams(data[0], params)}</td>
    %        else:
         <td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PR </td> <td  style="color: green"> success </td> <td>${buildnum(data[0], num, jobii['timestamp'] / 1000)}: ${mungeparams(data[0], params)}</td>
    %        endif
    </tr>
    % endfor
</table>
</%def>

<%def name="buildnum(job, num, tm)">
<a href="https://jenkins.fedorainfracloud.org/job/${job}/${num}">build ${num} (at: ${time.strftime("%Y-%m-%d %H:%M", time.gmtime(tm))})</a>
</%def>

<%def name="mungeparams(name, params)">
%   if '/forks/' in params:
${re.sub('BRANCH\[(.*)], REPO\[https://pagure.io/forks/([^/]*)(/[^/]*)[.]git]',
         '<a href="https://pagure.io/fork/\\\\2\\\\3/commits/\\\\1">\\\\2 <b>\\\\1</b></a>',
         params)}
%   else:
${re.sub('BRANCH\[(.*)], REPO\[https://pagure.io/([^/]*)[.]git]',
         '<a href="https://pagure.io/\\\\2/commits/\\\\1"> <b>\\\\1</b></a>',
         params)}
%   endif
</%def>

<%!
    import re
    import time
%>
"""
    print Template(tmpl).render(rows=rows)

def _print_build_info(text, build, build_info):
    if build is None:
        return
    print ' '*6, text, 'build', build['number'],
    print 'at', _ui_time(build_info['timestamp'] / 1000)
    print ' '*6, "          On:", build_info['builtOn'],
    print "lasting", _ui_age(build_info['duration'] / 1000)

_all_jobs = None
def _arg2wildjobi(server, name):
    jobi = _get_job_info(server, name)
    if jobi is not None:
        yield jobi
        return
    global _all_jobs
    try:
        if _all_jobs is None:
            _all_jobs = server.get_jobs()
    except jenkins.NotFoundException, e:
        print '** Not found any jobs:', e
        return

    for job in sorted(_all_jobs, key=lambda x: x['name']):
        if fnmatch.fnmatch(job['name'], name):
            jobi = _get_job_info(server, job['name'])
            if jobi is None:
                continue
            yield jobi

def _prnt_job_list(server, name):
    for jobi in _arg2wildjobi(server, name):
        print "%28s %10s" % (jobi['name'], jobi['color']),
        if jobi['lastBuild'] is not None:
            jobnum = jobi['lastBuild']['number']
            jobii = server.get_build_info(jobi['name'], jobnum)
            print "%6u %6s %s" % (jobii['number'], jobii['builtOn'],
                                  _ui_time(jobii['timestamp'] / 1000))
        else:
            print '<No builds>'

def _prnt_job_info(server, name, _debug=False):
    jobi = _get_job_info(server, name)
    if jobi is None:
        print '** Not found:', name
        return

    if _debug:
        print '=' * 79
        pprint(jobi)
        print '-' * 79

    if jobi['color'] == 'blue':
        print "Name:", name
    else:
        print "Name:", '****', name, '****'
    if 'description' in jobi:
        print ' '*2, "Description:", jobi['description']
    print ' '*2,     "     Health:", jobi['healthReport'][0]['description']

    sbi = sb = None
    fbi = fb = None
    lbi = lb = None
    if jobi['lastSuccessfulBuild'] is not None:
        sb = jobi['lastSuccessfulBuild']
        sbi = server.get_build_info(name, sb['number'])
        if _debug:
            print '-' * 79
            pprint(sbi)
            print '-' * 79
    if jobi['lastFailedBuild'] is not None:
        fb = jobi['lastFailedBuild']
        fbi = server.get_build_info(name, fb['number'])
        if _debug:
            print '-' * 79
            pprint(fbi)
            print '-' * 79
    if jobi['lastBuild'] is not None:
        lb = jobi['lastBuild']
        lbi = server.get_build_info(name, lb['number'])
        if _debug:
            print '-' * 79
            pprint(lbi)
            print '-' * 79
    if sb is not None and lb is not None and sb['number'] == lb['number']:
        lb = None
    if fb is not None and lb is not None and fb['number'] == lb['number']:
        lb = None

    if jobi['color'] == 'blue':
        _print_build_info("last Success:", sb, sbi)
        _print_build_info("last  Failed:", fb, fbi)
        _print_build_info("        last:", lb, lbi)
    else:
        _print_build_info("last  Failed:", fb, fbi)
        _print_build_info("last Success:", sb, sbi)
        _print_build_info("        last:", lb, lbi)

    if False and sb is not None:
        print ' '*6, "last Success:", 'build', sb['number'],
        print 'at', _ui_time(sbi['timestamp'] / 1000)
        print ' '*6, "          On:", sbi['builtOn'],
        print "lasting", _ui_age(sbi['duration'] / 1000)


__opt_debug = False
__opt_num = 8
all_cmds = sorted(['list', 'info', 'version', 'builds', 'params'])
if True:
    import optparse

    epilog = "\n    ".join(["\n\nCOMMANDS:"]+sorted(all_cmds)) + "\n"
    argp = optparse.OptionParser(
            description='Jenkins cli',
        version="%prog-" + __version__)
    argp.format_epilog = lambda y: epilog

    argp.add_option(
            '--debug', default=False, action='store_true',
            help='debug output from commands')
    argp.add_option("--num", dest="num", default=None,
                help="limit for builds", type='int',
                metavar='[build limit]')

    (opts, args) = argp.parse_args()

    __opt_debug = opts.debug
    if opts.num is not None:
        __opt_num   = opts.num
else:
    args = sys.argv[1:]

if not args:
    print >>sys.stderr, "Usage:", sys.argv[0], '<cmd>', '[args]'

elif args[0] == 'version':
    version = server.get_version()
    print 'Jenkins (http://jenkins.fedorainfracloud.org/):', version

elif args[0] == 'list':

    print "%28s %10s %6s %6s %19s" % ('Name', 'Status', 'Build', 'Serv', 'Time')
    print '=' * 79
    for job in args[1:]:
        _prnt_job_list(server, job)

elif args[0] == 'info':
    for job in args[1:]:
        _prnt_job_info(server, job, _debug=__opt_debug)

elif args[0] == 'builds':
    for job in args[1:]:
        _prnt_build_list(server, job, limitnum=__opt_num, _debug=__opt_debug)

elif args[0] in ('params', 'branches'):
    for job in args[1:]:
        _prnt_job_params(server, job, limitnum=__opt_num, _debug=__opt_debug)

elif args[0] in ('html-params', 'html-branches'):
    uitm = _ui_time(time.time())
    print "<html><head><title>Jenkins CI: %s</title></head><body><h1>Jenkins CI builds as of %s</h1>" % (uitm, uitm)
    _html_jobs_params(server, names=args[1:], limitnum=__opt_num,
                      _debug=__opt_debug)
    print "</body></html>"

elif False:
    _prnt_job_info(server, 'fm-metadata-service')
    _prnt_job_info(server, 'fm-trello-taiga-sync')
    _prnt_job_info(server, 'fm-dnf-plugin')
    _prnt_job_info(server, 'pungi-modularity')

else:
    print >>sys.stderr, 'Unknown command:', ", ".join(all_cmds)
