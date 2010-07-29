#!/usr/bin/env python
"""
Usage: git-provenance [-a] [-t[t]] [-v] [[-u <branchname>]...]
			[[-i <istr>]...] [[-x <xstr>]...]
			[<branch> [[<commitID>|<changeID>]...]]

For each commit in <branch> (default current branch) since the limb's
common kernel version, this command displays the commit's ID followed
by the commit ID and branch name of each provider commit from which
the commit was (recursively) cherry-picked.

The default output consists of a line containing the commit ID for
each commit in <branch> followed by a line for each provider commit
containing the provider commit's ID and branch name.  The provider
commit ID is preceded by whitespace and is separated from the provider
branch name by a space.

OPTIONS
-------
<branch>::
	The branch whose commits are to be displayed.  It defaults to
	the current branch.

<commitID>::
<changeID>::
	If any <commitID> or <changeID> arguments are given, the output
	is limited to commits in <branch> whose commit ID and/or changeID
	begins with <commitID> or <changeID>.

-a::
	Display abbreviated commit IDs.

-v::
	Verbose.  Append the commit's subject to the line for each commit
	in <branch>.

-t::
	Terse.  Display all information related to a commit in one line.
	The output will consist of one line for each commit in <branch>.
	If a second -t is specified, the information about provider
	branches is omitted from the output.

-i::
	Only display commits in <branch> whose provider branch names
	contain the substring <istr>.  To display all commits that
	were cherry-picked from any branch, use: -i "".

-x::
	Only display commits in <branch> whose provider branch names
	do not contain the substring <xstr>.  To display only commits
	that were not cherry-picked from any branch, use: -x "".

-u::
	Add an additional upstream reference provider branch <branchname>.

"""

import sys
import getopt
import re
import mvgitlib as git


config = {
    "verbose"		: False,
    "terse"		: False,
    "extraterse"	: False,
    "abbrev"		: False,
    "debug"		: False,
    "upstream_branchnames": [],
    "includes"		: [],
    "excludes"		: [],
    "limitIDs"		: [],
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
    short_opts = "ahi:tu:vx:"
    long_opts = ["help", "debug"]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    for option, value in options:
	if option == "--help" or option == "-h":
	    usage()
	elif option == "--debug":
	    config["debug"] = True
	elif option == "-a":
	    config["abbrev"] = True
	elif option == "-t":
	    if config["terse"]:
		config["extraterse"] = True
	    config["terse"] = True
	elif option == "-u":
	    config['upstream_branchnames'].append(value)
	elif option == "-v":
	    config["verbose"] = True
	elif option == "-i":
	    config["includes"].append(value)
	elif option == "-x":
	    config["excludes"].append(value)

    if len(args) > 0:
	config["branchname"] = args[0]
    else:
	config["branchname"] = ""

    if len(args) > 1:
	config["limitIDs"] = args[1:]


def provenance():
    branchname = config["branchname"]
    limitIDs = config["limitIDs"]
    abbrev = config["abbrev"]
    terse = config["terse"]
    extraterse = config["extraterse"]
    verbose = config["verbose"]
    includes = config["includes"]
    excludes = config["excludes"]
    upstream_branchnames = config["upstream_branchnames"]

    if branchname and branchname != 'HEAD':
	branch = git.Branch(branchname)
    else:
	branch = git.current_branch()

    if not branch.id or not branch.exists():
	if branchname:
	    sys.stderr.write('Branch "%s" not found\n' % branchname)
	else:
	    sys.stderr.write('No current branch\n')
	sys.exit(1)

    if upstream_branchnames:
	if not branch.limb:
	    sys.stderr.write('Branch "%s" is not part of a limb.\n' %
				branch.name)
	    sys.exit(1)

	upstream_branches = []
	for ub_name in upstream_branchnames:
	    ub = git.Branch.get(ub_name)
	    if not ub.exists():
		rub = ub.remote_branch
		if not rub.exists():
		    sys.stderr.write("upstream-branch '%s' not found\n"
				     % ub_name)
		    sys.exit(1)
		ub = rub
	    upstream_branches.append(ub)

	branch.limb.upstream_branches = upstream_branches

    ids = []
    for id in limitIDs:
	cmd = ['git', 'rev-parse', id]
	nid = git.call(cmd, error=None, stderr=None).rstrip() or id
	ids.append(nid)
    limitIDs = ids

    for commit, change in branch.provenance():
	commitid = commit.id
	changeid = commit.changeid
	if limitIDs:
	    for id in limitIDs:
		if commitid.startswith(id) or changeid.startswith(id):
		    break
	    else:
		continue

	if change == 'cherry-picked' and (includes or excludes):
	    from_branchnames = [x.name for x in commit.from_branches]
	    if includes:
		for s in includes:
		    for name in from_branchnames:
			if s in name:
			    break
		    else:
			continue
		    break
		else:
		    continue

	    if excludes:
		skip = False
		for s in excludes:
		    for name in from_branchnames:
			if s in name:
			    skip = True
			    break
		    else:
			continue
		    break
		if skip:
		    continue

	elif includes:
	    continue

	if abbrev:
	    commitid = commit.abbrev_id()

	sys.stdout.write(commitid)

	if verbose:
	    sys.stdout.write(" %s" % ' '.join(commit.subject))

	if change == 'cherry-picked':
	    if extraterse:
 		sys.stdout.write("\n")
		continue
	    elif terse:
		fmt = " %s %s"
	    else:
		if abbrev:
		    fmt = "\n %9s %s"
		else:
		    fmt = "\n  %s %s"
	    for i in reversed(range(len(commit.from_commits))):
		if abbrev:
		    commitid = commit.from_commits[i].abbrev_id()
		else:
		    commitid = commit.from_commits[i].id
		branchname = commit.from_branches[i].name
		sys.stdout.write(fmt % (commitid, branchname))

	if terse:
	    sys.stdout.write("\n")
	else:
	    sys.stdout.write("\n\n")


def main():
    process_options()


    try:
	git.check_repository()
	provenance()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
