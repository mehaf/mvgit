#!/usr/bin/env python
"""Usage: git-mvl6-releasify [opts] <committish> <output_dir>
   opts:
   	-r <repo>
	-s <since>
	--retries=N
	-f

Places a series of patches in <output_dir> corresponding to the commits
in <committish>, contained in the mvl6 git repository <repo>, a directory
on the local machine.  If "-r <repo>" is not specified, the current directory
is used.  The patch series begins with the first commit following <since>.
If "-s <since>" is not specified, the value contained in the file
MONTAVISTA/upstream_version of the limb-info branch in the same limb
as <committish> is used for <since>.

The calling of external programs has not been reliable in our initial
build environment for mvl6.  --retries may be used to specify that
such failed calls be repeated N times.

If <output_dir> exists and is not empty, git-mvl6-releasify fails
unless -f is specified.
"""

import getopt
import sys
import os
import re
import tarfile
import time
import shutil


config = {
    "debug"		: False,		# Not currently used
    "dry-run"		: False,		# produce no output
    "retries"		: 0,			# subprocess retries
    "force"		: False,		# overwrite <output_dir>
}


def usage(msg=None):
    """
    Print a usage message and exit with an error code
    """

    if msg:
	sys.stderr.write("%s\n" % str(msg).rstrip())

    sys.stderr.write("\n%s\n" % __doc__.strip())
    sys.exit(1)


def call(cmd, **kwargs):
    """
    Call the given Linux command.  Returns the command's stdout.
    Valid kwargs parameters are: error=None

    We previously used the subprocess.Popen() , but that may not be reliable
    on the older version of python we're using in the build environment.
    We now use os.popen() instead.
    """

    retries = config['retries']

    sys.stdout.flush()

    error = True
    if 'error' in kwargs:
	error = kwargs['error']

    retrying = True
    while retrying:
	retrying = False

	errno = None
	strerror = None
	try:
	    f = os.popen(cmd)
	    output = f.read()
	    rc = f.close()
	except IOError, (errno, strerr):
	    rc = -1
	except:
	    rc = -1

	if rc and error:
	    sys.stderr.write('"%s" returned %d\n' % (cmd, rc))
	    if errno:
		sys.stderr.write('errno: %d %s\n' % (errno, strerror))

	    if retries > 0:
		retrying = True
		retries -= 1
		sys.stderr.write('Retrying\n\n')
		time.sleep(1)
		continue

	    raise Exception('%s returned %d\n' % (cmd, rc))

    return output


def verify_git():
    """
    Just verify that we can find the git command
    """

    try:
	call("git --version")
    except:
	sys.stderr.write('Failed: "git --version"')
	sys.exit(1)


def process_options():
    """
    Process command line options
    """

    def rmtree_error(func, path, exc_info):
	sys.stderr.write("Cannot remove %s\n" % path)

    short_opts = "fhnr:s:"
    long_opts = ["debug", "retries=", "dry-run", "version"]

    try:
        options, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)

    except getopt.GetoptError, err:
        usage(err)

    repo = None
    since_commit = None

    for option, value in options:
        if option == "--help" or option == "-h":
	    usage()
	elif option == "--debug":
	    config["debug"] = True
	elif option == '--version':
	    sys.stdout.write('mvgit version %s\n' % "@@MVGIT_VERSION@@")
	    sys.exit(0)
	elif option == "-n" or option == "--dry-run":
	    config["dry-run"] = True
	elif option == "--retries":
	    config["retries"] = int(value)
        elif option == "-r":
	    repo = value
        elif option == "-f":
	    config["force"] = True
        elif option == "-s":
	    since_commit = value

    if len(args) != 2:
	usage()

    verify_git()

    committish, output_dir = args

    if repo:
	if not os.path.isdir(repo):
	    sys.stderr.write("Not a directory: %s\n" % repo)
	    sys.exit(1)

	try:
	    os.chdir(repo)
	except:
	    sys.stderr.write("failed: chdir %s\n" % repo)
	    sys.exit(1)

    forced = False
    if os.path.isdir(output_dir) and os.listdir(output_dir):
	if config["force"]:
	    forced = True
	    rmtree_errors = 0
	    shutil.rmtree(output_dir, False, rmtree_error)
	    if rmtree_errors:
		sys.stderr.write("Exiting.\n")
		sys.exit(1)
	else:
	    sys.stderr.write("%s: Directory not empty. Aborting.\n"
			     % output_dir)
	    sys.exit(1)
    
    if not os.path.isdir(output_dir):
	try:
	    os.mkdir(output_dir)
	except:
	    sys.stderr.write("Failed: mkdir %s\n" % output_dir)
	    sys.exit(1)
	if forced:
	    sys.stdout.write("Replacing %s\n" % output_dir)
	else:
	    sys.stdout.write("Creating %s\n" % output_dir)

    try:
	cmd = "git rev-parse --verify %s" % committish
	call(cmd)
    except:
	sys.stderr.write("git ref not found: %s\n" % committish)
	sys.exit(1)

    if not since_commit:		# first look on the current branch
	upstream_version_ref = "%s:%s" % (
		committish, "MONTAVISTA/upstream_version")
	try:
	    cmd = "git show %s" % upstream_version_ref
	    since_commit = "v%s" % call(cmd).strip()
	except:
	    pass

    if not since_commit:		# then look on limb-info branch
	limb_info = os.path.join(os.path.dirname(committish), "limb-info")
	cmd = "git rev-parse --symbolic-full-name %s" % limb_info
	info_fullname = call(cmd, error=None, stderr=None).strip()
	if not info_fullname:
	    sys.stderr.write("Invalid limb-info branch: %s\n" % limb_info)
	    usage()

	upstream_version_ref = "%s:%s" % (
		limb_info, "MONTAVISTA/upstream_version")
	try:
	    cmd = "git show %s" % upstream_version_ref
	    since_commit = "v%s" % call(cmd).strip()
	except:
	    sys.stderr.write("failed: git show %s\n" % upstream_version_ref)
	    usage()

    try:
	cmd = "git rev-parse --verify %s" % since_commit
	call(cmd)
    except:
	sys.stderr.write("git ref not found: %s\n" % since_commit)
	sys.exit(1)

    config["since_commit"] = since_commit
    config["committish"] = committish
    config["output_dir"] = output_dir


def metadata(filenames):
    for filename in filenames:
	if filename.startswith("MONTAVISTA"):
	    return True
    return False


def non_metadata(filenames):
    for filename in filenames:
	if not filename.startswith("MONTAVISTA"):
	    return True
    return False


class Commit:
    def __init__(self, id, parents, filenames):
	self.id = id
	self.parents = parents
	self.filenames = filenames


def create_patches():
    """
    Create a patch in config["output_dir"]/recipes/linux/patches for
    each commit that modifies non-metadata-files on config["committish"]
    since config["since_commit"].
    """

    def read_commit(file):
	id = None
	parents = None
	filenames = []
	section = 'header'
	for line in file:
	    line = line.rstrip()
	    if line == '/':
		break

	    if section == 'header':
		commit_info = line.split()
		id = commit_info[0]
		parents = commit_info[1:]
		section = 'filenames'
		continue

	    if section == 'filenames':
		if not line:
		    continue
		filenames.append(line)
		continue

	if not id:
	    return None

	return Commit(id, parents, filenames)


    since_commit = config["since_commit"]
    committish = config["committish"]
    output_dir = config["output_dir"]

    cmd = "git rev-list -1 %s ^%s" % (since_commit, committish)
    not_ancestor = call(cmd, error=None, stderr=None)
    if not_ancestor:
	sys.stderr.write("%s is not an ancestor of %s - exiting.\n" %
			(since_commit, committish))
	sys.exit(1)

    cmd = ("git log --name-only --reverse --pretty=format:'/%n%H %P' " +
	   "%s..%s" % (since_commit, committish))

    commits = []

    file = os.popen(cmd)
    if file.readline():
	while True:
	    commit = read_commit(file)
	    if not commit:
		break
	    commits.append(commit)
    file.close()

    consecutive_groups = []
    consecutive_commits = []
    for commit in commits:
	if len(commit.parents) > 1:			# it's a merge commit
	    sys.stderr.write("Found merge commit %s\n" % commit.id)
	    sys.stderr.write("Error: cannot releasify non-linear history\n")
	    sys.exit(1)

	if non_metadata(commit.filenames):
	    if metadata(commit.filenames):
		sys.stderr.write("Error: commit has both metadata and "
				 "non-metadata files: %s\n" % commit.id)
		sys.exit(1)
	    consecutive_commits.append(commit)
	else:
	    if consecutive_commits:
		consecutive_groups.append(consecutive_commits)
		consecutive_commits = []

    if consecutive_commits:
	consecutive_groups.append(consecutive_commits)

    if config["dry-run"]:
	return

    patch_dir = os.path.join(output_dir, "recipes/linux/patches")
    re_patch_dir = re.compile("%s/" % patch_dir)

    if not os.path.isdir(patch_dir):
	try:
	    os.makedirs(patch_dir)
	except:
	    sys.stderr.write("failed: mkdir %s\n" % patch_dir)
	    sys.exit(1)

    series_filename = os.path.join(patch_dir, "series")

    try:
	series_file = open(series_filename, "w")
    except:
	sys.stderr.write("open for writing failed: %s\n" % series_filename)
	sys.exit(1)

    index = 1
    for commits in consecutive_groups:
	cmd = "git format-patch -o %s -%s --start-number %d -N %s" % (
		patch_dir, len(commits), index, commits[-1].id)
	patchnames = call(cmd).splitlines()
	patchnames = [re_patch_dir.sub('', x) for x in patchnames]
	for patchname in patchnames:
	    series_file.write("%s\n" % patchname)
	index += len(commits)

    series_file.close()


def copy_metadata():
    """
    Copy the directory hierarchy from the MONTAVISTA/bitbake
    directory in config["committish"] to config["output_dir"].
    """

    committish = config["committish"]
    output_dir = config["output_dir"]

    bitbake_dir = "MONTAVISTA/bitbake"
    bitbake_dir_ref = "%s:%s" % (committish, bitbake_dir)

    try:
	call("git rev-parse %s" % bitbake_dir_ref)
    except:
	sys.stderr.write("Directory %s not found in %s\n" %
			    (bitbake_dir, committish))
	sys.exit(1)

    if config["dry-run"]:
	return

    retries = config["retries"]
    cmd = 'git archive %s' % bitbake_dir_ref
    retrying = True
    while retrying:
	retrying = False

	f = os.popen(cmd)

	tar = tarfile.open(fileobj=f, mode='r|')
	file = tar.next() # too bad we can't use extractall(), from python 2.5
	while file:
	    tar.extract(file, path=output_dir)
	    file = tar.next()
	tar.close()

	git_exit_code = f.close()

	if git_exit_code:
	    if retries > 0:
		retrying = True
		retries -= 1
		sys.stderr.write('Retrying "%s"\n' % cmd)
		time.sleep(1)
		continue

	    raise Exception('%s returned %d\n' % (cmd, git_exit_code))


def main():
    """
    Main Program
    """

    process_options()

    create_patches()
    copy_metadata()

    sys.exit(0)


main()
