#!/usr/bin/env python
"""
Usage: git-rebase-limb [opts] <upstream> [<limb>]
	opts	These options are passed directly to git-rebase:
		--verbose, --whitespace=<nowarn|warn|error|error-all|strip>,
		--preserve-merges

If <limb> is specified, git-rebase-limb will perform an automatic checkout
of the common branch in <limb> before doing anything else. Otherwise,
it remains on the current branch.

Each branch in the current limb is rebased on the correspondingly named
branch in <upstream>. For each branch, branch_name, in the current
limb, git-rebase-limb runs git rebase [opts] <upstream>/branch_name
<current_limb>/branch_name.
"""

import sys
import getopt
import re
import mvgitlib as git

config = {
    "debug"		: False,
    "options"		: [],
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
    short_opts = "h"
    long_opts = [
	"help", "debug", "verbose", "whitespace=", "preserve-merges",
	"version",
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
	elif value:
	    if option.startswith("--"):
		config["options"].append("%s=%s" % (option, value))
	    else:
		config["options"].append(option)
		config["options"].append(value)
	else:
	    config["options"].append(option)

    if len(args) < 1 or len(args) > 2:
        usage()

    config["upstream"] = args[0]

    if len(args) > 1:
	limb = args[1]
    else:
	limb = None
    
    config["limb"] = limb


def rebase_limb():
    options = config["options"]
    upstreamname = config["upstream"]
    limbname = config["limb"]

    if limbname:
	common_branch = "%s/common" % limbname.rstrip("/")
	cmd = ['git', 'checkout', common_branch]
	git.call(cmd, stdout=sys.stdout, verbose=True)

    original_branch = git.current_branch()
    limb = git.current_limb()
    limbname = limb.name

    upstreamname = upstreamname.rstrip("/")
    upstream = git.Limb.get(upstreamname)

    if not limb.exists():
	sys.stdout.write("%s: not found\n" % limbname)
	sys.exit(1)

    if not upstream.exists():
	sys.stdout.write("%s: not found\n" % upstreamname)
	sys.exit(1)

    upstream_subnames = git.subnames(upstreamname)
    limb_subnames = git.subnames(limbname)

    not_rebased = []
    for subname in limb_subnames:
	limb_branchname = "%s/%s" % (limbname, subname)
	upstream_branchname = "%s/%s" % (upstreamname, subname)

	if subname not in upstream_subnames:
	    not_rebased.append((limb_branchname, upstream_branchname))
	    continue

	limb_branch = git.Branch.get(limb_branchname)
	upstream_branch = git.Branch.get(upstream_branchname)
	if limb_branch.contains(upstream_branch):
	    continue

	cmd = ['git', 'checkout', limb_branchname]
	git.call(cmd, stdout=sys.stdout, verbose=True)

	cmd = ['git', 'rebase'] + options + [upstream_branchname]
	git.call(cmd, stdout=sys.stdout, verbose=True)

    for subname in upstream_subnames:
	if subname in limb_subnames:
	    continue

	limb_branchname = "%s/%s" % (limbname, subname)
	upstream_branchname = "%s/%s" % (upstreamname, subname)

	cmd = ['git', 'branch', limb_branchname, upstream_branchname]
	git.call(cmd, stdout=sys.stdout, verbose=True)

    # restore original branch
    if git.current_branch() != original_branch:
	cmd = ['git', 'checkout', original_branch.name]
	git.call(cmd, stdout=sys.stdout, verbose=True)

    if not_rebased:
	sys.stderr.write("\n")
	for limb_branchname, upstream_branchname in not_rebased:
	    sys.stderr.write("NOT rebasing %s, no %s\n" %
		(limb_branchname, upstream_branchname))


def main():
    process_options()

    try:
	git.check_repository()
	rebase_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
