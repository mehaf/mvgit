#!/usr/bin/env python
"""
Usage: git-changes [-l] [-v] [-a] [<left>] [<right>]
       git-changes --dependents <branch> [<limb> ...]

If -l is specified:
    <right> must not be specified.  The limb specified by <left>
    (the current limb, if <left> is omitted) is examined.  Each
    of the limb's branches that has pending changes from one or
    more branches is listed, followed by the status of each
    branch on which it depends.

If -l is not specified:
    If <left> is not specified, the name of the current branch is listed,
    followed by the status of each branch on which it depends.

    If <left> is specified, the output is a list of commit IDs, one per
    line, of commits in <left> that are not in <right> (the current branch,
    if <right> is omitted) based on the Change IDs of the commits in both
    branches.  If -v is specified, each commit's short description is
    appended to the its commit ID.

If -a is specified include rejected_changes.  Normally, changes found
one-per-line in the file MONTAVISTA/rejected_changes in the destination
branch are omitted.  When -a is specified, all changes, including
those in MONTAVISTA/rejected_changes are included in the output.

Format of pending change status:
    Each line of change status consists of two integers, separated by
    a plus (+) sign, followed by the name of the branch containing the
    pending changes.  The first integer is the number of pending commits
    contained directly in the branch.  The second integer is the number
    of pending commits contained in branches that that branch depends
    on (recursively).
    Example:
	mvl-2.6.24/dev.x86
	    3 + 2 mvl-2.6.24/feature.rt

    There are 3 commits in the mvl-2.6.24/feature.rt branch that haven't
    been propagated to the mvl-2.6.24/dev.x86 branch, and there are 2
    commits in branches that the mvl-2.6.24/feature.rt branch depends
    on that haven't been propagated to the mvl-2.24/feature.rt branch.

If --dependents is specified:
    The output is a list of all branches in each <limb> which depend on
    <branch>.  The current limb is used if <limb> is omitted.

"""

import sys
import getopt
import re
import mvgitlib as git


config = {
    "verbose"		: False,
    "debug"		: False,
    "limb"		: False,
    "left"		: None,
    "right"		: None,
    "with_rejects"	: False,
    "dependents"	: None,
    "limbs"		: [],
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
    short_opts = "ahlv"
    long_opts = ["help", "debug", "dependents=", "version"]

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
	elif option == "-v":
	    config["verbose"] = True
	elif option == "-l":
	    config["limb"] = True
	elif option == "-a":
	    config["with_rejects"] = True
	elif option == "--dependents":
	    config["dependents"] = value

    if config["dependents"]:
	config["limbs"] = args
	return

    if len(args) > 2:
	usage()

    if len(args) > 0:
	config["left"] = args[0]

    if len(args) > 1:
	if config["limb"]:
	    usage()
	config["right"] = args[1]


def git_pending_commits():
    left = config["left"]
    right = config["right"]
    with_rejects = config["with_rejects"]

    if right:
	right = git.Branch(right)
    else:
	right = git.current_branch()
    if left:
	left = git.Branch(left)

    if not left.id:
	sys.stderr.write("Invalid branch: %s\n" % left.name)
	sys.exit(1)

    if not right.id:
	sys.stderr.write("Invalid branch: %s\n" % right.name)
	sys.exit(1)

    left_base = left.upstream_version

    if not left_base:
	sys.stderr.write("Invalid upstream_version for %s\n" % left.name)
	sys.exit(1)

    commits = git.changeid_diff(left, right, with_rejects=with_rejects)

    if commits and not commits[0].contains(left_base):
	sys.stderr.write("Error: upstream version: %s\n"
	    "       is not a first-parent ancestor of:\n"
	    "       %s\n" % (left_base, left.name))
	sys.exit(1)

    if config["verbose"]:
	cmd = ["git", "rev-list", "-1", "--oneline"]
	for commit in commits:
	    git.call(cmd + [commit.id], stdout=sys.stdout)
    else:
	for commit in commits:
	    sys.stdout.write("%s\n" % commit.id)


def valid_provider(branch, provider):
    if not provider.id:
	remote_alias = git.remote_alias()
	remote_provider = git.Branch('%s/%s' % (remote_alias, provider.name))
	if remote_provider.id:
	    return remote_provider

	sys.stderr.write("\nERROR: %s depends on\n" % branch.name)
	sys.stderr.write("%s, which does not exist\n" % provider.name)
	sys.exit(1)

    return provider

cached_change_count = {}

def change_count(left, right):
    with_rejects = config["with_rejects"]

    if (left, right) in cached_change_count:
	return cached_change_count[(left, right)]

    if 'reference' in right.provider_flags[left]:
	count = 0
    else:
	count = len(git.changeid_diff(left, right, with_rejects=with_rejects))

    cached_change_count[(left, right)] = count

    return count


cached_recursive_change_count = {}

def recursive_change_count(branch):
    if branch in cached_recursive_change_count:
	return cached_recursive_change_count[branch]

    count = 0
    for prov in branch.providers:
	prov = valid_provider(branch, prov)
	count += change_count(prov, branch)
	count += recursive_change_count(prov)

    cached_recursive_change_count[branch] = count

    return count


def git_pending_branch(branch):
    total_changes = 0

    for prov in branch.providers:
	prov = valid_provider(branch, prov)
	changes = change_count(prov, branch)
	rchanges = recursive_change_count(prov)
	if (changes or rchanges) and not total_changes:
	    flags = " ".join(branch.flags)
	    if flags:
		flags = " (%s)" % flags
	    sys.stdout.write("%s%s\n" % (branch.name, flags))
	total_changes += changes + rchanges
	if changes or rchanges:
	    sys.stdout.write("%6d + %d\t%s\n" % (changes, rchanges, prov.name))

    if not total_changes:
	sys.stdout.write("No pending changes in %s\n" % branch.name)

    return total_changes


def git_pending_limb():
    verbose = config["verbose"]

    limb = config["left"]
    if limb:
	limb = git.Limb.get(limb)
    else:
	limb = git.current_limb()

    total_changes = 0
    for branch in limb.repository_branches:
	if not verbose:
	    if 'frozen' in branch.flags:
		continue
	    if 'deferred' in branch.flags:
		continue
	    for prov in branch.providers:
		prov = valid_provider(branch, prov)
		if change_count(prov, branch) or recursive_change_count(prov):
		    break
	    else:
		continue

	branch_changes = git_pending_branch(branch)
	total_changes += branch_changes

	if branch_changes and branch != limb.repository_branches[-1]:
	    sys.stdout.write("\n")

    if not total_changes:
	sys.stdout.write("No pending changes in %s/\n" % limb.name)


def git_dependent_branches():
    provider = config["dependents"].strip('/')
    if provider:
	provider = git.Branch(provider)
    else:
	provider = git.current_branch()

    limbs = config["limbs"]
    if limbs:
	limbs = [git.Limb.get(x.strip('/')) for x in limbs]
    else:
	limbs = [git.current_limb()]

    for limb in limbs:
	for branch in provider.all_dependents(limb):
	    sys.stdout.write('%s\n' % branch.name)


def main():
    process_options()


    try:
	git.check_repository()

	if config["dependents"]:
	    git_dependent_branches()
	elif config["limb"]:
	    git_pending_limb()
	else:
	    if config["left"]:
		git_pending_commits()
	    else:
		git_pending_branch(git.current_branch())

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
