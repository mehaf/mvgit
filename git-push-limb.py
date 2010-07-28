#!/usr/bin/env python
"""
Usage: git-push-limb [opts] [<remote_repository> [<local_limb>][:<remote_limb>]]
        opts        These options are passed to git-push:
                --dry-run, --tags, -f, --force, --thin, --no-thin

Push each branch in <local-limb> into <remote_limb> on
<remote_repository>.  If <remote_repository> is omitted, origin is used.
For each branch, branch_name, in <local_limb>, git-push-limb runs
"git push <remote_repository> [<local_limb>/]branch_name:[<remote_limb>/]branch_name".
If neither <local_limb> and <remote_limb> are supplied, push the current
limb.  If only :<remote_limb> is supplied, then first run "git fetch
<remote_repository>" to update remote references, and then delete
<remote_limb> from <remote_repository>.
"""

import sys
import getopt
import re
import gitlib as git


config = {
    "debug"		: False,
    'options'           : [],
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
    short_opts = "fh"
    long_opts = [
	"help", "debug", "dry-run", "tags", "force", "thin", "no-thin"
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

    if len(args) > 2:
        usage()


    if len(args) > 0:
	repo = args[0]
    else:
	repo = git.remote_alias()

    if len(args) < 2:
	local, remote = "", ""
    elif ":" in args[1]:
        match = re.match("(.*):(.*)", args[1])
        local, remote = match.groups()
    else:
        local, remote = args[1], ""

    config["repo"] = repo
    config["local"] = local
    config["remote"] = remote


def push_limb():
    re_parent = re.compile(r'(.*)/bugfixes/\d+[^/]*')

    options = config["options"]
    repo = config["repo"]
    localname = config["local"].rstrip("/")
    remotename = config["remote"].rstrip("/")

    if not remotename:
        if not localname:
            localname = git.current_limb().name
        remotename = localname

    git.call(['git', 'fetch', repo], stdout=sys.stdout, verbose=True)
    git.call(['git', 'remote', 'prune', repo], stdout=sys.stdout, verbose=True)

    if not localname:
        remote_branchnames = git.branchnames("%s/%s" % (repo, remotename))
	if not remote_branchnames:
	    sys.stdout.write("remote limb %s not found\n" % remotename)
	    sys.exit(1)

        del_prefix_len = len(repo) + 1
        cmd = ['git', 'push'] + options + [repo]
        cmd += [":%s" % x[del_prefix_len:] for x in remote_branchnames]
        git.call(cmd, stdout=sys.stdout, verbose=True)
        return

    local = git.Limb.get(localname)
    if not local.exists():
	sys.stdout.write("local limb %s not found\n" % localname)
	sys.exit(1)

    # call "git analyze-changes" before pushing
    cmd = ['git', 'analyze-changes', '-r', repo]
    if local != git.current_limb():
	cmd.append(localname)
    try:
	git.call(cmd, stdout=sys.stdout, verbose=True)
    except:
	sys.stderr.write("git analyze-changes failed.  No branches pushed.\n")
	sys.exit(1)

    local_subnames = git.subnames(localname)

    nff_names = []
    rebased_names = []
    branchnames = []
    for subname in local_subnames:
        branchname = "%s/%s" % (localname, subname)
	repo_branchname = "%s/%s/%s" % (repo, remotename, subname)

	repo_branch= git.Branch.get(repo_branchname)
	branch = git.Branch.get(branchname)

	if repo_branch.id and repo_branch.id == branch.id:
	    continue

	rebased = False
	match = re_parent.match(remotename)
	if match:
	    parentname = match.group(1)
	    parent_branchname = "%s/%s/%s" % (repo, parentname, subname)
	    parent_branch = git.Branch.get(parent_branchname)
	    rebased = parent_branch.id and not branch.contains(parent_branch)

	if rebased:
	    rebased_names.append(branchname)
	elif repo_branch.id and not branch.contains(repo_branch):
	    nff_names.append(branchname)

        if localname != remotename:
            branchname = "%s:%s" % (branchname, "%s/%s" % (remotename, subname))

        branchnames.append(branchname)

    force = "-f" in options or "--force" in options
    if rebased_names and not force:
	parentname = "%s/%s" % (repo, parentname)
	sys.stdout.write("\nNon-fast-forward when compared to %s:\n" %
		parentname)
	for branchname in rebased_names:
	    sys.stdout.write("    %s\n" % branchname)
	sys.stdout.write('\nPlease do "git rebase-limb %s".\n' % parentname)
	sys.stdout.write("Or if this is what you want, "
		"re-push the limb using --force.\n")
	sys.stdout.write("\nNo branches pushed.\n")
	return

    if nff_names and not force:
	sys.stdout.write("\nNon-fast-forward:\n")
	for branchname in nff_names:
	    sys.stdout.write("    %s\n" % branchname)
	sys.stdout.write("\nIf this is what you want, "
		"re-push the limb using --force.\n")
	sys.stdout.write("\nNo branches pushed.\n")
	return

    if not branchnames:
	sys.stdout.write("No updated or new branches to push.\n")
	return

    cmd = ['git', 'push'] + options + [repo] + branchnames
    git.call(cmd, stdout=sys.stdout, verbose=True)


def main():
    process_options()

    try:
	git.check_repository()
	push_limb()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
