#!/usr/bin/python
# requires python versions 2.4 or 2.5.  May work on 2.6

'''
This is a library of functions for accessing git from python.
It includes functions to work with git limbs as defined for MVL6.
'''

# Author: Dale Farnsworth <dfarnsworth@mvista.com>
# Copyright (C) 2009-2011 MontaVista Software, Inc.
#
# This file is licensed under the terms of the GNU General Public License
# version 2. This program is licensed "as is" without any warranty of any
# kind, whether express or implied.

import sys
import os
import subprocess
import re
import pwd
import grp
import time
import tempfile

def commit_contains(container, contained):
    """Return True if the commit container contains the commit contained"""
    cmd = ['git', 'rev-list', '-1', contained, '^%s' % container]
    return not bool(call(cmd, stderr=None))

class GitError(Exception):
    def __init__(self, msg):
        self.msg = msg


class cached_property(property):
    '''
    Convert a method into a cached attribute
    '''
    def __init__(self, method):
	private = '_' + method.__name__
	def fget(s):
	    try:
		return getattr(s, private)
	    except AttributeError:
		value = method(s)
		setattr(s, private, value)
	    return value

	super(cached_property, self).__init__(fget)


class User(object):
    '''
    Contains information about the user running the current program

    Each instance contains the following attributes containing information
    about the user who is running the current program

	.name	Login name of the current user
	.groups	Groups that the current user is a member of
    '''

    def __init__(self):
	pwent = pwd.getpwuid(os.getuid())
	self.name = pwent.pw_name
	self.real_name = pwent.pw_gecos.split(',', 2)[0]
	gids = os.getgroups()
	gid = os.getgid()
	if gid not in gids:
	    gids.append(gid)
	self.groups = []
	for gid in gids:
	    try:
		self.groups.append(grp.getgrgid(gid).gr_name)
	    except:
		notice("Can't find name for gid %d.  (This can usually be safely ignored.)\n" % gid)

def is_empty_commit(id):
    """Returns true if the given commit is empty."""

    cmd = ['git', 'diff-tree', id.id]
    return not bool(call(cmd, stderr=None))


class Limb(object):
    '''
    Represents a git limb (a related set of branches in a common namespace)
    '''

    limb_info_branchname = 'limb-info'
    limb_common_branchname = 'common'
    upstream_version_filename = 'MONTAVISTA/upstream_version'
    branch_dep_filename = 'MONTAVISTA/branch_dependencies'

    re_limbname = re.compile(r'''
	((?P<parent_limbname>		[^/]+)
	    (				.*/bugfixes/
		(?P<bugz>		[0-9]+)[^/]*)?)
	''', re.X)
    re_dependent = re.compile(r'^(\S+):(.*)$')
    re_provider = re.compile(r'^\s+(\S+)(.*)$')
    re_blank = re.compile(r'^\s*$')

    limb_dict = {}	# limb_dict is used to lookup limbs by name


    def __init__(self, name, newname=None):
	if newname:
	    self.newlimb = Limb.get(newname)
	else:
	    self.newlimb = None

	if not newname and name in self.limb_dict:
	    cls_name = self.__class__.__name__
	    raise GitError(
		    "%s '%s' exists, use %s.get()" % (cls_name, name, cls_name))
	self.limb_dict[name] = self
	self.name = name
	self.branches = []

	match = self.re_limbname.match(name)
	self.bugz = match.group('bugz')
	parent_limbname = match.group('parent_limbname')
	self.parent = None
	if parent_limbname:
	    parent = Limb.get(parent_limbname)
	    if parent != self:
		self.parent = parent


    @classmethod
    def get(cls, name, newname=None):
	'''
	Find an existing limb with the name, or create a new Limb
	'''
	if name in cls.limb_dict:
	    limb = cls.limb_dict[name]
	    if newname:
		raise GitError("Pre-existing %s:%s, but newname specified" %
		    (cls, name))
	    return limb
	else:
	    return Limb(name, newname)


    @cached_property
    def remote_limb(self):
	remote = remote_alias()
	if not remote or self.name.startswith(remote + "/"):
	    return None
	return Limb.get('%s/%s' % (remote, self.name))


    @cached_property
    def repository_branches(self, recursive=False):
	names = branchnames(self.name, recursive=recursive)
	return [Branch.get(x) for x in names]


    def lookup_upstream_version(self):
	'''
	Return the major kernel version on which branches in the limb are based
	'''

	re_is_numeric = re.compile(r'\d+\.\d+(\.\d+)?$')

	for x in (0, 1, 2, 3, 4, 5, 6, 7):
	    branches = []
	    if x == 0:
		if (self.common_branch and
		    hasattr(self.common_branch, 'newbranch')):
			branches.append(self.common_branch.newbranch)
	    elif x == 1:
		for branch in self.branches:
		    if hasattr(branch, 'newbranch'):
			branches.append(branch.newbranch)
	    elif x == 2:
		if self.common_branch:
		    branches.append(self.common_branch)
	    elif x == 3:
		branches += self.branches
	    elif x == 4:
		if (self.common_branch and self.common_branch.parent and
		    self.common_branch.parent.remote_branch):
			branches.append(self.common_branch.parent.remote_branch)
	    elif x == 5:
		if self.parent and self.parent.remote_limb:
		    branches += self.parent.remote_limb.repository_branches
	    elif x == 6:
		if self.remote_limb:
		    branches += self.remote_limb.repository_branches
	    elif x == 7:
		branches += self.repository_branches
	    else:
		break

	    for b in branches:
		ref = '%s:%s' % (b.id, self.upstream_version_filename)
		cmd = ['git', 'show', ref]
		version = call(cmd, error=None, stderr=None)
		if version:
		    version = version.strip()
		    version = re.sub('\n.*', '', version)
		    version = 'v%s' % version
		    cmd = ['git', 'rev-parse', version]
		    if bool(call(cmd, stderr=None)):
			return version

		    sys.stderr.write('Warning: Unknown version "%s" in %s\n' %
				     (version, ref))

	return None


    @cached_property
    def upstream_version(self):
	'''
	Return the major kernel version on which branches in the limb are based
	'''
	return self.lookup_upstream_version()


    @cached_property
    def merge_base(self):
	'''
	Return the merge base of all branches in the limb
	'''
	if self.upstream_version:
	    return self.upstream_version

	ids = []
	for branch in self.branches:
	    id = ((hasattr(branch, 'newbranch') and branch.newbranch.id) or
		    branch.id)

	    if id and id not in ids:
		ids.append(id)

	l = len(ids)
	if l == 0:
	    return None
	elif l == 1:
	    return ids[0]

	cmd = ['git', 'merge-base'] + ids
	return call(cmd, error=None, stderr=None).rstrip()


    @cached_property
    def info_branch(self):
	'''
	Return the limb's "limb-info" branch
	'''

	info_branchname = os.path.join(self.name, self.limb_info_branchname)
	branch = Branch.get(info_branchname)

	return ((branch and hasattr(branch, 'newbranch') and branch.newbranch)
		 or branch)


    @cached_property
    def common_branch(self):
	'''
	Return the limb's "common" branch
	'''

	common_branchname = os.path.join(self.name, self.limb_common_branchname)
	return Branch.get(common_branchname)


    @cached_property
    def dependent_branches(self):
	'''
	Find, read and parse the limb's branch_dependencies file.
	Return the limb's dependent branches.  Also, put branch
	flags, provider branches, and branch provider flags into
	branch.set_by_limb.
	'''

	dep_filename = self.branch_dep_filename
	for limb in (self,
		     self.remote_limb,
		     self.parent and self.parent.remote_limb):
	    if not limb:
		continue
	    info_branch = limb.info_branch
	    dep_ref = '%s:%s' % (info_branch.id, dep_filename)

	    try:
		# read branch_dependencies file
		cmd = ['git', 'show', dep_ref]
		dep_lines = call(cmd, stderr=None).splitlines()
		break
	    except:
		pass
	else:
	    dep_lines = []

	# parse branch dependencies
	arr = None
	expect_provider = False
	dependent_branches = []
	for orig_line in dep_lines:
	    line = orig_line

	    comment_index = line.find('#')
	    if comment_index >= 0:
		line = line[:comment_index]
		if self.re_blank.search(line):
		    continue

	    if self.re_blank.search(line):
		expect_provider = False
		continue

	    if expect_provider:
		m = self.re_provider.search(line)
		if m:
		    branchname = m.group(1)
		    if branchname.startswith('/'):
			remote = remote_alias()
			if remote:
			    branchname = remote + branchname
			else:
			    branchname = branchname[1:]
		    else:
			branchname = '%s/%s' % (self.name, branchname)
		    branch = Branch.get(branchname)
		    if not branch.id:
			if branch.remote_branch and branch.remote_branch.id:
			    branch = branch.remote_branch

		    provider_flags = m.group(2).split()
		    for flag in provider_flags:
			if flag not in branch.valid_provider_flags:
			    sys.stderr.write('branch_dependencies: '
				'Invalid flag "%s" for provider %s of '
				'dependent branch %s\n' %
				(flag, branch.name, dependent_branch.name))
			    sys.exit(1)
		    set_by_limb = dependent_branch.set_by_limb
		    set_by_limb['provider_flags'][branch] = provider_flags

		    arr.append(branch)
		    continue

	    m = self.re_dependent.search(line)
	    if m:
		arr = []
		branchname = '%s/%s' % (self.name, m.group(1))
		branch = Branch.get(branchname)
		if branch not in branch.limb.repository_branches:
		    rbranch = branch.remote_branch
		    if rbranch and rbranch in rbranch.limb.repository_branches:
			branch = rbranch

		branch.set_by_limb['providers'] = arr
		branch.set_by_limb['provider_flags'] = {}

		flags = m.group(2).split()
		for flag in flags:
		    if flag not in branch.valid_dependent_flags:
			sys.stderr.write('branch_dependencies: '
			    'Invalid flag "%s" for dependent branch %s\n' %
			    (flag, branch.name))
			sys.exit(1)
		branch.set_by_limb['flags'] = flags

		dependent_branches.append(branch)
		dependent_branch = branch

		expect_provider = True
		continue

	    raise GitError('Syntax error: %s, line: "%s"' %
				(dep_ref, orig_line))

	if hasattr(self, 'upstream_branches'):
	    for ub in self.upstream_branches:
		ub.merge_limb = self
		for branch in dependent_branches:
		    providers = branch.set_by_limb['providers']
		    flags_dict = branch.set_by_limb['provider_flags']
		    if ub not in providers:
			providers.insert(0, ub)
			flags_dict[ub] = ('upstream',  'reference')

	return dependent_branches


    @cached_property
    def branch_status_dict(self):
	'''
	Analyze the differences between the limb and limb.newlimb

	Add useful information by adding various attributes to these limbs,
	their branches, and the branches' commits
	'''

	if self.newlimb:
	    if self.branches and self.branches != self.repository_branches:
		raise GitError('newlimb with existing branches')

	    newlimb = self.newlimb
	    branches = self.repository_branches
	    newbranches = newlimb.repository_branches
	    subnames = set([x.subname for x in branches])
	    newsubnames = set([x.subname for x in newbranches])

	    for newbranch in newbranches:
		subname = newbranch.subname
		if subname not in subnames:
		    branchname = os.path.join(self.name, subname)
		    branches.append(Branch.get(branchname, Branch.zero_id))

	    for branch in branches:
		subname = branch.subname
		newbranchname = os.path.join(newlimb.name, subname)
		if subname not in newsubnames:
		    Branch.get(newbranchname, Branch.zero_id)
		branch.newbranch = Branch.find(newbranchname)

	unchanged = []
	created = []
	deleted = []
	changed = []

	for branch in self.branches:
	    if not branch.id and branch.parent:
		branch.oldbranch = branch.parent

	    if not hasattr(branch, 'newbranch'):
		branch.newbranch = branch

	    newbranch = branch.newbranch

	    if branch.id and branch.id == newbranch.id:
		unchanged.append(branch)
	    elif not branch.id:
		created.append(branch)
	    elif not newbranch.id:
		deleted.append(branch)
	    else:
		changed.append(branch)

	# deleted contains a list of all branches not in limb.newlimb
	# created contains a list of all branches not in limb
	# unchanged contains the list of branches that are not different
	# changed contains the list of common branches that are different

	result = {}
	result['unchanged'] = unchanged
	result['created'] = created
	result['deleted'] = deleted
	result['changed'] = changed

	return result


    @property
    def deleted_branches(self):
	return self.branch_status_dict['deleted']


    @property
    def created_branches(self):
	return self.branch_status_dict['created']


    @property
    def changed_branches(self):
	return self.branch_status_dict['changed']


    @property
    def unchanged_branches(self):
	return self.branch_status_dict['unchanged']


    def write_push_log_entry(self, file):
	zero_id = '0' * 40
	tokens = []
	tokens.append('%s UTC\n' % time.asctime(time.gmtime()))
	self.repository_branches		# fully populate self.branches
	for branch in sorted(self.branches, key=lambda x: x.subname):
		tokens.append(branch.subname)
		tokens.append(' ')
		tokens.append(branch.id or zero_id)
		if hasattr(branch, 'newbranch'):
		    tokens.append(' ')
		    tokens.append(branch.newbranch.id or zero_id)
		tokens.append('\n')

	tokens.append('\n')
	file.write(''.join(tokens))


    def exists(self):
	"""Returns True if self's name is that of a local or remote limb"""

	for prefix in ('refs/heads', 'refs/remotes'):
	    cmd = ['git', 'for-each-ref', '%s/%s/*' % (prefix, self.name)]
	    if bool(call(cmd, error=None, stderr=None)):
		return True

	return False


class Ref(object):
    '''
    Represents a git reference to a branch or a tag that is pushed.

    Each instance contains the name of the reference, and commit IDs
    of the state of the reference before (old) and after (new) the
    push.
    '''

    ref_dict = {}
    zero_id = '0' * 40

    def __init__(self, name, id=None, new_id=None, new=False):
	cls = self.__class__
	cls_name = cls.__name__

	if new_id:
	    newref = cls.get(name, new_id, new=True)
	    setattr(self, "new%s" % cls_name.lower(), newref)

	if new:
	    name = '../%s' % name

	if not id and not new_id:
	    cmd = ['git', 'rev-parse', name]
	    try:
		id = call(cmd, stderr=None).rstrip()
	    except:
		id = None
	elif id == self.zero_id:
	    id = None

	self.new = new
	self.lookup_name = name
	self.id = id
	if name in self.ref_dict:
	    raise GitError("%s instance '%s' already exists, use %s.get()" %
		    (cls_name, name, cls_name))
	self.ref_dict[name] = self


    @classmethod
    def find(cls, name):
	'''
	Find a Ref by name
	'''
	if name in Ref.ref_dict:
	    return Ref.ref_dict[name]
	else:
	    return None


    @classmethod
    def get(cls, name, id=None, new_id=None, new=False):
	'''
	Find a Ref by name if the ref exists, otherwise return a new Ref
	'''
	if id == cls.zero_id:
	    id = None
	ref = cls.find(name)
	if ref:
	    if id and ref.id != id:
		raise GitError("Pre-existing %s:%s with different id" %
		    (cls, name))
	    if new_id:
		raise GitError("Pre-existing %s:%s, but new_id specified" %
		    (cls, name))

	    return ref

	return cls(name, id, new_id, new)


    @cached_property
    def name(self):
	name = self.lookup_name
	if name.startswith('../'):
	    name = name[3:]
	return name


class Tag(Ref):
    '''
    Represents a pushed git tag reference
    '''

    prefix = 'refs/tags/'

    def __init__(self, name, id=None, new_id=None, new=False):
	Ref.__init__(self, name, id, new_id, new)


    def annotated(self):
	'''
	Return True if tag is annotated
	'''
	cmd = ['git', 'cat-file', '-t', self.id]
	git_object_type = call(cmd, error=None, stderr=None).strip()
	return git_object_type == 'tag'


class Branch(Ref):
    '''
    Represents a git branch
    '''

    prefix = 'refs/heads/'
    remote_prefix = 'refs/remotes/'

    re_branchname = re.compile(r'''
	((?P<limb_name>		.+)/)?
	(?P<branch_subname>
	    (?P<branch_type>	[^.]+)(\.[^/]+)?)
	''', re.X)

    re_branch_type = re.compile(r'.*/(?P<branch_type>[^/.]*)')

    valid_dependent_flags = ('frozen', 'deferred')
    valid_provider_flags = ('reference', 'upstream')


    def __init__(self, name, id=None, new_id=None, new=False):
	Ref.__init__(self, name, id, new_id, new)
	match = self.re_branchname.match(self.name)
	self.subname = match.group('branch_subname')
	self.subtype = match.group('branch_type')
	self.oldbranch = self
	self.set_by_limb = {}
	limb_name = match.group('limb_name')
	if limb_name:
	    limb = Limb.get(limb_name)
	    self.limb = limb
	    if not self.new:
		limb.branches.append(self)
	else:
	    self.limb = None


    @cached_property
    def flags(self):
	self.limb.dependent_branches	# sets set_by_limb['flags']
	if 'flags' in self.set_by_limb:
	    flags = self.set_by_limb['flags']
	else:
	    flags = []
	return flags


    @cached_property
    def providers(self):
	if not self.limb:
	    return []

	self.limb.dependent_branches	# sets set_by_limb['providers']

	if 'providers' not in self.set_by_limb:
	    return []

	return self.set_by_limb['providers']


    @cached_property
    def provider_flags(self):
	self.limb.dependent_branches	# sets set_by_limb['provider_flags']
	if 'provider_flags' in self.set_by_limb:
	    provider_flags = self.set_by_limb['provider_flags']
	else:
	    provider_flags = []
	return provider_flags


    @cached_property
    def commits_with_change(self):
	'''
	Returns an array containing one tuple for each changed commit in
	this branch.

	Each tuple consists of (commit, string_describing_change)
	'''

	old_commits = self.old_commits()
	commits_with_change = self.provenance(new=True)
	for i, (commit, change) in enumerate(commits_with_change):
	    changeid = commit.changeid

	    for old_commit in old_commits:
		if old_commit.changeid == changeid:
		    commits_with_change[i] = (commit, 'rebased')
		    commit.from_commits = [old_commit]
		    old_commit.rebased_to_commit = commit
		    break

	for old_commit in old_commits:
	    if not hasattr(old_commit, 'rebased_to_commit'):
		commits_with_change.append((old_commit, 'deleted'))

	return commits_with_change


    @cached_property
    def remote_branch(self):
	remote = remote_alias()
	if not remote:
	    return None
	return self.get('%s/%s' % (remote, self.name))


    @cached_property
    def commits(self):
	'''
	Return all commits added to this branch since the limb's merge base
	'''
	if self.id:
	    return read_commits(self, self.merge_base)
	else:
	    sys.stderr.write('\nNo branch %s\n' % self.name)
	    sys.exit(1)


    @cached_property
    def first_parent_commits(self):
	'''
	Return all commits added to this branch since the limb's merge base
	'''
	if self.id:
	    return read_commits(self, self.merge_base, first_parent=True)
	else:
	    sys.stderr.write('\nNo branch %s\n' % self.name)
	    sys.exit(1)


    @cached_property
    def changeids_with_commits(self):
	'''
	Return a list of (changeid, commit) tuples of added commits

	Commits are those added to this branch since the limb's merge
	base to those commits
	'''
	return [(x.changeid, x) for x in self.commits]


    @cached_property
    def changeid_to_commit(self):
	'''
	Return a mapping (dict) of each added changeid to its commit

	Commits are those added to this branch since the limb's merge
	base to those commits
	'''
	return dict(self.changeids_with_commits)


    @cached_property
    def first_parent_changeids_with_commits(self):
	'''
	Return a list of (changeid, commit) tuples of added commits

	Commits are those added to this branch since the limb's merge
	base to those commits
	'''
	return [(x.changeid, x) for x in self.first_parent_commits]


    @cached_property
    def first_parent_changeid_to_commit(self):
	'''
	Return a mapping (dict) of each added changeid to its commit

	Commits are those added to this branch since the limb's merge
	base to those commits
	'''
	return dict(self.first_parent_changeids_with_commits)


    @property
    def created(self):
	'''
	Return True if the the branch does not exist in limb
	'''
	return not self.id


    @property
    def deleted(self):
	'''
	Return True if the branch does not exist in limb.newlimb
	'''
	return self.newbranch and not self.newbranch.id


    @property
    def changed(self):
	'''
	Return True if the branch differs from self.newbranch
	'''
	return (self.newbranch and self.id != self.newbranch.id)


    @property
    def unchanged(self):
	'''
	Return True if the branch is the same as self.newbranch
	'''
	return not self.newbranch or self.id == self.newbranch.id


    @cached_property
    def merge_base(self):
	if hasattr(self, 'merge_limb'):
	    limb = self.merge_limb
	else:
	    limb = self.limb

	if not limb:
	    raise GitError('Branch "%s" is not part of a limb.\n' % self.name)

	return limb.merge_base


    @cached_property
    def new_merge_base(self):
	'''
	Return the merge base of self.oldbranch and self.newbranch
	'''
	if not self.oldbranch.id:
	    return self.merge_base

	cmd = ['git', 'merge-base',
		self.oldbranch.id, self.newbranch.id]
	base = call(cmd, error=None, stderr=None).rstrip()
	if not commit_contains(base, self.upstream_version):
	    base = self.upstream_version
	return base


    def old_commits(self):
	'''
	Return the list of commits on self, but not on self.newbranch
	'''
	return read_commits(self.oldbranch, self.new_merge_base)


    def new_commits(self):
	'''
	Return the list of commits on self.newbranch, but not on self
	'''
	return read_commits(self.newbranch, self.new_merge_base,
			    with_filenames=True)


    def provider_tuples_helper(self):
	'''
	Return an ordered list of branches that feed into self.

	Each item in the list is a pair of branches: (provider, dependent).
	The list may contain duplicates, which should be removed by the caller.
	'''

	tuples = []

	for provider in self.providers:
	    if 'reference' in self.provider_flags[provider]:
		continue
	    tuples += provider.provider_tuples_helper()

	for provider in self.providers:
	    if 'reference' in self.provider_flags[provider]:
		continue
	    tuples.append((provider, self))

	return tuples


    @cached_property
    def provider_tuples(self):
	'''
	Return an ordered list of branches that feed into "branch".

	Each item in the list is a pair of branches: (provider, dependent).
	'''

	tuples = self.provider_tuples_helper()

	# remove redundant entries from tuples, preserving order
	seen = set()
	return [x for x in tuples if x not in seen and not seen.add(x)]


    @cached_property
    def all_providers(self):
	'''
	Return an ordered list of all providers for this branch

	Both direct and indirect providers are included.
	The list is ordered so that each branch comes before branches that
	depend on it.
	'''

	return [provider for provider, dependent in self.provider_tuples]


    def all_dependents(self, limb):
	'''
	Return a list of all dependents in the given limb for which this
	branch is a provider, either directly or indirectly.
	'''

	return [x for x in limb.dependent_branches
		if self in x.all_providers or
		    self.remote_branch and
			self.remote_branch in x.all_providers]


    @cached_property
    def parent(self):
	'''
	Return the 'parent' branch of this branch.
	'''
	if self.limb and self.limb.parent:
	    for branch in self.limb.parent.repository_branches:
		if branch.subname == self.subname:
		    return branch

	return None


    @cached_property
    def upstream_version(self):
	'''
	Return the major kernel version on which this branch is based
	'''

	return self.limb.upstream_version


    def exists(self):
	"""Returns True if self's name is that of a local or remote branch"""

	return self.id in all_branch_ids()


    def contains(self, commit):
	"""Return True if the branch contains the commit"""
	try:
		commit = commit.id
	except:
	    try:
		commit = commit.name
	    except:
		pass
	return commit_contains(self.name, commit)


    @cached_property
    def rejected_changes(self):
	filename = 'MONTAVISTA/rejected_changes'
	ref = '%s:%s' % (self.id, filename)

	changes = []
	try:
	    lines = call(['git', 'show', ref], stderr=None).splitlines()
	except:
	    lines = []

	for line in lines:
	    line = line.lstrip()
	    line = re.sub(r'#.*', '', line)
	    line = re.sub('[\s].*', '', line)
	    if line:
		changes.append(line)

	return changes


    def from_branches_and_commits(self, changeid, new=False):
	from_branches_dict = {}
	from_branches_and_commits = []

	for branch in self.providers:
	    if new and hasattr(branch, 'newbranch'):
		if branch.newbranch:
		    branch = branch.newbranch
	    if changeid in branch.changeid_to_commit:
		bc_list = branch.from_branches_and_commits(changeid, new)
		for from_branch, from_commit in bc_list:
		    if new and hasattr(from_branch, 'newbranch'):
			if from_branch.newbranch:
			    from_branch = from_branch.newbranch
		    if from_branch in from_branches_dict:
			continue
		    from_branches_dict[from_branch] = True
		    from_branches_and_commits.append((from_branch, from_commit))

		if branch in from_branches_dict:
		    continue
		from_branches_dict[branch] = True
		commit = branch.changeid_to_commit[changeid]
		from_branches_and_commits.append((branch, commit))

	return from_branches_and_commits


    def provenance(self, new=False):
	'''
	Returns a tuple for each commit on self in the commit range.

	Each tuple consists of (commit, string_describing_change)
	'''

	commits_with_change = []

	if new:
	    commits = self.new_commits()
	else:
	    commits = self.commits
	for commit in commits:
	    from_commits = []
	    from_branches = []
	    changeid = commit.changeid
	    bc_list = self.from_branches_and_commits(changeid, new)
	    for from_branch, from_commit in bc_list:
		    from_commits.append(from_commit)
		    from_branches.append(from_branch)

	    if from_commits:
		commit.from_commits = from_commits
		commit.from_branches = from_branches

		change = 'cherry-picked'
	    else:
		change = 'created'

	    commits_with_change.append((commit, change))

	return commits_with_change


class Commit(object):
    '''
    Represents an individual git commit
    '''

    mv_header_fields = {
	'Source:'		: re.compile(r'.'),
	'MR:'		: re.compile(r'\d+(, \d+)*$'),
	'Type:'		: re.compile(r'''
				    (Defect\ Fix $) |
				    (Security\ Fix $) |
				    (Enhancement $) |
				    (Integration $)
				''', re.X),
	'Disposition:'	: re.compile(r'''
				    (Local $) |
				    (Backport\ from [ \t]+.) |
				    (Merged\ from [ \t]+.) |
				    (Accepted\ by [ \t]+.) |
				    (Rejected\ by [ \t]+.) |
				    (Submitted\ to [ \t]+.) |
				    (Needs\ submitting\ to [ \t]+.) |
				    (MontaVista $)
				''', re.X),
	'ChangeID:'	: re.compile(r'[0-9a-f]{40}$'),
    }

    re_through_last_whitespace = re.compile(r'.*\s')
    mv_terminator_prefix = 'Description:'
    commit_dict = {}


    def __init__(self, id):
	self.id = id
	self.commit_dict[id] = self
	self.from_branches = []
	self.from_commits = []


    @classmethod
    def get(cls, id):
	'''
	Find a commit with the given id or return a new Commit
	'''
	if id in cls.commit_dict:
	    return cls.commit_dict[id]
	else:
	    return read_commit(id)


    def parents(self):
	parents = []
	for line in self.header:
	    if line.startswith('parent '):
		id = line.rstrip().split()[1]
		commit = Commit.get(id)
		parents.append(commit)

	return parents


    def contains(self, commit_id):
	"""Return True if the commit contains the commit_id"""
	return commit_contains(self.id, commit_id)


    @cached_property
    def mv_header_lines(self):
	'''
	Return the list of MontaVista header lines in the commit's message body
	'''

	bad_line_count = 0
	lines = []

	for line in self.body:
	    l = line.strip()

	    if not l or l.startswith(self.mv_terminator_prefix):
		break

	    key = l.split(None, 1)[0]
	    if key not in self.mv_header_fields:
		for field in self.mv_header_fields:
		    if key.lower() == field.lower():
			break
		else:
		    bad_line_count += 1
		    continue

	    lines.append(line)

	if len(lines) < 2 or bad_line_count > 2:
	    lines = []

	return lines


    def mv_header_errors(self):
	'''
	Parse the MV header fields and return an array of error messages
	'''

	errors = []
	dict = {}

	for line in self.mv_header_lines:
	    if line.startswith(' ') or line.startswith('\t'):
		errors.append('leading whitespace: "%s"\n' % line)
		line = line.lstrip()

	    if line.endswith(' ') or line.endswith('\t'):
		errors.append('trailing whitespace: "%s"\n' % line)
		line = line.rstrip()

	    fields = line.split(None, 1)
	    if len(fields) < 2:
		errors.append('MV header line %s has no value\n' % line)
		continue

	    (key, value) = fields

	    if key not in self.mv_header_fields:
		errors.append('Bad MV header line: %s\n' % line)
		continue

	    if self.mv_header_fields[key].match(value):
		lkey = key.lower().rstrip(':')
		if lkey in dict:
		    errors.append('multiple instances of "%s"\n' % key)
		else:
		    dict[lkey] = value
		    if (lkey == 'source' and 'URL | Some Guy' in value or
			    lkey == 'disposition' and
				'Submitted to | Needs submi' in value):
			errors.append('Bad MV header value: "%s"\n' % line)
	    else:
		errors.append('Bad MV header value: "%s"\n' % line)

	if not errors:
	    for key in self.mv_header_fields.keys():
		lkey = key.lower().rstrip(':')
		if lkey == 'changeid' and not mvl6_kernel_repo():
		    continue
		if lkey not in dict:
		    errors.append('missing "%s" MV header line\n' % key)

	return errors


    @cached_property
    def mv_header_dict(self):
	'''
	Return a dictionary of MV header fields

	Each key is the lowercase name of the field and the value is
	the whitespace-stripped value for that key.
	'''

	dict = {}

	for line in self.mv_header_lines:
	    (key, value) = line.split(None, 1)
	    lkey = key.lower().rstrip(':')
	    dict[lkey] = value

	return dict


    @cached_property
    def changeid(self):
	'''
	Return the changeid for this commit
	'''
	changeid = self.mv_header_dict.get('changeid')
	if not changeid:
	    changeid = self.id
	return changeid


    @cached_property
    def bugz(self):
	'''
	Returns the last bugz number contained in the MV header's MR: field
	'''

	mr_list = self.mv_header_dict.get('mr')
	if not mr_list:
	    return None

	bugz = self.re_through_last_whitespace.sub('', mr_list)
	return bugz


    @cached_property
    def patch_id(self):
	'''
	Return the patch-id for this commit
	'''
	id = self.id
	cmd = 'git diff %s^..%s | git patch-id' % (id, id)
	return call(cmd, shell=True).split(None, 1)[0]


    @cached_property
    def committer_time(self):
	'''
	Return the commit time as an integer - seconds since the epoch
	'''
	for line in self.header:
	    if line.startswith('committer '):
		fields = line.split(' ')
		return int(fields[-2])


    def write_id(self, file):
	'''
	Write the commit's id to file
	'''
	file.write('commit %s\n' % self.id)


    def write_header(self, file):
	'''
	Write the commit's header to file
	'''
	for line in self.header:
	    if not line.startswith('author ') \
		    and not line.startswith('committer '):
		continue

	    fields = line.split(' ')
	    fields[-2] = time.ctime(int(fields[-2]))	# convert time
	    line = ' '.join(fields)

	    file.write("%s\n" % line)


    def abbrev_id(self):
	cmd = ['git', 'rev-list', '-1', '--pretty=format:%h', self.id]
	return call(cmd).splitlines()[1].rstrip()


    def write_abbrev_id_and_subject(self, file):
	'''
	Write the commit's abbreviated id and subject to file
	'''
	subject = ' '.join(self.subject)
	file.write('%s %s\n' % (self.abbrev_id(), subject))


    def write_subject(self, file):
	'''
	Write the commit's subject to file
	'''
	subject = ' '.join(self.subject)
	file.write('    %s\n' % subject)


    def write_body(self, file):
	'''
	Write the commit's body to file
	'''
	if self.body:
	    file.write('\n')
	    for line in self.body:
		file.write('    %s\n' % line)


    def write_patch(self, file):
	'''
	Write the commit's patch to file
	'''
	id = self.id
	cmd = ['git', '--no-pager', 'diff', '-p', '-M', '--stat', '--summary',
		'%s^..%s' % (id, id)]
	call(cmd, stdout=file)


def call(cmd, **kwargs):
    '''
    Call the given Linux command.

    This is very much like the subprocess.Popen() function that this
    function calls.  The main difference is that, by default, the
    command's stdout is returned as a string result of this function.

    Also, the command's stdout and stderr can be redirected to /dev/null
    by setting stdout=None or stderr=None in the kwargs.
    The return value is ignored if error=None is specified in kwargs.
    '''

    sys.stdout.flush()

    verbose = False
#    verbose = True
    if 'verbose' in kwargs:
	verbose = kwargs['verbose']
	del kwargs['verbose']

    error = True
    if 'error' in kwargs:
	if not kwargs['error']:
	    error = False
	del kwargs['error']

    dev_null = None
    if 'stdout' not in kwargs:
	kwargs['stdout'] = subprocess.PIPE
    elif kwargs['stdout'] == None:
	dev_null = open('/dev/null', 'w')
	kwargs['stdout'] = dev_null
    elif kwargs['stdout'] == sys.stdout or kwargs['stdout'] == 1:
	kwargs['stdout'] = None

    if 'stderr' in kwargs and kwargs.get('stderr') == None:
	if not dev_null:
	    dev_null = open('/dev/null', 'w')
	kwargs['stderr'] = dev_null

    if verbose:
	sys.stdout.write('-> ' + ' '.join(cmd) + '\n')
	sys.stdout.flush()

    p = subprocess.Popen(cmd, **kwargs)

    if dev_null:
	dev_null.close()

    if kwargs['stdout'] == subprocess.PIPE:
	output = p.stdout.read()
    else:
	output = ''

    if p.wait() != 0 and error:
	try:
	    cmd + ''
	except:
	    cmd = ' '.join(cmd)
	raise GitError('failed: "%s"' % cmd)

    return output


def read_commits(tip, ancestor_id, first_parent=False, with_filenames=False):
    '''
    Instantiate commits for a given range
    '''

    re_whitespace = re.compile(r'^\s*$')

    def read_commit(file, id, with_filenames=False):
	'''
	Read and instantiate an individual commit from file

	Returns the commit, and the next commit ID from the file, if any.
	'''

	header = []
	subject = []
	body = []
	filenames = []

	commit_prefix = 'commit '

	section = 'header'
	for line in file:
	    line = line.rstrip('\n')
	    if line.startswith(commit_prefix):
		next_id = line[len(commit_prefix):]
		break

	    if section == 'header':
		if not line:
		    section = 'subject'
		    continue
		header.append(line)
		continue

	    if section == 'filenames':
		if line:
		    filenames.append(line)
		continue

	    if not line:
		section = 'filenames'
		continue

	    line = line[4:]

	    if section == 'body':
		body.append(line)
		continue

	    if section == 'subject':
		if not line:
		    section = 'body'
		    continue
		subject.append(line)
		continue
	else:
	    next_id = None

	if id:
	    # strip trailing blank lines, AFAIK, only gregKH creates them
	    while body and re_whitespace.match(body[-1]):
		del body[-1]

	    if id in Commit.commit_dict:
		commit = Commit.commit_dict[id]
	    else:
		commit = Commit(id)
		commit.header = header
		commit.subject = subject
		commit.body = body
	    if with_filenames:
		commit.filenames = filenames
	else:
	    commit = None

	return commit, next_id

    try:
	if not tip.id:
	    return []
	tip = tip.id
    except:
	# use the tip string as is
	pass

    ancestor_stop = '^%s' % ancestor_id

    cmd = ['git', 'log', '--pretty=raw', '--topo-order', '--reverse']
    if first_parent:
	cmd.append('--first-parent')
    if with_filenames:
	cmd.append('--name-only')
    cmd += [tip, ancestor_stop]
#    print ' '.join(cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    commits = []
    commit, next_id = read_commit(p.stdout, None, with_filenames=with_filenames)
    while next_id:
	commit, next_id = read_commit(p.stdout, next_id, with_filenames)
	commits.append(commit)

    if p.wait() != 0:
#	print cmd
	raise GitError('failed: %s' % ' '.join(cmd))

    p.stdout.close()
    return commits


def read_commit(id):
    return read_commits(id, '%s^' % id)[0]


def notice(msg):
    '''
    Output a message on stdout
    '''

    sys.stdout.write(msg)


def current_branch():
    '''
    Return an object for the current branch
    '''
    cmd = ['git', 'rev-parse', '--symbolic-full-name', 'HEAD']
    fullname = call(cmd, error=None, stderr=None).rstrip()
    prefix = Branch.prefix
    if not fullname or not fullname.startswith(prefix):
	raise GitError("No current branch.\n")

    branchname = fullname[len(prefix):]
    return Branch.get(branchname)


def current_limb():
    '''
    Return an object for the current limb
    '''
    cb = current_branch()
    limb = cb.limb
    if not limb:
	raise GitError('Current branch "%s" is not part of a limb.\n' % cb.name)

    return limb


def changeid_diff(left, right, symmetric=False, with_rejects=False):
    """Return a list of commits in left but not in right, per ChangeIDs

    If symmetric == True, then also return the list of commits that
    are in right, but not in left.
    """

    left_changes_with_commits = left.first_parent_changeids_with_commits
    right_changes_with_commits = right.first_parent_changeids_with_commits
    left_dict = left.first_parent_changeid_to_commit
    right_dict = right.first_parent_changeid_to_commit

    if not with_rejects:
	for id in right.rejected_changes:
	    right_dict[id] = None

    left_ids = [x[0] for x in left_changes_with_commits]
    left_commits = [left_dict[x] for x in left_ids if x not in right_dict]

    # Delete any commits that are empty, as they won't propagate.  These are
    # going to generally be empty merge commits, anyway.
    i = 0
    end = len(left_commits)
    while (i < end):
        if is_empty_commit(left_commits[i]):
            del(left_commits[i])
            end -= 1
        else:
            i += 1

    if not symmetric:
	return left_commits

    if not with_rejects:
	for id in left.rejected_changes:
	    left_dict[id] = None

    right_ids = [x[0] for x in right_changes_with_commits]
    right_commits = [right_dict[x] for x in right_ids if x not in left_dict]

    # Delete any commits that are empty, as they won't propagate.  These are
    # going to generally be empty merge commits, anyway.
    i = 0
    end = len(right_commits)
    while (i < end):
        if is_empty_commit(right_commits[i]):
            del(right_commits[i])
            end -= 1
        else:
            i += 1

    return (left_commits, right_commits)


def branchnames(limbname="", recursive=False, branches=True, limbs=False):
    '''Return the the branch names of all branches with the given limbname'''

    prefix = limbname
    if prefix and not prefix.endswith('/'):
	prefix += '/'

    seen_limbs = {}
    names = []
    cmd = ['git', 'rev-parse', '--symbolic', '--branches', '--remotes']
    for name in call(cmd).splitlines():
	if prefix and not name.startswith(prefix):
	    continue
	if limbs:
	    sublimbname = os.path.dirname(name)
	    if not sublimbname in seen_limbs:
		seen_limbs[sublimbname] = 1
		if sublimbname != limbname:
		    if recursive or sublimbname.find('/', len(prefix)) < 0:
			names.append(sublimbname + '/')
	if not branches:
	    continue
	if not recursive and name.find('/', len(prefix)) >= 0:
	    continue
	names.append(name)

    return names


def subnames(limbname, names=None, recursive=False, branches=True, limbs=False):
    if not names:
	names = branchnames(limbname, recursive=recursive,
			    branches=branches, limbs=limbs)

    return [x[(len(limbname)+1):] for x in names]


cached_branch_ids = None

def all_branch_ids():
    global cached_branch_ids

    if cached_branch_ids:
	return cached_branch_ids

    cmd = ['git', 'rev-parse', '--branches', '--remotes']
    cached_branch_ids = call(cmd).splitlines()
    return cached_branch_ids


def is_repository():
    """Returns False if current directory doesn't look like a git repo."""

    cmd = ['git', 'rev-parse', '--git-dir']
    return bool(call(cmd, stderr=None))


def check_repository():
    """Raises GitError if current directory doesn't look like a git repo."""

    if not is_repository():
	raise GitError("Not in a git repository.")


cached_remote_alias = None

def remote_alias():
    global cached_remote_alias
    if cached_remote_alias:
	return cached_remote_alias

    cmd = ['git', 'config', '--get', 'mvista.remote-alias']
    lines = call(cmd, error=None, stderr=None).splitlines()
    if lines:
	cached_remote_alias = lines[-1].rstrip()
	return cached_remote_alias

    cmd = ['git', 'config', '--get-regexp', r'remote\..*\.url']
    lines = call(cmd, error=None, stderr=None).splitlines()
    mvlinux_lines = [x for x in lines if
	x.endswith('/mvlinux.git') or x.endswith('/mvlinux')]
    if len(lines) == 1:
	line = lines[0]
    elif len(mvlinux_lines) == 1:
	line = mvlinux_lines[0]
    else:
	sys.stderr.write(
	    '\nError: Cannot automatically determine the remote alias '
	    '(typically "origin").\n'
	    'Set the alias via '
	    '"git config --add mvista.remote-alias <alias>".\n')
	sys.exit(1)

    name = line.split()[0]
    loffset = len('remote.')
    roffset = len('.url')
    cached_remote_alias = name[loffset:-roffset]
    return cached_remote_alias


cached_repo_type = None

def repo_type():
    global cached_repo_type
    if cached_repo_type:
	return cached_repo_type

    cmd = ['git', 'config', 'mvista.repo-type']
    cached_repo_type = call(cmd, error=None, stderr=None).strip()
    if cached_repo_type:
	return cached_repo_type

    for case in (1, 2, 3):
	if case == 1:
	    cmd = ['git', 'config', 'remote.origin.url']
	    remote_url = call(cmd, error=None, stderr=None).strip()
	    if '/git/kernel/mvlinux.git' in remote_url:
		cached_repo_type = 'mvl6-kernel'
		break
	elif case == 2:
	    cmd = ['git', 'branch', '-r']
	    for branch_name in call(cmd, error=None, stderr=None).splitlines():
		if 'mvl-' in branch_name and '/limb-info' in branch_name:
		    cached_repo_type = 'mvl6-kernel'
		    break
	    else:
		continue
	    break
	elif case == 3:
	    cached_repo_type = 'non-mvl6-kernel'
	    break

    cmd = ['git', 'config', 'mvista.repo-type', cached_repo_type]
    call(cmd, error=None, stderr=None).strip()

    return cached_repo_type


def mvl6_kernel_repo():
    return repo_type() == 'mvl6-kernel'


def require_mvl6_kernel_repo():
    if repo_type() != 'mvl6-kernel':
	sys.stderr.write("""
This command is intended only for use in MVL6 (and later) kernel repositories.
You may annotate an MVL6 repository as such by running:
	git config mvista.repo-type mvl6-kernel
""")
	sys.exit(1)
