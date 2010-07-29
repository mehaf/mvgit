#!/usr/bin/env python
"""
Usage: git-diff-limb [opts] [<limb1>]..[<limb2>] [--] [<path>...]
	[opts]	These options are passed directly to "git diff":
		-p, -u, --unified=<n>, --stat, --shortstat, --summary,
		--name-only, --name-status, --color, --no-color,
		--color-words, --no-renames, --check, --full-index,
		--binary, -B, -M, -C, --find-copies-harder, -R, -b,
		-w, --ext-diff, --no-ext-diff


Each branch in <limb1> is compared to the correspondingly
named branch in <limb2>.  git-diff-limb runs "git diff [opts]
<limb1>/branch_name..<limb2>/branch_name [--] [<path>...]" for each branch
in <limb1> and <limb2>.  The name of the current limb is substituted
for <limb1> or <limb2> if either is omitted.
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
    short_opts = "bhpBMCRw"
    long_opts = [
	"help", "debug", "unified=", "stat", "shortstat", "summary",
	"name-only", "name-status", "color", "no-color",
	"color-words", "no-renames", "check", "full-index",
	"binary", "find-copies-harder", "ext-diff", "no-ext-diff"
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
	elif value:
	    if option.startswith("--"):
		config["options"].append("%s=%s" % (option, value))
	    else:
		config["options"].append(option)
		config["options"].append(value)
	else:
	    config["options"].append(option)

    if len(args) < 1:
	usage()

    match = re.match(r"(.*)\.\.(.*)", args[0])
    if not match:
	usage()

    config["limb1"], config["limb2"] = match.groups()
    config["paths"] = args[1:]


def diff_limb():
    options = config["options"]
    limb1name = config["limb1"].rstrip("/")
    limb2name = config["limb2"].rstrip("/")
    paths = config["paths"]

    if not limb1name:
	limb1name = git.current_limb().name

    if not limb2name:
	limb2name = git.current_limb().name

    limb1 = git.Limb.get(limb1name)
    if not limb1.exists():
	sys.stdout.write("%s: not found\n" % limb1name)
	sys.exit(1)

    limb2 = git.Limb.get(limb2name)
    if not limb2.exists():
	sys.stdout.write("%s: not found\n" % limb2name)
	sys.exit(1)

    limb1_subnames = git.subnames(limb1name)
    limb2_subnames = git.subnames(limb2name)

    not_found = False
    diff_branches = []
    for subname in sorted(set(limb1_subnames + limb2_subnames)):
	branch1name = "%s/%s" % (limb1name, subname)
	branch2name = "%s/%s" % (limb2name, subname)
	if subname not in limb1_subnames:
	    sys.stdout.write("WARNING, non-existent branch: %s\n" % branch1name)
	    not_found = True
	    continue

	if subname not in limb2_subnames:
	    sys.stdout.write("WARNING, non-existent branch: %s\n" % branch2name)
	    not_found = True
	    continue

	branch1 = git.Branch.get(branch1name)
	branch2 = git.Branch.get(branch2name)
	if branch1.id == branch2.id:
	    continue

	diff_branches.append([branch1name, branch2name])

    if not_found and diff_branches:
	sys.stdout.write("\n")

    for branch1name, branch2name in diff_branches:
	cmd = ['git', '--no-pager', 'diff'] + options
	cmd.append('%s..%s' % (branch1name, branch2name))
	cmd += paths

	git.call(cmd, stdout=sys.stdout, verbose=True)


def main():
    process_options()

    try:
	git.check_repository()
	diff_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
