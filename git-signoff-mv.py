#!/usr/bin/env python
"""
Usage: git-signoff-mv [opts] <rev-list>
	[opts]
	--ack
		Instead of a "Signed-off-by" line, add an "Acked-by" line.
	--nack
		Instead of a "Signed-off-by" line, add an "Nacked-by" line.
	--name <name>
		Use <name> as the name in the sign-off.
	--email <email>
		Use <email> as the email in the sign-off.
	--bugz <bug_number>
		Add a second bug number to the MR: line of the subheader.
		Use when git cherry-pick-mv didn't do the right thing.
	--disposition <disposition>
		Value of Disposition: line to be added to the commit message
		subheader.
	--type <type>
		Value of Type: line to be added to the commit message subheader.
	-n
		Do not add a sign-off line.
	-f | --force
		git signoff-mv uses git filter-branch internally. Sometimes git
		filter-branch refuses to overwrite the new branch without the
		-f or --force option.  git signoff-mv passes the -f or
		--force option directly to git filter-branch.
	<rev-list>
		List of revisions to sign-off.
"""


import sys
import os
import getopt
import shutil
import subprocess
import mvgitlib as git


config = {
    "debug"		: False,
    "force"		: False,
    "signoff"		: "Signed-off-by",
    "addsignoff"	: True,
    "name"		: None,
    "email"		: None,
    "source"		: None,
    "bugz"		: None,
    "type"		: None,
    "disposition"	: None,
    "changeid"		: None,
    "revlist"		: None,
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
    short_opts = "fn"
    long_opts = [
	"help", "debug", "version", "ack",
	"nack", "name=", "email=", "source=", "bugz=", "type=",
	"disposition=", "changeid=", "force",
    ]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    for option, value in options:
	if option == "--help" or option == "-h":
	    usage()
	elif option == "--debug":
	    config["debug"] = True
	elif option == '--version':
	    sys.stdout.write('mvgit version %s\n' % "@@MVGIT_VERSION@@")
	    sys.exit(0)
	elif option == '--ack':
	    config["signoff"] = "Acked-by"
	elif option == '--nack':
	    config["signoff"] = "Nacked-by"
	    noargs = True
	elif option == '--name':
	    config["name"] = value
	elif option == '--email':
	    config["email"] = value
	elif option == '--source':
	    config['source'] = value
	elif option == '--bugz':
	    config['bugz'] = value
	elif option == '--type':
	    config['type'] = value
	elif option == '--disposition':
	    config['disposition'] = value
	elif option == '--changeid':
	    config['changeid'] = value
	elif option == '-n':
	    config['addsignoff'] = False
	elif option in ('-f', '--force'):
	    config["force"] = True

    if len(args) == 0:
	    usage()

    config["revlist"] = args

    error = False

    if not config["email"]:
	config["email"] = os.environ.get("GIT_COMMITTER_EMAIL")

    if not config["email"]:
	cmd = ["git", "config", "--get", "user.email"]
	config["email"] = git.call(cmd, error=None)

    if not config["email"]:
	error = True
	sys.stdout.write("Either git config user.email, the "
		"GIT_COMMITER_EMAIL\n"
		"environment variable, or --email must be specified.\n")

    if not config["name"]:
	config["name"] = os.environ.get("GIT_COMMITTER_NAME")

    if not config["name"]:
	cmd = ["git", "config", "--get", "user.name"]
	config["name"] = git.call(cmd, error=None)

    if not config["name"]:
	error = True
	sys.stdout.write("Either git config user.name, the "
		"GIT_COMMITER_NAME\n"
		"environment variable, or --name must be specified.\n")

    if error:
	sys.exit(2)


def signoff_mv():
    name = config["name"]
    email = config["email"]

    if email[0] == '<' and email[-1] == '>':
	email = email[1:-1]

    name_email = '"%s <%s>"' % (name, email)

    for v in ("signoff", "source", "bugz", "type", "disposition", "changeid"):
	if config[v] != None:
	    config[v] = '"%s"' % config[v]

    filter_script = ("""python -c '''

import sys
import os
import re

signoff = %s
add_signoff = %s
name_email = %s
source = %s
bugz = %s
type = %s
disposition = %s
changeid = %s
""" % (config["signoff"], config["addsignoff"], name_email, config["source"],
    config["bugz"], config["type"], config["disposition"], config["changeid"]) +
r"""
re_source = re.compile(r"Source:\s+(.*)", re.IGNORECASE)
re_bugz = re.compile(r"MR:\s+(.*)", re.IGNORECASE)
re_type = re.compile(r"Type:\s+(.*)", re.IGNORECASE)
re_disposition = re.compile(r"Disposition:\s+(.*)", re.IGNORECASE)
re_changeid = re.compile(r"ChangeID:\s+(.*)", re.IGNORECASE)
re_signoff = re.compile(r"%s:\s+(.*)" % signoff, re.IGNORECASE)

lines = sys.stdin.readlines()
while lines[-1].strip() == "":
    lines = lines[:-1]

mvheader = False
saw_changeid = False
saw_source = False
saw_bugz = False
saw_type = False
saw_disposition = False

blanks = 0
first_blank_index = None
last_mvheader_index = None
to_delete = []
for i, line in enumerate(lines):
    if line.rstrip() == "":
	blanks += 1
	if blanks == 1:
	    first_blank_index = i
	if blanks > 1:
	    if not last_mvheader_index:
		last_mvheader_index = i
	    break

    if line.lower().startswith("description:"):
	last_mvheader_index = i
	mvheader = True
	break

    m = re_source.match(line)
    if m:
	mvheader = True
	if source != None:
	    if source:
		lines[i] = "Source: %s\n" % source
		saw_source = True
	    else:
		to_delete.append(i)
	continue

    m = re_bugz.match(line)
    if m:
	mvheader = True
	if bugz != None:
	    if bugz:
		bugs = re.split(",\b*", m.group(1))
		if bugz not in bugs:
		    if len(bugs) > 1:
			bugs[1] = bugz
		    else:
			bugs.append(bugz)
		    lines[i] = "MR: " + ", ".join(bugs) + "\n"
		saw_bugz = True
	    else:
		to_delete.append(i)
	continue

    m = re_type.match(line)
    if m:
	mvheader = True
	if type != None:
	    if type:
		lines[i] = "Type: %s\n" % type
		saw_type = True
	    else:
		to_delete.append(i)
	continue

    m = re_disposition.match(line)
    if m:
	mvheader = True
	if disposition != None:
	    if disposition:
		lines[i] = "Disposition: %s\n" % disposition
		saw_disposition = True
	    else:
		to_delete.append(i)
	continue

    m = re_changeid.match(line)
    if m:
	mvheader = True
	if changeid != None:
	    if changeid:
		if changeid == "-":
		    changeid = os.environ["GIT_COMMIT"]
		lines[i] = "ChangeID: %s\n" % changeid
		saw_changeid = True
	    else:
		to_delete.append(i)
	continue

if add_signoff:
    for line in lines:
	m = re_signoff.match(line)
	if m and m.group(1) == name_email:
	    add_signoff = False

if to_delete:
    to_delete.reverse()
    for i in to_delete:
	del lines[i]

    last_deleted = to_delete[-1]
    if lines[last_deleted] == "\n" and lines[last_deleted - 1] == "\n":
	del lines[last_deleted - 1]
	to_delete.append(last_deleted - 1)

if changeid or disposition or type or bugz or source:
    if mvheader:
	last_mvheader_index -= len(to_delete)
    else:
	if not first_blank_index:
	    lines.append("\n")
	    first_blank_index = 1
	else:
	    lines.insert(first_blank_index, "\n")
	last_mvheader_index = first_blank_index + 1

    if changeid and not saw_changeid:
	if changeid == "-":
	    changeid = os.environ["GIT_COMMIT"]
	lines.insert(last_mvheader_index, "ChangeID: %s\n" % changeid)

    if disposition and not saw_disposition:
	lines.insert(last_mvheader_index, "Disposition: %s\n" % disposition)

    if type and not saw_type:
	lines.insert(last_mvheader_index, "Type: %s\n" % type)

    if bugz and not saw_bugz:
	lines.insert(last_mvheader_index, "MR: %s\n" % bugz)

    if source and not saw_source:
	lines.insert(last_mvheader_index, "Source: %s\n" % source)

begin, junk = lines[-1].split(None, 1)
if not (begin.endswith("-off-by:") or
	begin.endswith("acked-by:") or
	begin.endswith("eviewed-by:")):
    lines.append("\n")

if add_signoff:
    lines.append("%s: %s\n" % (signoff, name_email))

sys.stdout.writelines(lines)

'''
""")

    revlist = ' '.join(config["revlist"])
    cmd = ['git', 'filter-branch', '--msg-filter', filter_script]
    if config["force"]:
	cmd.append("-f")
    cmd.append(revlist)
    rc = subprocess.call(cmd)

    cmd = ['git', 'rev-parse', '--git-dir']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    gitdir = p.stdout.read().rstrip()
    rc = p.wait()
    original = gitdir + "/refs/original"
    if os.path.isdir(original):
	shutil.rmtree(original)


def main():
    process_options()

    try:
	git.check_repository()
	signoff_mv()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
