#!/usr/bin/env python
"""
Usage: git-limb
       git-limb [-f ] [-R] [<limb1>] [<limb2>]
       git-limb [-m | -M] [-R] [<oldlimb>] <newlimb>
       git-limb [-d] [-R] <limb>
       git-limb [--deps] [<limb>

With no arguments given, a list of branches in the current limb will
be shown, the current branch will be highlighted with an asterisk.

In the second form, a new limb named <limb1> will be created.  It will
start out with copies of all the branches in <limb2>.  If <limb2> is
not given, the limb will be a copy of the current limb.

With a -m or -M option, <oldlimb> will be renamed to <newlimb>.  If
<newlimb> exists, -M must be used to force the rename to happen.
Unless the -R (recursive) option is specified, only branches directly
in the limb will be moved.  If -R is specified all sub-limbs are
also moved.

With a -d option, the branches in <limb> will be deleted.
The -R options will also cause sub-limbs to be deleted.

If --deps is specified, the contents of <limb>'s branch
dependencies file is output, or the current limb if <limb>
isn't specified.

Otherwise, if <limb1> is specified, a new limb, named <limb1> is
created, containing copies of all the branches in <limb2>, or the
current limb if <limb2> is omitted.  If <limb1> already exists, it
will not be overwritten unless -f is specified.  If -R is specified,
sub-limbs are also copied.
"""

import sys
import getopt
import re
import mvgitlib as git


config = {
    "debug"		: False,
    "force"		: False,
    "move"		: False,
    "delete"		: False,
    "recursive"		: False,
    "checkout"		: False,
    "deps"		: False,
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
    short_opts = "cfhmMdR"
    long_opts = [ "help", "debug", "deps", "version" ]

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
        elif option == "-c":
	    config["checkout"] = True
        elif option == "-f":
	    config["force"] = True
        elif option == "-m":
	    config["move"] = True
        elif option == "-M":
	    config["move"] = True
	    config["force"] = True
        elif option == "-d":
	    config["delete"] = True
        elif option == "-R":
	    config["recursive"] = True
        elif option == "--deps":
	    config["deps"] = True

    if len(args) > 2:
	usage()

    if len(args) >= 1:
	limb1 = args[0].rstrip("/")
    else:
	limb1 = None

    if len(args) >= 2:
	limb2 = args[1].rstrip("/")
    else:
	limb2 = None

    if config["delete"] and limb2:
	usage()

    if config["checkout"] and (not limb1 or config["delete"] or config["move"]):
	usage()
    
    config["limb1"] = limb1
    config["limb2"] = limb2


def git_list_branches():
    branch_name = git.current_branch().name
    limb_name = git.current_limb().name

    if limb_name:
	sys.stdout.write("%s/\n" % limb_name)

	for name in git.branchnames(limb_name):
	    if name == branch_name:
		sys.stdout.write("* %s\n" % name)
	    else:
		sys.stdout.write("  %s\n" % name)


def git_create_limb():
    limb1name = config["limb1"]
    limb2name = config["limb2"]
    force = config["force"]
    recursive = config["recursive"]
    checkout = config["checkout"]
    checkout_name = None

    branch = git.Branch.get(limb1name)
    if branch.exists():
	sys.stdout.write("%s is an existing branch, need a limb name\n" %
		limb1name)
	sys.exit(1)

    if limb2name:
	branch = git.Branch.get(limb2name)
	if branch.exists():
	    sys.stdout.write("%s is an existing branch, need a limb\n" %
		    limb2name)
	    sys.exit(1)
	limb2 = git.Limb.get(limb2name)
    else:
	limb2 = git.current_limb()
	limb2name = limb2.name

    if not limb2.exists():
	if not limb2name:
	    limb2name = '""'
	sys.stdout.write("%s: not found\n" % limb2name)
	sys.exit(1)

    if limb1name == limb2name:
	sys.stdout.write("%s and %s are identical.\n" % (limb1name, limb2name))
	return

    limb1_branchnames = git.branchnames(limb1name, recursive=recursive)

    if limb1_branchnames and not force:
	sys.stderr.write("%s exists.  Use -f to force overwrite.\n" % limb1name)
	sys.exit(1)

    limb2_subnames = git.subnames(limb2name, recursive=recursive)

    try:
	current = git.current_branch()
	current_name = current.name
    except:
	current_name = None

    if current_name and current_name in limb1_branchnames:
	git.call(['git', 'checkout', current.id], stdout=None, stderr=None)
	checkout = True
	if current.subname in limb2_subnames:
	    checkout_name = current_name

    limb1_subnames = git.subnames(limb1name, limb1_branchnames)

    for subname in limb2_subnames:
	destname = "%s/%s" % (limb1name, subname)
	sourcename = "%s/%s" % (limb2name, subname)

	dest = git.Branch.get(destname)
	source = git.Branch.get(sourcename)
	if dest.id != source.id:
	    cmd = ['git', 'branch', '-f', destname, sourcename]
	    git.call(cmd, stdout=sys.stdout, verbose=True)

	if not checkout_name:
	    checkout_name = destname

    for subname in limb1_subnames:
	if subname in limb2_subnames:
	    continue

	del_name = "%s/%s" % (limb1name, subname)
	cmd = ['git', 'branch', '-D', del_name]
	git.call(cmd, stdout=sys.stdout, verbose=True)

    if checkout:
	if not checkout_name:
	    sys.stderr.write("No branch in %s to checkout.\n" % limb2name)
	    sys.exit(1)

	cmd = ['git', 'checkout', checkout_name]
	if current_name and checkout_name == current.name:
	    git.call(cmd, stdout=None, stderr=None)
	else:
	    git.call(cmd, stdout=sys.stdout, verbose=True)


def git_move_limb():
    force = config["force"]
    recursive = config["recursive"]

    if config["limb2"]:
       oldlimbname = config["limb1"]
       newlimbname = config["limb2"]
    else:
	oldlimbname = git.current_limb().name
	newlimbname = config["limb1"]

    oldlimb = git.Limb.get(oldlimbname)
    if not oldlimb.exists():
	if not oldlimbname:
	    oldlimbname = '""'
	sys.stderr.write("%s: not found\n" % oldlimbname)
	sys.exit(1)

    newlimb = git.Limb.get(newlimbname)
    if newlimb.exists():
	if force:

	    cmd = ['git', 'branch', '-D']
	    cmd += git.branchnames(newlimbname, recursive=recursive)
	    git.call(cmd, stdout=sys.stdout)
	else:
	    sys.stderr.write("%s: already exists.  Use -M to overwrite.\n"
				 % newlimbname)
	    sys.exit(1)

    if force:
	m_opt = "M"
    else:
	m_opt = "m"

    branchnames = git.branchnames(oldlimbname, recursive=recursive)
    subnames = [x[(len(oldlimbname)+1):] for x in branchnames]
    for subname in subnames:
	old_name = "%s/%s" % (oldlimbname, subname)
	new_name = "%s/%s" % (newlimbname, subname)
	cmd = ['git', 'branch', '-%s' % m_opt, old_name, new_name]
	git.call(cmd, stdout=sys.stdout, verbose=True)


def git_delete_limb():
    limbname = config["limb1"]
    recursive = config["recursive"]

    limb = git.Limb.get(limbname)
    if not limb.exists():
	if not limbname:
	    limbname = '""'
	sys.stderr.write("%s: not found\n" % limbname)
	sys.exit(1)

    limb_branches = git.branchnames(limbname, recursive=recursive)
    try:
	current_name = git.current_branch().name
	if current_name and current_name in limb_branches:
		sys.stderr.write("Cannot delete current branch: %s.\n" %
			current_name)
		sys.exit(1)
    except GitError:
	pass

    cmd = ['git', 'branch', '-D'] + limb_branches
    git.call(cmd, stdout=sys.stdout, verbose=True)


def git_list_dependencies():
    limbname = config["limb1"]
    if not limbname:
	limbname = git.current_limb().name

    branch_dep_ref = "%s/limb-info:MONTAVISTA/branch_dependencies" % limbname

    try:
	git.call(['git', 'show', branch_dep_ref], stdout=sys.stdout)
    except:
	sys.stderr.write("%s not found\n", branch_dep_ref)
	sys.exit(1)


def main():
    process_options()

    try:
	git.check_repository()

	if config["deps"]:
	    git_list_dependencies()

	elif not config["limb1"] and not config["limb2"]:
	    git_list_branches()

	elif config["move"]:
	    git_move_limb()

	elif config["delete"]:
	    git_delete_limb()

	else:
	    git_create_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
