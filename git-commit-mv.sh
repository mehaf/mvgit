#!/bin/bash
#
# Commit changes to the tree using the MontaVista Header
#

# Header Format:
######################################################################################
# Oneline summary of change, less then 60 characters
#
# Source: MontaVista Software, LLC | URL | Some Guy <email@addr>
# MR:
# Type: Defect Fix | Security Fix | Enhancement | Integration
# Disposition: Submitted to | Needs submitting to | Merged from | Rejected by | Backport | Local | MontaVista
# Description:
#
# Verbose description of the change
#
# Signed-off-by: Name <email@mvista.com>
#
#####################################################################################

SUBDIRECTORY_OK=Yes
OPTIONS_SPEC=
. $(git --exec-path)/git-sh-setup
require_work_tree
cd_to_toplevel

source="MontaVista Software, LLC | URL | Some Guy <email@addr>"
bugz="Bugzilla bug number"
type="Defect Fix | Security Fix | Enhancement | Integration"
changeid=""
disposition="Submitted to | Needs submitting to | Merged from | Accepted by | Rejected by | Backport from | Local"
oneline="Oneline summary of change, less then 60 characters"
blanknote="
# *** Leave above line blank for clean log formatting ***"

commit_opt="-t"
preserve_author=false

email=$GIT_COMMITTER_EMAIL
if [ -z "$email" ]
then
	email=`git config --get user.email`
fi
if [ -z "$email" ]
then
	echo "Either git-config user.email or GIT_COMMITTER_EMAIL env variable must be set"
	error=1
fi

name=$GIT_COMMITTER_NAME
if [ -z "$name" ]
then
	name=`git config --get user.name`
fi
if [ -z "$name" ]
then
	echo "Either git-config user.name or GIT_COMMITTER_NAME env variable must be set"
	error=1
fi

if [ ! -z $error ]
then
	exit
fi

while test $# != 0
do
	case "$1" in
	--source)
		source="$2"
		shift
		;;
	--bugz)
		bugz="$2"
		bugz_arg="$2"
		shift
		;;
	--type)
		type="$2"
		shift
		;;
	--disposition)
		disposition="$2"
		shift
		;;
	--changeid)
		changeid="$2"
		shift
		;;
	--oneline)
		oneline="$2"
		if [[ $commit_opt = -t ]]; then
			commit_opt="-e -F"
		fi
		shift;;
	-c|-C)
		if [[ "$1" = -c ]]; then
			if [[ $commit_opt = -t ]]; then
				commit_opt="-e -F"
			fi
		else
			commit_opt="-F"
		fi
		preserve_author=true

		orig_commit="$2"
		shift

		git rev-parse --verify $orig_commit > /dev/null 2>&1
		if [[ $? -ne 0 ]]
		then
			die "Error: $orig_commit is not a valid revision"
		fi

		oneline=`git log -n1 --pretty=format:%s $orig_commit`
		git log -n1 --pretty=format:%b $orig_commit > /tmp/commit-body.$$
		bodyfile="/tmp/commit-body.$$"
		rmbodyfile=true
		;;
	-x)
		cherry_pick=true
		;;
	--no-signoff)
		no_signoff=true
		;;

	#
	# Following parameters should only be used by scripts
	#
	--bodyfile)
		bodyfile=$2
		shift
		if [ ! -f $bodyfile ]
		then
			echo >&2 $bodyfile does not exist
			exit 1
		fi
		if [ ! -r $bodyfile ]
		then
			echo >&2 $bodyfile is not readable
			exit 1
		fi
		blanknote="
"
		;;
	--no-edit)
		blanknote="
"
		commit_opt="-F"
		;;

	*)
		break
		;;
	esac
	shift
done

#
# Do some validation
#

if [[ -z $orig_commit && -n $cherry_pick ]]
then
	die "Error: -c and -x must be used together"
elif [[ -n $orig_commit && -n $cherry_pick ]]
then
	echo >> $bodyfile
	echo "(Cherry-picked from commit $orig_commit)" >> $bodyfile
fi

has_MV_header() {
	[[ "$bodyfile" ]] || return 1

	# only checks for existence, does not fully validate header
	seen_Source=
	seen_MR=
	seen_Type=
	seen_Disposition=
	seen_ChangeID=

	while read line; do
		case "$line" in
		''|Description:*)
			break ;;
		Source:*)
			[[ "$seen_Source" ]] && return 1
			seen_Source=true ;;
		MR:*)
			[[ "$seen_MR" ]] && return 1
			orig_MR_line="$line"
			seen_MR=true ;;
		Type:*)
			[[ "$seen_Type" ]] && return 1
			seen_Type=true ;;
		Disposition:*)
			[[ "$seen_Disposition" ]] && return 1
			seen_Disposition=true ;;
		ChangeID:*)
			[[ "$seen_ChangeID" ]] && return 1
			seen_ChangeID=true ;;
		esac
	done < "$bodyfile"

	[[ "$seen_Source" && "$seen_MR" && "$seen_Type" &&
	   "$seen_Disposition" && "$seen_ChangeID" ]] &&
		return 0
	return 1
}

echo "$oneline" > /tmp/git-commit-mv-msg.$$

if has_MV_header; then
	if [[ -n "$bugz_arg" ]]; then
		orig_MR=$(echo $orig_MR_line | sed -e 's/^[^ \t][^ \t]*[ \t][ \t]*//' -e 's/,.*//')
		if [[ $orig_MR != $bugz_arg ]]; then
			sed -i -e "1,/^$/{1,/^Description:/{/^MR:/s/.*/MR: $orig_MR, $bugz_arg/}}" $bodyfile
		fi
	fi
else
	cat <<EOF >> /tmp/git-commit-mv-msg.$$
$blanknote
Source: $source
MR: $bugz
Type: $type
Disposition: $disposition
ChangeID: $changeid
Description:
EOF
fi

echo >> /tmp/git-commit-mv-msg.$$

if [[ -z $bodyfile ]]
then
	echo "# Verbose description of the change" >> /tmp/git-commit-mv-msg.$$
else
	cat $bodyfile >> /tmp/git-commit-mv-msg.$$
fi

signed_off_line="Signed-off-by: $name <$email>"

if [[ -z $no_signoff ]] &&
	! grep -q -F "$signed_off_line" /tmp/git-commit-mv-msg.$$
then
	# Remove trailing blank lines.
	sed -i -e ':a;/^[ \t\n]*$/{$d;N;ba;}' /tmp/git-commit-mv-msg.$$

	if ! (tail -1 /tmp/git-commit-mv-msg.$$ | grep -q -F -- "-by: "); then
		echo >> /tmp/git-commit-mv-msg.$$
	fi
	echo "$signed_off_line" >> /tmp/git-commit-mv-msg.$$
fi

if [[ -z $changeid ]]
then
	# generate a change ID based on several things related to
	# what's being committed.
	changeid=$(
		(
			git rev-list -1 HEAD
			cat /tmp/git-commit-mv-msg.$$
			git diff --cached HEAD
			echo $signed_off_line
			date
		) | git hash-object --stdin
	)
	sed -i "s/^ChangeID: $/ChangeID: $changeid/" /tmp/git-commit-mv-msg.$$
fi

if [[ "$preserve_author" = true ]]
then
	export GIT_AUTHOR_NAME="$(git log -1 --pretty=format:%an $orig_commit)"
	export GIT_AUTHOR_EMAIL="$(git log -1 --pretty=format:%ae $orig_commit)"
	export GIT_AUTHOR_DATE="$(git log -1 --pretty=format:%ai $orig_commit)"
fi

git commit $commit_opt /tmp/git-commit-mv-msg.$$ $@

rm /tmp/git-commit-mv-msg.$$
[ -n "$rmbodyfile" ] && rm $bodyfile
