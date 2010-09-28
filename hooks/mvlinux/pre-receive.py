#!/usr/bin/python
# requires python versions 2.4 or 2.5.  Should work on 2.6, but not tested.

'''
This program functions as a git server pre-receive or post-receive hook

This program is designed to be run by git-receive-pack on an MVL6 kernel
git server.  It is not intended to be invoked directly from the command line.
'''

# Author: Dale Farnsworth <dfarnsworth@mvista.com>
# Copyright (C) 2009-2010 MontaVista Software, Inc.
#
# This file is licensed under the terms of the GNU General Public License
# version 2. This program is licensed "as is" without any warranty of any
# kind, whether express or implied.

import getopt
import sys
import os
import subprocess
import time
import mvgitlib as git


# Global Constants
bugz_server = 'bugz.sh.mvista.com'
git_server = 'git.sh.mvista.com'
git_base_dir = '/var/cache/git'
debug_flag = False
progname = ''
git_dir = ''
project_desc = ''
project_url = ''
commit_url_fmt = ''
bugz_url_fmt = ''
gatekeeper_groups = ''
gatekeepers = []
gitadmin_groups = ''
gitadmins = []
email_recipients = ()
user = None


# Global Variables
errors = []		# a list of error message lines
bugz_dict = {}		# each element is {bugz#: set(branches)}
rebased_branches = []


def debug(msg):
    if debug_flag:
	for line in msg.splitlines():
	    notice("DEBUG %s\n"  % line)


def warning(msg):
    for line in msg.splitlines():
	notice("Warning: %s\n"  % line)


def error(*msgs, **kwargs):
    '''
    Add each line of msg to the global error list
    '''

    global errors

    fail = True
    for key in kwargs.keys():
	if key == 'fail':
	    fail = kwargs[key]
	else:
	    sys.stderr.write('errors: unknown kwarg: "%s"\n' % key)
	    sys.exit(1)

    errors.append((msgs, fail))


def check_errors():
    '''
    If there are any errors in the global error list, print them and exit
    '''

    if errors:
	sys.stderr.write("\n")
	error_exit = False
	for msgs, fail in errors:
	    sys.stderr.write("Error: %s\n" % msgs[0].strip())
	    for msg in msgs[1:]:
		sys.stderr.write('           %s\n' %  msg.strip())
	    if fail:
		error_exit = True
	sys.stderr.write("\n")
	if error_exit:
	    sys.exit(1)
	else:
	    sys.stderr.write("Allowing push to bugfixes branch to proceed.\n\n")


def gitadmin():
    if user.name in gitadmins:
	return True

    for group in user.groups:
	if group in gitadmin_groups:
	    return True

    return False


def gatekeeper():
    if user.name in gatekeepers:
	return True

    for group in user.groups:
	if group in gatekeeper_groups:
	    return True

    if gitadmin():
	return True

    return False


def pre_commit(commit, change, branch):
    '''
    Perform all of the pre-receive checks on a commit
    '''

    if change == 'deleted':
	if branch.limb.bugz:		# anyone can delete bugfixes commits
	    return

	if gitadmin():			# gitadmin can delete non-bugfix commits
	    return

	if branch not in rebased_branches:
	    rebased_branches.append(branch)
	    error('Deleting commits from branch %s requires gitadmin privileges\n'
		    % branch.name)
	return

    if branch.subtype == 'external':
	return

    errors = list(commit.mv_header_errors())
    if errors:
	errors[0] = 'Commit %s %s' % (commit.abbrev_id(), errors[0])
	fail = not branch.limb.bugz
	error(fail=fail, *errors)

    if change == 'rebased':
	if branch.limb.bugz:		# anyone can rebase bugfixes commits
	    return

	if gitadmin():			# gitadmin can rebase non-bugfix commits
	    return

	if branch not in rebased_branches:
	    rebased_branches.append(branch)
	    error('Rebasing branch %s requires gitadmin privileges\n'
		    % branch.name)


def pre_branch(branch):
    '''
    Perform all of the pre-receive checks on a branch
    '''

    if branch.deleted:
	if branch.limb.bugz:		# anyone can delete bugfixes branches
	    return
	if gitadmin():			# gitadmin can delete any branches
	    return

	error('Deleting branch %s requires gitadmin privileges\n'
	    % branch.name)
	return

    for commit, change in branch.commits_with_change:
	pre_commit(commit, change, branch)


def pre_tag(tag):
    '''
    Perform pre-receive checks on the given tag
    '''
    if not tag.newtag.id:
	error('Tag deletion is not allowed: %s\n' % tag.name)
	return

    if not tag.newtag.annotated():
	error('Un-annotated tag is not allowed: %s\n' % tag.name)


def pre_receive(tags, branches):
    '''
    Perform pre-receive checks on all of the passed tags and limbs
    '''

    for tag in tags:
	pre_tag(tag)

    for branch in branches:
	pre_branch(branch)

    check_errors()

    os.umask(0002)	# we want the logs to be group writable

    limbs = []
    for branch in branches:
	limb = branch.limb

	if not limb.name.startswith('mvl-'):
	    continue

	if not limb in limbs:
	    limbs.append(limb)

    for limb in limbs:
	filename = os.path.join('limblogs', '%s.log' % limb.name)
	dirname = os.path.dirname(filename)
	if not os.path.isdir(dirname):
	    os.makedirs(dirname)
	file = open(filename, 'a')
	limb.write_push_log_entry(file)


def notice(msg):
    '''
    Output a message on stdout
    '''

    sys.stdout.write(msg)


def commit_update_summary(commits_with_change):
    changes = ['created', 'cherry-picked', 'rebased', 'deleted']

    sum = dict([(x, 0) for x in changes])

    for commit, change in commits_with_change:
	sum[change] += 1

    results = ['%d %s' % (sum[x], x) for x in changes if sum[x]]
    return ', '.join(results)


def get_change_msg(commit, change):
    if change == 'deleted':
	msg = 'DELETED'
    elif change == 'rebased':
	msg = 'rebased'
    elif change == 'cherry-picked':
	msg = 'cherry-picked from %s' % commit.from_branches[0].name
    elif change == 'created':
	msg = 'created'

    return msg


def write_commit(file, commit):
    '''
    Writes information (to be emailed) about the commit to file
    '''

    commit.write_abbrev_id_and_subject(file)
    file.write('%s\n' % (commit_url_fmt % commit.id))


def send_email():
    '''
    Send email about the pushed changes

    Email is sent to each recipient in the global "email_recipients"
    regarding commits for each bugz that is a key in the global "bugz_dict".
    '''

    def branch_name(branch):
	return branch.name

    recipients = ', '.join(email_recipients)
    if not recipients:
	return

    envelope_sender = '<git-mail@mvista.com>'
    cmd = ['/usr/sbin/sendmail', '-t', '-f', envelope_sender]

    if 'external' in bugz_dict:
	external_branches = list(bugz_dict['external'])
	del bugz_dict['external']
    else:
	external_branches = []

    if 'deleted' in bugz_dict:
	deleted_branches = list(bugz_dict['deleted'])
	del bugz_dict['deleted']
    else:
	deleted_branches = []

    if 'created' in bugz_dict:
	created_branches = list(bugz_dict['created'])
	del bugz_dict['created']
    else:
	created_branches = []

    bugz_list = bugz_dict.keys()
    bugz_list.sort(key=int)
    for bugz in bugz_list:

	p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=1)
	file = p.stdin

	file.write((
	    'From: git-checkin@mvista.com\n'
	    'To: %s\n'
	    'Subject:  [Bug %s]\n'
	    'Content-Type: text/plain\n'
	    'X-Bugz-URL: ' + bugz_url_fmt + '\n\n'
	    'Project: %s\n'
	    '%s\n\n') % (recipients, bugz, bugz, project_desc, project_url))

	file.write("Pushed by %s (%s)\n" % (user.real_name, user.name))
	if len(bugz_list) > 1:
	    other_bugz = list(bugz_list)
	    other_bugz.remove(bugz)
	    other_bugz = ', '.join(['bug %s' % x for x in other_bugz])
	    file.write('Simultaneously pushed: %s\n\n' % other_bugz)

	if deleted_branches:
	    file.write('Branches deleted:\n')
	    for branch in deleted_branches:
		file.write('    %s\n' % branch.name)
	    file.write('\n')

	if created_branches:
	    file.write('Branches created:\n')
	    for branch in created_branches:
		file.write('    %s created\n' % branch.name)
	    file.write('\n')

	file.write('Branches updated:\n')

	branches = list(bugz_dict[bugz]) + external_branches
	branches.sort(key=branch_name)
	for branch in branches:
	    if branch.created:
		file.write('    %s created, commits:\n' % branch.name)
	    else:
		file.write('    %s modified, commits:\n' % branch.name)
	    bugz_commits_with_change = []
	    for commit_with_change in branch.commits_with_change:
		commit, change = commit_with_change
		if commit.bugz == bugz or change == 'deleted':
		    bugz_commits_with_change.append(commit_with_change)

	    branch.bugz_commits_with_change = bugz_commits_with_change

	    msg_count = {}
	    for commit, change in branch.commits_with_change:
		msg = get_change_msg(commit, change)
		if not msg in msg_count:
		    msg_count[msg] = 0
		msg_count[msg] += 1

	    for msg in msg_count.keys():
		file.write('    %5d %s\n' % (msg_count[msg], msg))

	    file.write('\n')

	for branch in branches:
	    if branch.subtype == 'external':
		continue

	    file.write('Branch %s commits:\n' % branch.name)
	    new_commits = []
	    deleted_commits = []
	    for commit, change in branch.bugz_commits_with_change:
		if change == 'deleted':
		    deleted_commits.append((commit, change))
		else:
		    new_commits.append((commit, change))

	    if deleted_commits:
		for commit, change in deleted_commits:
		    file.write("DELETED ")
		    write_commit(file, commit)
		file.write('\n')

	    if new_commits:
		if len(new_commits) > 25:
		    file.write("%d new commits in the range:\n" %
		    		len(new_commits))
		    write_commit(file, new_commits[0][0])
		    file.write("    through\n")
		    write_commit(file, new_commits[-1][0])
		    file.write('\n')
		else:
		    for commit, change in new_commits:
			write_commit(file, commit)
		    file.write('\n')

	file.close()

	if p.wait() != 0:
	    raise Exception('failed: "%s"\n' % ' '.join(cmd))

    if bugz_list:
	bugz_list_str = ', '.join(bugz_list)
	notice(
	    'Affected bugs: %s\n'
	    'Email sent to %s\n' % (bugz_list_str, recipients))


def add_branch_to_bugz_dict(bugz, branch):
    '''
    Add the branch to the list of branches for the bugz
    '''

    if bugz not in bugz_dict:
	bugz_dict[bugz] = set()

    bugz_dict[bugz].add(branch)


def post_commit(commit, change, branch):
    '''
    Perform post-receive operations on the given commit
    '''

    bugz = commit.bugz

    if debug_flag:
	subject = ''.join(commit.subject)

	if bugz:
	    bugz_msg = ' - Bugz %s' % bugz
	else:
	    bugz_msg = ''

	debug('commit %s%s\n' % (commit.id, bugz_msg))
	msg = get_change_msg(commit, change)
	if change == 'cherry-picked':
	    msg = '%s %s' % (msg, commit.from_commit.id)
	debug('%s\n' % msg)
	debug('    %s\n\n' % subject)

    if branch.limb.bugz:
	return				# No email for bugz branches

    if branch.subtype == 'external':
	bugz = 'external'

    if not bugz:
	if change == 'deleted':
	    return
	raise Exception('No bugz for non-external commit')

    add_branch_to_bugz_dict(bugz, branch)


def post_branch(branch):
    '''
    Perform post-receive operations on the given branch
    '''

    def l20(s):
	'''
	Return the leftmost 20 characters of the passed string
	'''
	if not s:
	    s = '0' * 40
	return s[:20]

    notice('Branch %s\n' % branch.name)

    if branch.deleted:
	add_branch_to_bugz_dict('deleted', branch)
	notice("    deleted, was %s\n" % branch.id)
	return

    if branch.created:
	add_branch_to_bugz_dict('created', branch)
	notice("    created at %s\n" % branch.newbranch.id)

    debug('    %s -> %s\n' %
	    (l20(branch.id), l20(branch.newbranch.id)))

    cwc = branch.commits_with_change
    if cwc:
	notice('    commits: %s\n\n' % commit_update_summary(cwc))
	for commit, change in cwc:
	    post_commit(commit, change, branch)


def post_receive(tags, branches):
    '''
    Perform post-receive operations on the passed limbs
    '''

    # nothing to do for tags

    for branch in branches:
	post_branch(branch)

    send_email()


def usage(msg=None):
    '''
    Print a usage message and exit with an error code
    '''

    if msg:
	sys.stderr.write('%s\n' % str(msg).rstrip())

    sys.stderr.write('\n%s\n' % __doc__.strip())
    sys.exit(1)


def do_refs():
    '''
    Read refs from stdin, then instantiate and process them

    Depending on the name of the running program, performs either
    pre-receive or post-receive operations.
    '''

    def branch_name(branch):
	return branch.name

    tags = []
    branches = []
    for line in sys.stdin:
	(old, new, refname) = line.split()

	prefix = git.Tag.prefix
	if refname.startswith(prefix):
	    refname = refname[len(prefix):]
	    tag = git.Tag(refname, old, new)
	    tags.append(tag)
	    continue

	prefix = git.Branch.prefix
	if refname.startswith(prefix):
	    refname = refname[len(prefix):]
	    branch = git.Branch(refname, old, new)

	    if not branch.limb or not branch.limb.bugz:
		if not gatekeeper():
		    error("Pushing branch %s requires gatekeeper permissions\n"
			% refname)
		if not branch.limb:
		    continue

	    branches.append(branch)
	    continue

    branches.sort(key=branch_name)

    if progname == 'pre-receive':
	pre_receive(tags, branches)

    elif progname == 'post-receive':
	post_receive(tags, branches)

    else:
	usage()


def set_global_constants():
    '''
    Initialize several global contants used by this program
    '''

    def get_config(var, array=False, required=False):
	'''
	Return the value of the given git config variable
	'''
	try:
	    val = git.call(['git', 'config', var]).strip()
	    if array:
		val = [x.strip() for x in val.split(',')]
	except:
	    if required:
		error('"Server missing config variable %s"\n' % var)
	    if array:
		val = []
	    else:
		val = ''

	return val


    global git_dir
    global progname
    global debug_flag
    global gatekeeper_groups
    global gatekeepers
    global gitadmin_groups
    global gitadmins
    global email_recipients
    global user
    global project_desc
    global project_url
    global commit_url_fmt
    global bugz_url_fmt

    progname, ext = os.path.splitext(os.path.basename(sys.argv[0]))

    if 'GIT_DIR' in os.environ:
	git_dir = os.path.abspath(os.environ['GIT_DIR'])
	if git_dir.startswith(git_base_dir):
	    rel_dir = git_dir[(len(git_base_dir)+1):]
	else:
	    rel_dir = git_dir
    else:
	usage()

    notice('\n')

    debug_flag = get_config('mvista.debug')

    if debug_flag != '0' and debug_flag != 'False' and debug_flag != 'off':
	debug_flag = True
	notice('%s\n' % progname)
    else:
	debug_flag = False

    gatekeeper_groups = get_config('mvista.gatekeeper-groups', array=True)
    gatekeepers = get_config('mvista.gatekeepers', array=True)
    gitadmin_groups = get_config('mvista.gitadmin-groups', array=True)
    gitadmins = get_config('mvista.gitadmins', array=True)
    email_recipients = get_config('mvista.dev.push-recipients',
	array=True, required=True)

    cmd = ['head', '-1', os.path.join(git_dir, "description")]
    project_desc = git.call(cmd, error=False).strip()

    if not project_desc or project_desc.startswith('Unnamed repository; edit'):
	notice('Warning: project description file not set on server\n')

    project_url = 'http://%s/?p=%s;a=summary' % (git_server, rel_dir)
    commit_url_fmt = 'http://%s/?p=%s;a=commitdiff;h=%%s' % \
			(git_server, rel_dir)
    bugz_url_fmt = 'http://%s/show_bug.cgi?id=%%s' % bugz_server

    user = git.User()

    check_errors()


def main():
    '''
    Main program
    '''

    set_global_constants()

    do_refs()


main()
