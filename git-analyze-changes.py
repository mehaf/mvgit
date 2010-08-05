#!/usr/bin/env python
# requires python versions 2.4 or 2.5.  May work on 2.6.
'''
This program analyzes the changes between two limbs.

Usage: git analyze-limb [options] <limb1>..<limb2>
       git analyze-limb [options] [<limb1>]
    options:
	-r <remote>	specifies the remote alias, default "origin".
	-v		display commit descriptions for each commit
	-p		display patches with each commit
	-u <branchname>	Include <branchname> as a reference provider branch
	-c		display only "created" patches
	-h		display this help message

Analyzes the changes between two limbs.

In the first form, it analyzes the difference between <limb1> and <limb2>

In the second form, it analyzes the differences between <origin>/<limb1>
and <limb1>.  If <limb1> is omitted, the current limb is used for it.
'''

# Author: Dale Farnsworth <dfarnsworth@mvista.com>
# Copyright (C) 2009 MontaVista Software, Inc.
#
# This file is licensed under the terms of the GNU General Public License
# version 2. This program is licensed "as is" without any warranty of any
# kind, whether express or implied.

import getopt
import sys
import os
import re
import mvgitlib as git


# Global Constants
progname = ''
git_dir = None

# Global variables
debug = False
verbose = False
limb1_name = None
limb2_name = None
separator = None
remote_alias = None
upstream_branchnames = []
paths = []
patch = False
created_only = False
error_exit = False


def error(msg):
    sys.stderr.write(msg)
    sys.exit(1)


def usage(msg=None):
    '''
    Print a usage message and exit with an error code
    '''

    if msg:
	sys.stderr.write('%s\n' % str(msg).rstrip())

    error('\n%s\n' % __doc__.strip())


def process_options():
    global debug, verbose, limb1_name, limb2_name, separator, paths, patch
    global created_only, remote_alias
    short_opts = 'cr:hpu:v'
    long_opts = [ 'help', 'debug', 'verbose', 'version' ]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    for option, value in options:
	if option == '--help' or option == '-h':
	    usage()
	elif option == '--debug':
	    debug = True
	elif option == '--version':
	    sys.stdout.write('mvgit version %s\n' % "@@MVGIT_VERSION@@")
	    sys.exit(0)
	elif option == '--verbose' or option == '-v':
	    verbose = True
	elif option == '-p':
	    patch = True
	    verbose = True
	elif option == '-r':
	    remote_alias = value
	elif option == '-u':
	    upstream_branchnames.append(value)
	elif option == '-c':
	    created_only = True
	    patch = True
	    verbose = True
	else:
	    usage('Unknown option: %s' % option)

    if len(args) > 0:
	arg0 = args[0]
	match = (re.match(r'(.*)(\.\.\.)(.*)', arg0) or
		 re.match(r'(.*)(\.\.)(.*)', arg0))
    else:
	arg0 = ''
	match = None

    if match:
	limb1_name, separator, limb2_name = match.groups()
	if not limb1_name:
	    limb1_name = git.current_limb().name
	if not limb2_name:
	    limb2_name = git.current_limb().name
    else:
	limb2_name = arg0
	if not limb2_name:
	    limb2_name = git.current_limb().name

	limb1_name = limb2_name
	if not remote_alias:
	    remote_alias = git.remote_alias()
	remote_prefix = '%s/' % remote_alias
	if limb1_name.startswith('/'):
	    limb1_name = limb1_name[1:]
	if limb1_name.startswith(remote_prefix):
	    limb1_name = limb1_name[len(remote_prefix):]
	limb1_name = '%s/%s' % (remote_alias, limb1_name)
	separator = '..'

    if limb1_name.startswith('/'):
	limb1_name = limb1_name[1:]

    if limb2_name.startswith('/'):
	limb2_name = limb2_name[1:]

    if limb1_name.endswith('/'):
	limb1_name = limb1_name[:-1]

    if limb2_name.endswith('/'):
	limb2_name = limb2_name[:-1]

    paths = args[1:]


def change_msg(commit, change):
    if change == 'cherry-picked':
	msg = 'cherry-picked from %s' % commit.from_branches[0].name
    else:
	msg = change

    return msg


def write_commit(file, commit, change, branch):
    '''
    Writes information about the commit to file
    '''

    if change == 'old':
	branchname = branch.name
    else:
	branchname = branch.newbranch.name

    file.write('branch %s\n' % branchname)
    commit.write_id(file)

    if verbose:
	commit.write_header(file)

    msg = change_msg(commit, change)
    if change == 'rebased':
	msg += ' from %s' % commit.from_commits[0].id
    elif change == 'cherry-picked':
	msg += ' %s' % commit.from_commits[0].id

    file.write('change %s\n\n' % msg)

    commit.write_subject(file)

    if verbose:
	commit.write_body(file)

    file.write('\n')

    if patch:
	commit.write_patch(file)
	file.write('\n')


def plural(count, suffix='s'):
    if count == 1:
	return ''
    else:
	return suffix


def notice(s):
    global error_exit
    if s.strip().startswith('ERROR'):
	error_exit = True
    sys.stdout.write(s)
    sys.stdout.flush()


def summarize_branches(branches, action):
    if not branches:
	return

    if action == 'deleted':
	x = len(branches)
	notice('%2d deleted branch%s:\n' % (x, plural(x, 'es')))
	for branch in branches:
	    notice('    %s\n' % branch.name)
	notice('\n')

    elif action == 'created' or action == 'changed':
	x = len(branches)
	notice('%2d %s branch%s:\n' % (x, action, plural(x, 'es')))

	for branch in branches:
	    newbranch = branch.newbranch
	    notice('    %s commits: ' % newbranch.name)
	    old = 0
	    new = 0
	    for commit, change in branch.commits_with_change:
		if change == 'deleted':
		    old += 1
		else:
		    new += 1

	    if old:
		old = '%d deleted' % old
	    else:
		old = ''
	    if new:
		new = '%d new' % new
	    else:
		new = ''
	    if old and new:
		sep = ', '
	    else:
		sep = ''
	    notice('%s%s%s\n' % (old, sep, new))

	    if (newbranch != newbranch.limb.info_branch and
		    newbranch not in newbranch.limb.dependent_branches):
		notice('        ERROR: not in branch_dependencies\n')

	    if newbranch.subname.startswith('msd.'):
		check_msd_branch(newbranch)


	notice('\n')


def has_meta_and_nonmeta(commit):
    metadata = False
    non_metadata = False
    for name in commit.filenames:
	if name.startswith("MONTAVISTA"):
	    metadata = True
	else:
	    non_metadata = True

    return metadata and non_metadata


def summarize_commits(branches, action):
    def note_error(str):
	errors.append(str)

    file = sys.stdout

    for branch in branches:
	if branch.subname.startswith('external.'):
	    continue

	errors = []

	notice('====== %s changes:\n' % branch.newbranch.name)

	changemap = {}
	dups = 0
	for commit in branch.newbranch.commits:
	    changeid = commit.changeid
	    if changeid in changemap:
		notice('    Error: commit %s has same changeid '
			'as commit %s\n' %
			(commit.id, changemap[changeid].id))
		dups += 1
	    else:
		changemap[changeid] = commit
	if dups:
	    notice('\n')

	merges = []
	msg_count = {}
	for commit, change in branch.commits_with_change:
	    msg = change_msg(commit, change)
	    if change != 'deleted':
		bugz = commit.bugz or 'NONE'
		msg = "%s - bugz %s" % (msg, bugz)

		if has_meta_and_nonmeta(commit):
		    note_error('    Error: commit %s has both metadata '
		    		'and non-metadata files\n' % commit.id)

		if len(commit.parents()) > 1:
		    merges.append(commit)

		errs = commit.mv_header_errors()
		if errs:
		    for err in errs:
			note_error('    Warning: Commit %s %s' %
				(commit.abbrev_id(), err))
		    note_error('\n')
		if (commit.mv_header_dict.has_key('disposition') and
			commit.mv_header_dict['disposition'] == 'MontaVista'):
		    note_error('    Commit %s has disposition: Montavista\n' %
			commit.abbrev_id())

	    if change == 'cherry-picked':
		subj = commit.subject[0]
		for fcommit in commit.from_commits:
		    if fcommit.subject[0] == subj:
			break
		else:
		    note_error('  Cherry-picked commit subjects differ:\n'
			    '%12s "%s"\n       was cherry-picked from\n'
			    '%12s "%s"\n\n' %
			    (commit.abbrev_id(), subj,
			     fcommit.abbrev_id(), fcommit.subject[0]))

	    if not msg in msg_count:
		msg_count[msg] = 0
	    msg_count[msg] += 1

	for msg in msg_count.keys():
	    notice('%5d %s\n' % (msg_count[msg], msg))

	notice('\n')

	if merges:
	    notice('  New merge commits:\n')
	    for merge in merges:
		notice('    %s\n' % merge.id)
	    notice('\n')

	if errors:
	    for err in errors:
		notice(err)
	    notice('\n')

	if verbose or patch:
	    for commit, change in branch.commits_with_change:
		if created_only:
		    if change == 'cherry-picked':
			picked_branch = commit.from_branches[-1]
			if not picked_branch.subname.startswith('external.'):
			    continue
		    elif change != 'created':
			continue
		write_commit(file, commit, change, branch)

	    notice('\n')


def commit_signoffs(commit):
    re_signoff = re.compile(r'^Signed-off-by:[\s]*(.*)')
    signoffs = []
    for line in commit.body:
	m = re_signoff.match(line)
	if m:
	    signoffs.append(m.group(1).rstrip())
    return signoffs


def summarize_new_commits(branches):
    all_signoffs = None
    all_bugz = []
    commits_without_bugz = []
    errors = 0
    for branch in branches:
	if branch.subname.startswith('external.'):
	    for commit, change in branch.commits_with_change:
		if change == 'deleted' or change == 'rebased':
		    notice('Commit %s in %s was %s.\n' %
			(commit.abbrev_id(), branch.name, change))
		    errors += 1

		if commit.mv_header_dict:
		    notice('Commit %s in %s has an MV header.\n' %
			(commit.abbrev_id(), branch.newbranch.name))
		    errors += 1

	    continue

	for commit, change in branch.commits_with_change:
	    if change == 'deleted':
		continue

	    signoffs = set(commit_signoffs(commit))
	    if all_signoffs == None:
		all_signoffs = signoffs
	    all_signoffs &= signoffs

	    bugz = commit.bugz
	    if not bugz:
		bugz = 'NONE'
		commits_without_bugz.append(commit)

	    if bugz not in all_bugz:
		all_bugz.append(bugz)

    if errors:
	notice('\n')

    notice('All new commits in non-external branches are signed-off by:\n')
    if all_signoffs:
	all_signoffs = list(all_signoffs)
	all_signoffs.sort()
	for signoff in all_signoffs:
	    notice('    %s\n' % signoff)
    else:
	notice('    NONE\n')

    if all_bugz:
	notice('\nBugz for all changes: %s\n' % ' '.join(all_bugz))

    if commits_without_bugz:
	notice('Commits without a bugz number\n')
	for commit in commits_without_bugz:
	    notice('    %s\n' % commit.id)

    notice('\n')


def file_lines(branch, path):
    ref = '%s:%s' % (branch.name, path)
    cmd = ['git', 'show', ref]
    return git.call(cmd).splitlines()


def check_kernel_defconfigs(branch):
    '''
    Ensure that each defconfig file in ./configs contains a
    "# checksetconfig" line, and is newer than scripts/kconfig/baseconfig
    '''

    indent = ' ' * 8
    cmd = ['git', 'ls-tree', '--name-only', '%s:configs' % branch.name]
    try:
	defconfig_names = git.call(cmd).splitlines()
    except:
	notice(indent + 'WARNING: No ./configs directory\n')
	return

    paths = []
    commit_time = {}
    checksetconfig = {}
    for name in defconfig_names:
	path = 'configs/%s' % name
	paths.append(path)
	for line in file_lines(branch, path):
	    if line == '# checksetconfig':
		checksetconfig[path] = True
		break
	else:
	    checksetconfig[path] = False

	cmd = ['git', 'rev-list', '-1', '--date=raw', '--pretty=format:%cd',
		branch.name, '--', path]
	commit_time[path] = int(git.call(cmd).split()[2])

    if paths:
	baseconfig_path = 'scripts/kconfig/baseconfig'
	cmd = ['git', 'rev-list', '-1', '--date=raw', '--pretty=format:%cd',
		branch.name, '--', baseconfig_path]
	base_config_time = git.call(cmd)
	if base_config_time:
	    base_config_time = int(base_config_time.split()[2])

	for path in paths:
	    if not checksetconfig[path]:
		notice((indent +
			'WARNING: %s has no "# checksetconfig" line\n' % path) +
			indent + 'Need to run "make checksetconfig".\n')
	    elif base_config_time and base_config_time > commit_time[path]:
		notice((indent +
			'WARNING: %s is older than baseconfig.\n' % path) +
			indent + 'Need to run "make checksetconfig".\n')


def check_msd_conf(branch):
    indent = ' ' * 8
    path = 'MONTAVISTA/bitbake/conf/msd.conf'
    sane_inc = None
    for line in file_lines(branch, path):
	if line.startswith('MSD_VERSION'):
	    notice(indent + "WARNING: obsolete variable: MSD_VERSION in %s\n"
		    % path)
	if line.startswith('include') or line.startswith('require'):
	    if 'sane-2.6.' in line:
		sane_inc = line

    if not sane_inc:
	notice(indent + "WARNING: %s doesn't require sane.2.6.XX.inc\n" % path)
    

def check_bitbake_files(branch):
    check_msd_conf(branch)


def check_msd_branch(branch):
    check_kernel_defconfigs(branch)
    check_bitbake_files(branch)


def do_analyze():
    global limb1_name
    if '/bugfixes/' in limb1_name:
	limb = git.Limb(limb1_name, limb2_name)
	deleted_branches = limb.deleted_branches
	if deleted_branches:
	    sys.stdout.write("The following branch(es) don't exist in %s.\n" %
		    limb2_name)
	    for branch in deleted_branches:
		sys.stdout.write("\t%s\n" % branch.name)
	    sys.stdout.write("They may be removed via git push %s" %
		    remote_alias)
	    sys.stdout.write("For example: git push %s" % remote_alias)
	    for branch in deleted_branches:
		sys.stdout.write(" :%s" % branch.name)
	    sys.stdout.write("\n")

	limb1_name = re.sub(r'/bugfixes/.*', '', limb1_name)

    limb = git.Limb(limb1_name, limb2_name)

    if not limb.newlimb.repository_branches:
	error("Limb not found: %s\n" % limb2_name)

    if not limb.repository_branches:
	error("Limb not found: %s\n" % limb1_name)

    if upstream_branchnames:
	upstream_branches = []
	for ub_name in upstream_branchnames:
	    ub = git.Branch.get(ub_name)
	    if not ub.exists():
		rub = ub.remote_branch
		if not_rub.exists():
		    error("upstream-branch '%s' not found\n" % ub_name)
		ub = rub
	    upstream_branches.append(ub)
	limb.upstream_branches = upstream_branches

    deleted_branches = limb.deleted_branches
    created_branches = limb.created_branches
    changed_branches = limb.changed_branches
    branches_with_new_commits = created_branches + changed_branches

    summarize_branches(deleted_branches, 'deleted')
    summarize_branches(created_branches, 'created')
    summarize_branches(changed_branches, 'changed')

    if branches_with_new_commits:
	summarize_new_commits(branches_with_new_commits)

    summarize_commits(created_branches, 'created')
    summarize_commits(changed_branches, 'changed')


def set_global_constants():
    '''
    Initialize several global contants used by this program
    '''

    global git_dir
    global progname

    progname, ext = os.path.splitext(os.path.basename(sys.argv[0]))

    if 'GIT_DIR' in os.environ:
	git_dir = os.path.abspath(os.environ['GIT_DIR'])
    else:
	cmd = ['git', 'rev-parse', '--git-dir']
	git_dir = git.call(cmd, error=None, stderr=None)
	if not git_dir:
	    error('No git repository found\n')


def main():
    '''
    Main program
    '''

    set_global_constants()
    process_options()

    try:
	do_analyze()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


    if error_exit:
	sys.exit(1)


main()
