#!/bin/bash

# NAME
# git-push-mv - Push a branch to MontaVista git kernel repository
#
# SYNOPSIS
# git-push-mv [--branch <branch>] [--bugz <bugno>|--dev] [--merge] <repo>
#
# DESCRIPTION
#
# git-push-mv is an extension on top of the standard git-push command
# that is aware of MontaVista's git repository layout and naming scheme.
#
# OPTIONS
# ---branch <branch>
# Push the local branch specified in the command option. If this option
# is missing, "git-push-mv" will push the current HEAD.
#
# --bugz <bugno>
# Push the requested branch into the repository's "bugfixes"
# namespace. git-commit-mv will automatically determine the appropriate
# version number to use in the branch name. See GitBugFixing in the
# MontaVista Wiki for details on branch naming.
#
# --dev
# Push the requested branch into the repository's "dev" namespace.  This
# is the default behavior unless "--bugz" is specified. The push must be
# a fast-forward push or it will fail.
#
# --merge
# Request a merge of the bugfix branch. This option must be used in
# conjunction with the "--bugz" option.
#
# <repo> 
# The name of the kernel repository to push to.
#
# EXAMPLE
# To push an update to bug number 12345 in the f2.6.24 kernel, one would
# run:
#
# git-push-mv --bugz 12345 f2.6.24

#-----------------------------------------------------------------------------
ERROR () {
    echo >&2 "ERROR" "$@"
}
#-----------------------------------------------------------------------------
WARNING () {
    echo >&2 "WARNING" "$@"
}
#-----------------------------------------------------------------------------
TRACE () {
    echo >&2 "TRACE" "$@"
    "$@"  ### expands into several args
}
#-----------------------------------------------------------------------------
# returns stdout and exit-code from perl
transform () {
    local refname="$1"
    local format="$2"
    local cmd="$3"

    echo "$refname" |
    perl -ne 'if (m'"$format"') { print '"$cmd"' ; } else { exit 1 ; }'
}
#-----------------------------------------------------------------------------
. $(git --exec-path)/git-sh-setup
require_work_tree
cd_to_toplevel

BUGNO=""
LOCAL_HEAD=""
REMOTE_HEAD=""
MERGE_REQUEST=""
REVIEW_REQUEST=""

while [ "$#" != 0 ] ; do
    case "$1" in
	--branch)  # ---branch <branch>
	    if [ -n "$LOCAL_HEAD" ] ; then
		ERROR "can't use --branch option more than once"
		exit 2
	    fi
	    LOCAL_HEAD="$2"
	    shift
	    ;;
	--bugz)    # --bugz <bugno>
	    if [ -n "$REMOTE_HEAD" ] ; then
		ERROR "can't use --bugz and --dev options together"
		exit 2
	    fi
	    if [ -n "$BUGNO" ] ; then
		ERROR "can't use --bugz option more than once"
		exit 2
	    fi
	    BUGNO="$2"
	    shift
	    ;;
	--dev)     # --dev
	    if [ -n "$BUGNO" ] ; then
		ERROR "can't use --bugz and --dev options together"
		exit 2
	    fi
	    if [ -n "$REMOTE_HEAD" ] ; then
		ERROR "can't use --bugz and --dev option together or more than once"
		exit 2
	    fi
	    REMOTE_HEAD="dev"
	    ;;	
	--merge)   # --merge <email_address>
	    MERGE_REQUEST="$2"
	    shift
	    ;;
	--review)  # --review <email_address>
	    REVIEW_REQUEST="$2"
	    shift
	    ;;
	-*)
	    ERROR "unknown option $1"
	    exit 2
	    ;;
	*)         # <repo>
	    if [ "$#" != 1 ] ; then
		ERROR "arguments after the remote name are not allowed: $1"
		exit 2
	    fi
	    REPO="$1"
	    break
	    ;;
    esac
    shift
done

if [ -z "$REPO" ] ; then
    REPO="origin"
fi

if [ -z "$LOCAL_HEAD" ] ; then
    LOCAL_HEAD="HEAD"
fi

if ! SHA1_HEAD=`git-rev-parse "$LOCAL_HEAD"` ; then
    ERROR "couldn't git-rev-parse $LOCAL_HEAD"
    ERROR "this probably means it isn't a branch"
    exit 2
fi

# check repo before we start querying it
if ! git-remote show "$REPO" > /dev/null ; then
    ERROR "git-remote doesn't think $REPO is a remote repository name"
    ERROR "(or your network is down)"
    ERROR "the available remote repositories are: "
    git-remote | sed "s/^/    /" >&2
    exit 2
fi

if [ -n "$BUGNO" ] ; then
    PREFIX="refs/heads/bugfixes/${BUGNO}_v"
    refname=`git-ls-remote -h "$REPO" | cut -f 2 | grep "$PREFIX" | sort | tail -1`
    format='(^(refs/heads/)(bugfixes/)([0-9]+)(_v)([0-9][0-9])$)'
    new_version='$2,$3,$4,sprintf ("%2.2d", 1)'
    increment_version='$2,$3,$4,sprintf ("%2.2d", $5+1)'
    if [ -z "$refname" ] ; then
	refname="${PREFIX}00"
	REMOTE_HEAD=$(transform "$refname" "$format" "$new_version")
	WARNING "new bug number ($REMOTE_HEAD), did you make typo?"
    else
	# Namespace format:
	#   bugfixes/<bug_number>_v<version>
	#   parens so regex substition can be used
	#   first and last char is perl m// command delimiter
	REMOTE_HEAD=$(transform "$refname" "$format" "$increment_version")
	WARNING "next bug number ($REMOTE_HEAD)"
    fi
fi

if [ -z "$REMOTE_HEAD" ] ; then
    REMOTE_HEAD="dev"
fi

if [ -n "$REVIEW_REQUEST" ] ; then
    TAGNAME="$REMOTE_HEAD/Request_Review/$SHA1_HEAD"
    TRACE git-tag -a -m "$REVIEW_REQUEST" "$TAGNAME" "$SHA1_HEAD"
    TRACE git-push "$REPO" "$TAGNAME"
    TRACE git-tag -d "$TAGNAME"
fi

if [ -n "$MERGE_REQUEST" ] ; then
    TAGNAME="$REMOTE_HEAD/Request_Merge/$SHA1_HEAD"
    TRACE git-tag -a -m "$MERGE_REQUEST" "$TAGNAME" "$SHA1_HEAD"
    TRACE git-push "$REPO" "$TAGNAME"
    TRACE git-tag -d "$TAGNAME"
fi

TRACE git-push "$REPO" "$LOCAL_HEAD":refs/heads/"$REMOTE_HEAD"
