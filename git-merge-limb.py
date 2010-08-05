#!/usr/bin/env python
"""
Usage: git-merge-limb [opts] <remote> [<limb>]
        opts    These options are passed directly to git-merge:
                --stat, --no-stat, --log, --no-log, -s, --strategy=

If <limb> is specified, git-merge-limb will perform an automatic checkout
of the common branch in <limb> before doing anything else. Otherwise,
it remains on the current branch.

Each branch in the current limb merges from the correspondingly named
branch in <remote>.  For each branch, branch_name, in the current
limb, git-merge-limb runs git merge [opts] <remote>/branch_name
<current_limb>/branch_name.
"""

import sys
import getopt
import re
import mvgitlib as git


config = {
    "debug"                : False,
    "options"              : [],
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
    short_opts = "hs:"
    long_opts = [
        "help", "debug", "stat", "no-stat", "log", "no-log", "strategy=",
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

    config["remote"] = args[0]

    if len(args) > 1:
        limb = args[1]
    else:
        limb = None

    config["limb"] = limb


def merge_limb():
    options = config["options"]
    remotename = config["remote"]
    limbname = config["limb"]

    if limbname:
	limbname = limbname.rstrip('/')
	limb = git.Limb.get(limbname)
	branch = limb.repository_branches()[0]
        git.call(['git', 'checkout', branch], stdout=sys.stdout, verbose=True)
    else:
	limb = git.current_limb()
	limbname = limb.name

    remotename = remote.rstrip("/")
    remote = git.Limb.get(remotename)

    if not limb.exists():
        sys.stdout.write("%s: not found\n" % limbname)
        sys.exit(1)

    if not remote.exists():
        sys.stdout.write("%s: not found\n" % remotename)
        sys.exit(1)

    limb_subnames = git.subnames(limbname)
    remote_subnames = git.subnames(remotename)

    for subname in remote_subnames:
	if subname not in limb_subnames:
            limb_branchname = "%s/%s" % (limbname, subname)
            remote_branchname = "%s/%s" % (remotename, subname)
	    cmd = ['git', 'branch', limb_branchname, remote_branchname]
	    git.call(cmd, stdout=sys.stdout, verbose=True)

    for subname in limb_subnames:
        if subname not in remote_subnames:
	    continue
        limb_branchname = "%s/%s" % (limbname, subname)
        remote_branchname = "%s/%s" % (remotename, subname)

	limb_branch = Limb.get(limb_branchname)
	remote_branch = Limb.get(remote_branchname)
	if limb_branch.contains(remote_branch):
	    sys.stdout.write("%s is up-to-date.\n" % limb_branchname)
	    continue

        try:
	    cmd = ['git', 'checkout', limb_branchname]
	    git.call(cmd, stdout=sys.stdout, verbose=True)
	    cmd = ['git', 'merge', remote_branchname]
	    git.call(cmd, stdout=sys.stdout, verbose=True)

        except git.GitError:
            cmdline = ' '.join([re.sub(".*/", "", sys.argv[0])] + sys.argv[1:])
            sys.stdout.write("\n")
            sys.stdout.write("After resolving this issue, you may continue\n")
            sys.stdout.write("the merge by re-running the command:\n")
            sys.stdout.write("  %s\n" % cmdline)

            if config["debug"]:
                sys.stdout.write("\n")
                raise

            sys.exit(1)


def main():
    process_options()

    try:
        git.check_repository()
        merge_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

        if config["debug"]:
            sys.stdout.write("\n")
            raise

        sys.exit(1)


main()
