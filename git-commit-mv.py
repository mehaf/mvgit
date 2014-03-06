#!/usr/bin/env python
"""
Usage: git-commit-mv [[-c|-C] <commit> [-x]] [--bugz <bugno>] [--type <string>]
		     [--disposition <string>] [--source <string>]
		     [--no-edit] [--amend] [git-commit options]

       git-commit-mv --version

    OPTIONS
	-C <commit>
		Take existing commit object, and reuse the log message
		and the authorship information (including the timestamp)
		when creating the commit.

	-c <commit>
		Same as -C <commit> above, but lets you edit the commit
		message.

	--bugz <bugno>, --mr <bugno>
		Fill in the "MR:" field of the MontaVista commit header with
		<bugno>.

	--source <string>
		Fill in the "Source:" field of the MontaVista commit header
		with the string specified in the command option.

	--type <string>
		Fill in the "Type:" field of the MontaVista commit header
		with the string specified in the command option.

	--disposition <string>
		Fill in the "Disposition:" field of the MontaVista commit
		header with the string specified in the command option.

	--no-edit
		Do not run $GIT_EDITOR to edit the commit message but instead
		simply commit the changes with the header generated via the
		command line options. This option is primarily inteded for
		use by higher level automation scripts.

	--no-signoff
		Default behavior is to add a Signed-off-by: line to the end
		of the commit message.  This option disables that.

	--amend
		Instead of creating a new commit, amend the commit at the
		tip of the current branch by folding the current changes
		into it.

	--changeid <hash>
		Don't use this option.  Let it be computed for you.  This
		option is intended for use by other commands.
	-x
		Append a "(commit cherry-picked from XXXXXX)" line.
		May only be used with -c or -C.  This option is intended for
		use by other commands.
"""


import sys
import os
import getopt
import shutil
import subprocess
import time
import tempfile
import mvgitlib as git


opt = {
    "debug"		: False,
    "source"		: None,
    "bugz"		: None,
    "type"		: None,
    "disposition"	: None,
    "changeid"		: None,
    "message-commit"	: None,
    "add-picked-message": None,
    "no-edit"		: False,
    "addsignoff"	: True,
    "delete_changeid"	: False,
    "commit_all"	: False,
    "amend"		: False,
    "reset_author"	: False,
    "commit_options"	: [],
}


def usage(msg=None):
    """
    Print a usage message and exit with an error code
    """

    if msg:
	sys.stderr.write("%s\n" % str(msg).rstrip())

    sys.stderr.write("\n%s\n" % __doc__.strip())
    sys.exit(1)


def process_options():
    short_opts = "aC:c:x"
    long_opts = [
	"help", "debug", "version", "source=", "bugz=", "mr=", "type=",
	"disposition=", "changeid=", "no-edit", "no-signoff",
	"amend", "reset_author",
    ]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    for option, value in options:
	if option == "--help" or option == "-h":
	    usage()
	elif option == "--debug":
	    opt["debug"] = True
	elif option == '--version':
	    sys.stdout.write('mvgit version %s\n' % "@@MVGIT_VERSION@@")
	    sys.exit(0)
	    noargs = True
	elif option in ('-a', '--all'):
	    opt['commit_all'] = True
	    opt['commit_options'].append(option)
	elif option == '--amend':
	    opt['amend'] = True
	    opt['commit_options'].append(option)
	elif option == '--source':
	    opt['source'] = value
	elif option in ('--bugz', '--mr'):
	    opt['bugz'] = value
	elif option == '--type':
	    opt['type'] = value
	elif option == '--disposition':
	    opt['disposition'] = value
	elif option == '--changeid':
	    if value:
		opt['changeid'] = value
	    else:
		opt['delete_changeid'] = True
	elif option in ('-c', '-C'):
	    if opt['message-commit']:
		sys.stdout.write('Error: Only one of -c and -C may be specified.\n')
		sys.exit(1)
	    opt['message-commit'] = value
	    if option == '-C':
		opt['no-edit'] = True
	elif option == '--no-signoff':
	    opt['addsignoff'] = False
	elif option == '--no-edit':
	    opt['no-edit'] = True
	elif option == '--reset-author':
	    opt['reset_author'] = True
	elif option == '-x':
	    opt['add-picked-message'] = True
	elif value:
	    if option.startswith("--"):
		opt["commit_options"] += [option, value]
	    else:
		opt["commit_options"].append(option)
		opt["commit_options"].append(value)
	else:
	    opt["commit_options"].append(option)


    # validate options
    message_commit = opt['message-commit']

    if opt['add-picked-message'] and not message_commit:
	sys.stdout.write("Error: -x may only be used with -c or -C\n")
	sys.exit(1)

    if opt["amend"]:
	if message_commit:
	    sys.stdout.write("Error: --amend can't be used with -c or -C\n")
	    sys.exit(1)
	message_commit = 'HEAD^0'

    if message_commit:
	commit = git.read_commit(message_commit)
	if commit:
	    opt['message-commit'] = commit
	else:
	    sys.stdout.write('Error: Invalid commit "%s".\n' % id)
	    sys.exit(1)


def generate_changeid(header, body):
    hcmd = ['git', 'hash-object', '--stdin']
    hash = subprocess.Popen(hcmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    hash.stdin.write(header)
    hash.stdin.write(body)
    timestr = time.asctime()
    hash.stdin.write(timestr)

    pcmd = ['git', 'rev-list', '-1', 'HEAD^0']
    parent = subprocess.Popen(pcmd, stdout=subprocess.PIPE)
    data = parent.stdout.read()
    hash.stdin.write(data)
    rc = parent.wait()
    if rc != 0:
	raise Exception("Command %s returned %d\n" % (" ".join(pcmd), rc))

    dcmd = ['git', 'diff', '--cached', 'HEAD^0']
    diff = subprocess.Popen(dcmd, stdout=subprocess.PIPE)
    while True:
	data = diff.stdout.read(4096)
	if len(data) == 0:
	    break
	hash.stdin.write(data)
    rc = diff.wait()
    if rc != 0:
	raise Exception("Command %s returned %d\n" % (" ".join(dcmd), rc))

    if opt["commit_all"]:
	dcmd = ['git', 'diff']
	diff = subprocess.Popen(dcmd, stdout=subprocess.PIPE)
	while True:
	    data = diff.stdout.read(4096)
	    if len(data) == 0:
		break
	    hash.stdin.write(data)
	rc = diff.wait()
	if rc != 0:
	    raise Exception("Command %s returned %d\n" % (" ".join(dcmd), rc))

    hash.stdin.close()
    changeid = hash.stdout.read()
    rc = hash.wait()
    if rc != 0:
	raise Exception("Command %s returned %d\n" % (" ".join(hcmd), rc))

    return changeid.strip()


def commit_message():
    message_commit = opt["message-commit"]
    addsignoff = opt["addsignoff"]

    subject = ("Oneline summary of change, less then 60 characters\n"
		"# *** Leave above line blank for clean log formatting ***")
    source = "Mentor Graphics Corporation | URL | Some Guy <email@addr>"
    bugz = "Jira ID"
    type = "Defect Fix | Security Fix | Enhancement | Integration"
    disposition = ("Submitted to | Needs submitting to | Merged from |"
		    " Accepted by | Rejected by | Backport from | Local")
    changeid = None
    body = []

    if message_commit:
	subject = '\n'.join(message_commit.subject)
	body = message_commit.body
	mv_header_lines = message_commit.mv_header_lines
	mv_header_dict = message_commit.mv_header_dict
	body = body[len(mv_header_lines):]
	if opt['add-picked-message']:
	    body.append("(cherry picked from commit %s)" % message_commit.id)

	if 'mr' in mv_header_dict:
	    bugz = mv_header_dict['mr']
	if 'source' in mv_header_dict:
	    source = mv_header_dict['source']
	if 'type' in mv_header_dict:
	    type = mv_header_dict['type']
	if 'disposition' in mv_header_dict:
	    disposition = mv_header_dict['disposition']
	if 'changeid' in mv_header_dict:
	    changeid = mv_header_dict['changeid']

    if opt["source"]:
    	source = opt["source"]
    if opt["bugz"]:
	if bugz.startswith('Jira'):
	    bugz = opt["bugz"]
	else:
	    bugz = bugz.split(',', 2)[0].strip()
	    if bugz != opt["bugz"]:
		bugz += ", " + opt["bugz"]
    if opt["type"]:
	type = opt["type"]
    if opt["disposition"]:
	disposition = opt["disposition"]

    if addsignoff:
	cmd = ['git', 'var', 'GIT_COMMITTER_IDENT']
	ident = git.call(cmd)
	ident = ident[0:(ident.rindex('>')+1)]
	signoff_line = "Signed-off-by: " + ident
	if signoff_line not in body:
	    if not body or ("-by: " not in body[-1] and
		    not body[-1].lower().startswith('cc:')):
		body.append("")
	    body.append(signoff_line)

    header = """%s

Source: %s
MR: %s
Type: %s
Disposition: %s
""" % (subject, source, bugz, type, disposition)

    body = '\n'.join(body) + '\n'

    if opt["delete_changeid"]:
	changeid = None
    elif opt['repo-type'] == 'mvl6-kernel':
	if opt["changeid"]:
	    changeid = opt["changeid"]
	elif not changeid:
	    changeid = generate_changeid(header, body)

    if changeid:
	header += "ChangeID: %s\n" % changeid

    if not body.startswith("Description:\n"):
	header += "Description:\n\n"

    return header + body


def validate_commit(commit):
    commit = git.read_commit(commit)
    errors = commit.mv_header_errors()
    subject = '\n'.join(commit.subject)
    if subject.startswith("Oneline summary of change,"):
	errors.append("Bad subject: %s\n" % subject)
    for error in errors:
	sys.stdout.write("Warning: "+ error)


def commit_mv():
    no_edit = opt["no-edit"]
    message_commit = opt["message-commit"]
    reset_author = opt["reset_author"]
    commit_options = opt["commit_options"]

    if message_commit and not reset_author:
	cmd = ['git', 'log', '-1', '--pretty=format:%an\n%ae\n%ai',
		message_commit.id]
	a_name, a_email, a_date = git.call(cmd).splitlines()
	os.environ["GIT_AUTHOR_NAME"] = a_name
	os.environ["GIT_AUTHOR_EMAIL"] = a_email
	os.environ["GIT_AUTHOR_DATE"] = a_date

    if not no_edit:
	commit_options.append("-e")

    msg = commit_message()
    msgfile = tempfile.NamedTemporaryFile()
    msgfile.write(msg)
    msgfile.flush()

    commit_options += ["--file", msgfile.name]

    cmd = ['git', 'commit'] + commit_options
    commit = subprocess.Popen(cmd)
    rc = commit.wait()
    msgfile.close()

    if rc != 0:
	sys.exit(rc)

    validate_commit('HEAD^0')


def main():
    try:
	process_options()

	git.check_repository()
	opt['repo-type'] = git.repo_type()

	commit_mv()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if opt["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
