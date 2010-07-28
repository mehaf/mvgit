#!/usr/bin/env python
"""
Usage: git-ls-limb [-R] [<limb>]
	-R	Recursively list branches in sub-limbs
	-b	List only branches, not limbs
	-l	List only limbs, not branches

Lists the names of the branches and limbs contained in <limb>.
If <limb> is omitted, the branches and limbs in the current limb
are listed.  Unless the -R option is supplied, only branches
contained directly within the limb are listed.
"""

import sys
import getopt
import re
import mvgitlib as git


config = {
    "debug"		: False,
    "recursive"		: False,
    "branches-only"	: False,
    "limbs-only"	: False,
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
    short_opts = "Rbhl"
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
        elif option == "-R":
	    config["recursive"] = True
        elif option == "-b":
	    config["branches-only"] = True
        elif option == "-l":
	    config["limbs-only"] = True

    if config["branches-only"] and config["limbs-only"]:
	config["branches-only"] = False
	config["limbs-only"] = False

    if len(args) > 1:
	usage()

    if len(args) >= 1:
	limb = args[0]
    else:
	limb = None

    config["limb"] = limb


def git_ls_limb():
    limbname = config["limb"]
    recursive = config["recursive"]

    if limbname == None:
	limbname = git.current_limb().name
    else:
	limbname = limbname.strip("/")

    if limbname:
	limb = git.Limb.get(limbname)
	if not limb or not limb.exists():
	    sys.stdout.write("%s: limb not found\n" % limbname)
	    sys.exit(1)

    branches = True
    limbs=True

    if config["branches-only"]:
	limbs = False
    elif config["limbs-only"]:
	branches = False

    if limbs and limbname:
	sys.stdout.write("%s/\n" % limbname)

    for name in git.branchnames(limbname, recursive=recursive,
				branches=branches, limbs=limbs):
	sys.stdout.write("%s\n" % name)


def main():
    process_options()

    try:
	git.check_repository()

	git_ls_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
