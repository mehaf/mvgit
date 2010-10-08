#!/usr/bin/env python
"""
Usage: git-cherry-pick-mv [opts] <commit>...
	[opts]
	-m
		Permit cherry-picking merge commits.  The result will
		be a non-merge commit containing all the changes of the
		merge commit.
	-e, --edit
		With this option, git cherry-pick-mv will let you edit
		the commit message prior to committing.
	--no-signoff
		By default, a signoff-line is added to the commit message.
		This option causes a signoff-line not to be added.
	-n | --no-commit
		Perform the cherry-pick(s), but don't commit them.
	--stdin
		Take commit list from stdin instead of the command line.
	--source <source>
		Provides the value of the Source: field of the MV-header.
	--bugz <bugz_number>
		Provides the value of the MR: field of the MV-header.
	--type <type>
		Provides the value of the Type: field of the MV-header.
	--disposition <disposition>
		Provides the value of the Disposition: field of the MV-header.

	These options are passed directly to "git cherry-pick":
		-x --ff
	
	git-cherry-pick-mv should work similarly to git-cherry-pick,
	except that an MV-header is introduced into the commit message.
	The MV-header contents can be provided by the --source, --bugz,
	--type, and --disposition arguments, or by editing an MV-header
	template.
"""
    	

import sys
import os
import shutil
import getopt
import subprocess
import pickle
import mvgitlib as git


config = {
    "debug"		: False,
    "edit"		: False,
    "nosignoff"		: False,
    "merges_ok"		: False,
    "continue"		: False,
    "skip"		: False,
    "abort"		: False,
    "nocommit"		: False,
    "cherry_options"	: [],
    "source"		: None,
    "bugz"		: None,
    "type"		: None,
    "disposition"	: None,
    "gitdir"		: "",
    "commits_done"	: 0,
    "skipped_commits"	: []
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
    short_opts = "emnx"
    long_opts = [
	"help", "debug", "version", "edit",
	"ff", "continue", "skip", "abort", "stdin",
	"source=", "bugz=", "mr=", "type=", "disposition=",
	"no-commit",
    ]

    noargs = False

    args = sys.argv[1:]
    if args and args[-1] == '--':
	args = args[0:-1]
	noargs = True

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
	elif option == '--stdin':
	    noargs = True
	elif option == '--continue':
	    config["continue"] = True
	    noargs = True
	elif option == '--skip':
	    config["skip"] = True
	    noargs = True
	elif option == '--abort':
	    config["abort"] = True
	    noargs = True
	elif option == '--no-signoff':
	    config['nosignoff'] = True
	elif option in ('-e', "--edit"):
	    config["edit"] = True
	elif option == '--source':
	    config['source'] = value
	elif option in ('--bugz', '--mr'):
	    config['bugz'] = value
	elif option == '--type':
	    config['type'] = value
	elif option == '--disposition':
	    config['disposition'] = value
	elif option == '-m':
	    config["merges_ok"] = True
	elif option in ('-n', '--no-commit'):
	    config['nocommit'] = True
	elif value:
	    if option.startswith("--"):
		config["cherry_options"] += [option, value]
	    else:
		config["cherry_options"].append(option)
		config["cherry_options"].append(value)
	else:
	    config["cherry_options"].append(option)

    if len(args) == 0:
	if not noargs:
	    usage()
    else:
	if noargs:
	    usage()

    config["commits"] = args

    if not config["nosignoff"]:
	config["cherry_options"].append("-s")


def save_state():
    statefilename = config["gitdir"] + "/.dotest/cherry-pick-mv.state"
    f = open(statefilename, "w")
    pickle.dump(config, f)


def restore_state():
    dotest = config["gitdir"] + "/.dotest"
    if not os.path.isdir(dotest):
	sys.stdout.write("No dotest directory found.\n"
	    "No git-cherry-pick-mv in progress?\n")
	sys.exit(1)

    statefilename = dotest + "/cherry-pick-mv.state"
    if not os.path.isfile(statefilename):
	sys.stdout.write("%s not found.\n" % dotest)
	sys.stdout.write("No git-cherry-pick-mv in progress?\n")
	sys.exit(1)

    f = open(statefilename)
    lconfig = pickle.load(f)
    for v in lconfig:
	if v not in ("continue", "skip"):
	    config[v] = lconfig[v]


def checkout_original_branch():
    if config["orig_branchname"] != 'detached HEAD':
	if not config["nocommit"]:
	    cmd = ["git", "reset", "--hard"]
	    git.call(cmd)
	prefix_len = len('refs/heads/')
	cmd = ["git", "checkout", config["orig_branchname"][prefix_len:]]
	p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
	errmsg = p.stderr.read()
	rc = p.wait()
	if 'Switched to branch ' not in errmsg:
	    sys.stderr.write(errmsg)
	if rc != 0:
	    sys.stdout.write('"git checkout %s" failed\n' % config["orig_branchname"])
	    sys.exit(1)


def do_abort():
    restore_state()

    merge_msg_filename = config["gitdir"] + "/MERGE_MSG"
    if os.path.isfile(merge_msg_filename):
	os.remove(merge_msg_filename)

    cleanup_state()
    checkout_original_branch()
    cmd = ['git', '--no-pager', 'log', '-1', '--oneline', 'HEAD']
    git.call(cmd, stdout=sys.stdout)

    sys.exit(0)


def do_continue_or_skip():
    restore_state()
    merge_msg_filename = config["gitdir"] + "/MERGE_MSG"
    if os.path.isfile(merge_msg_filename):
	os.remove(merge_msg_filename)

    commits = config["commits"]
    commits_done = config["commits_done"]

    commit = commits[commits_done]
    cmd = ['git', 'log', '--oneline', '-1', commit]
    oneline = git.call(cmd).strip()
    if config["continue"]:
	sys.stdout.write("Continuing %s\n" % oneline)
	unmerged = unmerged_files()
	if unmerged:
	    sys.stderr.write(unmerged)
	    sys.stderr.write("Unmerged files.  ")
	    output_resolve_msg_and_exit()
	do_commit(commit)
    else:
	cmd = ['git', 'reset', '--hard', 'HEAD']
	git.call(cmd, stdout=None)
	sys.stdout.write("Skipping %s\n" % oneline)
	config["skipped_commits"].append(commit)
    commits_done += 1
    config["commits_done"] = commits_done
    save_state()


def select_merge_commits(commits):
    merge_commits = {}

    cmd = ["git", "rev-list", "--no-walk", "--parents"] + commits
    parentlines = git.call(cmd, stderr=None).splitlines()
    for parentline in parentlines:
	ids = parentline.split()
	if len(ids) > 2:
	    merge_commits[ids] = True

    return merge_commits


def create_state_directory():
    dotest = config["gitdir"] + "/.dotest"
    if os.path.isdir(dotest):
	sys.stdout.write("Previous dotest directory %s still exists.\n" %
		dotest)
	sys.stdout.write("Try git cherry-pick-mv [ --continue | --abort ]\n")
	sys.stdout.write('If all else fails, you can try "rm -rf %s"\n' %
				dotest)
	sys.stdout.write("and try again.\n")
	sys.exit(1)
    else:
	os.makedirs(dotest)


def unmerged_files():
    cmd = ['git', 'update-index', '--refresh']
    return git.call(cmd, error=None)


def changed_files():
    cmd = ['git', 'diff-index', '--cached', '--name-status', '-r', 'HEAD', '--']
    return git.call(cmd, error=None)


def cleanup_state():
    dotest = config["gitdir"] + "/.dotest"
    try:
	shutil.rmtree(dotest)
    except:
	sys.stdout.write("rmdir of %s failed\n" % dotest)
	sys.exit(1)
    

def move_commits_to_original_branch():
    branch = config["orig_branchname"]
    if branch != 'detached HEAD':
	cmd = ['git', 'rev-parse', 'HEAD']
	head = git.call(cmd).strip()
	message = "Cherry-pick finished"
	orig_head = config["orig_head"]
	cmd = ['git', 'update-ref', '-m', message, branch, head, orig_head]
	git.call(cmd)


def check_mv_headers(ids):
    no_mv_header_ids = []

    for id in ids:
	commit = git.read_commit(id)
	h = commit.mv_header_dict
	if 'source' in h and 'mr' in h and 'type' in h and 'disposition' in h:
	    continue
	no_mv_header_ids.append(id)

    if no_mv_header_ids:
	sys.stderr.write("The following commits have no MV header:\n")
	for id in no_mv_header_ids:
	    cmd = ['git', '--no-pager', 'log', '-1', '--pretty=oneline', id]
	    git.call(cmd, stdout=sys.stdout)
	sys.stderr.write("To cherry-pick commits without an MV header, "
	    "it is necessary to specify either\n"
	    "--edit or all of these options: --source, --bugz, "
	    "--type, --disposition\n")
	sys.exit(1)


def move_to_detached_head():
    cmd = ['git', 'rev-parse', 'HEAD^0']
    orig_head = git.call(cmd).strip()
    config['orig_head'] = orig_head

    cmd = ['git', 'symbolic-ref', 'HEAD']
    orig_branchname = git.call(cmd, stderr=None, error=None).strip()
    if not orig_branchname:
	orig_branchname = 'detached HEAD'
    else:
	cmd = ['git', 'checkout', orig_head]
	try:
	    git.call(cmd, stdout=None, stderr=None)
	except:
	    sys.stderr.write("could not detach HEAD\n")
	    sys.exit(1)
    config['orig_branchname'] = orig_branchname


def set_gitdir():
    cmd = ['git', 'rev-parse', '--git-dir']
    config['gitdir'] = git.call(cmd).strip()


def initialize_commits():
    commits = config["commits"]
    edit = config["edit"]
    source = config["source"]
    bugz = config["bugz"]
    type = config["type"]
    disposition = config["disposition"]

    if not edit and bugz == None:
	sys.stdout.write("Either of --edit or --bugz options is required")
	sys.exit(1)

    if not commits:
	commits = [x.strip() for x in sys.stdin.readlines()]

    # newer versions of git-list handle "--no-walk" and a range.
    # sadly, we can't rely on having a recent version.  Do it the hard way
    for commit in commits:
	if (commit.startswith('^') or
		'..' in commit or
		'^@' in commit or
		'^@' in commit):
	    range = True
	    break
    else:
	range = False

    cmd = ["git", "rev-list", "--no-walk"]
    if range:
	cmd = ["git", "rev-list", "--reverse", "--topo-order"] + commits
	try:
	    commits = git.call(cmd).splitlines()
	except:
	    sys.exit(1)
    else:
	orig_commits = commits
	commits = []
	for commit in orig_commits:
	    cmd = ["git", "rev-list", "--no-walk"] + [commit]
	    try:
		commit = git.call(cmd).rstrip()
	    except:
		sys.exit(1)
	    commits.append(commit)

    config["commits"] = commits

    merge_commits = select_merge_commits(commits)
    if merge_commits and not merges_ok:
	sys.stdout.write("The specified revisions contain merges.  "
	    "Please linearize the history\n"
	    "or specify -m to enable cherry-picking merge commits.\n")
	sys.exit(1)
    config["merge_commits"] = merge_commits

    msg = unmerged_files() or changed_files()
    if msg:
	sys.stdout.write("cannot cherry-pick: your index is not up-to-date\n")
	sys.stderr.write(msg)
	sys.exit(1)

    if not edit and not (source and bugz and type and disposition):
	check_mv_headers(commits)

    create_state_directory()
    move_to_detached_head()

    config["commits_done"] = 0
    save_state()


def output_resolve_msg_and_exit():
    sys.stderr.write("After resolving the conflicts, mark the\n"
	"corrected paths with 'git add <paths>' or 'git rm <paths>'.\n"
	"(Do NOT commit before running 'git cherry-pick-mv --continue'.)\n"
	"When you are ready to continue, run "
	"'git cherry-pick-mv --continue'.\n"
	"Or, if you would prefer to skip this patch, "
	"run 'git cherry-pick-mv --skip'.\n"
	"Or, to restore the original branch, "
	"run 'git cherry-pick-mv --abort'.\n")
    sys.exit(1)


def do_cherry_pick(commit):
    cherry_options = config["cherry_options"]
    merge_commits = config["merge_commits"]

    if commit in merge_commits:
	cherry_options = cherry_options + ["-m", "1"]

    sys.stdout.write("Pick ")
    cmd = ['git', '--no-pager', 'log', '-1', '--oneline', commit]
    git.call(cmd, stdout=sys.stdout)
    cmd = ["git", "cherry-pick", "-n"] + cherry_options + [commit]
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=subprocess.PIPE)
    errmsg = p.stderr.read()
    rc = p.wait()
    if errmsg == 'Finished one cherry-pick.\n':
	return
    elif errmsg:
	unmerged = unmerged_files()
	if unmerged:
	    sys.stderr.write(unmerged)
	    sys.stderr.write("Automatic cherry-pick failed.  ")
	    output_resolve_msg_and_exit()
	sys.stdout.write(errmsg)

    if rc != 0:
	sys.exit(rc)


def changes_added_to_index():
    cmd = ["git", "diff", "--quiet", "--cached"]
    rc = subprocess.call(cmd)
    return rc != 0


def abbrev(commit):
    cmd = ['git', '--no-pager', 'rev-list', '-1', '--abbrev-commit', commit]
    return git.call(cmd).rstrip()


def do_commit(commit):
    commit_options = []
    if config['source']:
	commit_options += ['--source', config['source']]
    if config['bugz']:
	commit_options += ['--bugz', config['bugz']]
    if config['type']:
	commit_options += ['--type', config['type']]
    if config['disposition']:
	commit_options += ['--disposition', config['disposition']]
    if git.mvl6_kernel_repo():
	commit_options += ['--changeid', git.read_commit(commit).changeid]

    cmd = ["git", "commit-mv"] + commit_options
    edit = config["edit"]

    if edit:
	if not changes_added_to_index():
	    sys.stdout.write("Skipping %s - No additional changes to pick.\n\n"
			     % abbrev(commit))
	    config["skipped_commits"].append(commit)
	    return

	if config['nocommit']:
	    sys.stdout.write('Not committing changes in %s\n' % abbrev(commit))
	    return

	cmd += ['-c', commit]
	p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
	output = ""
    else:
	if config['nocommit']:
	    sys.stdout.write('Not committing changes in %s\n' % abbrev(commit))
	    return

	cmd += ['--no-edit', '-C', commit]
	p = subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
	output = p.stdout.read()

    errmsg = p.stderr.read()
    rc = p.wait()
    if 'nothing added to commit' in output or 'nothing to commit' in output:
	skipped = True
	sys.stdout.write("Skipping %s - No additional changes to pick.\n\n"
			    % abbrev(commit))
	config["skipped_commits"].append(commit)
    else:
	skipped = False
	lines = output.splitlines()
	for line in lines:
	    if (not line.startswith('[detached HEAD ') and
		    not line.startswith(' Author: ') and
		    not 'files changed' in line):
		sys.stdout.write(line)

    if errmsg:
	sys.stderr.write(errmsg + "\n")

    if rc != 0 and not skipped:
	sys.stderr.write("***** git-commit returned %d\n" % rc)


def cherry_pick_mv():
    set_gitdir()

    if config["abort"]:
	do_abort()

    if config["continue"] or config["skip"]:
	do_continue_or_skip()
    else:
	initialize_commits()

    commits = config["commits"]
    commits_done = config["commits_done"]

    for commit in commits[commits_done:]:
	do_cherry_pick(commit)

	do_commit(commit)

	commits_done += 1
	config["commits_done"] = commits_done

	save_state()

    if len(commits) > 1:
	if config["skipped_commits"]:
	    count = len(config["skipped_commits"])
	    if count == 1:
		str = "commit was"
	    else:
		str = "%d commits were" % count
	    sys.stderr.write("The following %s skipped:\n" % str)
	    for commit in config["skipped_commits"]:
		cmd = ['git', '--no-pager', 'log', '-1', '--oneline', commit]
		oneline = git.call(cmd).rstrip()
		sys.stderr.write("    %s\n" % oneline)

    move_commits_to_original_branch()
    checkout_original_branch()
    cleanup_state()


def main():
    process_options()

    try:
	git.check_repository()
	cherry_pick_mv()

    except git.GitError, e:
	sys.stderr.write("\nError: %s\n" % e.msg)
	sys.stderr.write("Exiting.\n")

	if config["debug"]:
	    sys.stdout.write("\n")
	    raise

	sys.exit(1)


main()
