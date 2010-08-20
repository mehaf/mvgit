#!/usr/bin/env python
"""
Usage: git-signoff-limb [opts] <limb1>..[<limb2>]
	opts	These options are passed directly to git signoff-mv:
		--ack, --name=<name>, --email=<email>
		--bugz=<bugno>, --disposition=<disp>,
		--source=<source>, --type=<type> ]

Checks out each branch, branch_name, in <limb2>, and runs
"git signoff-mv [opts] <limb1>/branch_name..".

This will add signoff/ack lines to all commits that are in <limb2>
that are not in <limb1>. The name of the current limb is substituted
for <limb2> if it is omitted.
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
    short_opts = "f"
    long_opts = [ "help", "debug", "ack", "force", "name=", "email=",
		  "bugz=", "disposition=", "source=", "type=", "version" ]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    for option, value in options:
	if option == "help":
	    usage()
	elif option == "--debug":
	    config["debug"] = True
	elif option == '--version':
	    sys.stdout.write('mvgit version %s\n' % "@@MVGIT_VERSION@@")
	    sys.exit(0)
	elif value:
	    config["options"].append(option)
	    config["options"].append(value)
	else:
	    config["options"].append(option)

    if len(args) != 1:
        usage()

    match = re.match(r"(.*)\.\.(.*)", args[0])
    if not match:
	usage()

    limb1, limb2 = match.groups()

    if not limb1:
	usage()

    config["limb1"] = limb1
    config["limb2"] = limb2


def signoff_limb():
    options = config["options"]
    limb1name = config["limb1"].rstrip("/")
    limb2name = config["limb2"].rstrip("/")

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

    signed_off_count = 0
    skipped_branchnames = []
    for subname in limb2_subnames:
	limb1_branchname = "%s/%s" % (limb1name, subname)
	limb2_branchname = "%s/%s" % (limb2name, subname)

	if subname.startswith("external."):
	    continue

	if subname not in limb1_subnames:
	    skipped_branchnames.append((limb1_branchname, limb2_branchname))
	    continue

	limb1_branch = git.Branch.get(limb1_branchname)
	limb2_branch = git.Branch.get(limb2_branchname)
	if limb1_branch.id == limb2_branch.id:
	    continue

	cmd = ['git', 'checkout', limb2_branchname]
	git.call(cmd, stdout=sys.stdout, verbose=True)

	cmd = ['git', 'signoff-mv'] + options + ['%s..' % limb1_branchname]

	# ignore the error return from git signoff-mv, until it's fixed
	git.call(cmd, error=None, stdout=sys.stdout, stderr=sys.stderr,
		 verbose=True)

	signed_off_count += 1

    for limb1_branchname, limb2_branchname in skipped_branchnames:
	sys.stdout.write("%s not found, \n" % limb1_branchname)
	sys.stdout.write("  NOT signing off on commits in %s\n" %
			 limb2_branchname)
    else:
	if not signed_off_count:
	    sys.stdout.write("No new commits to signoff.\n")


def main():
    process_options()

    try:
	git.check_repository()
	git.require_mvl6_kernel_repo()

	signoff_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
