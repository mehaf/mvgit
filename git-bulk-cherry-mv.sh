#!/bin/bash
#
# Cherry pick an upstream commit into the tree with the 
# MV header inserted
#
# This is somewhat of a hack of ugly global variables. Shell scripting kind
# sucks for making beautifully structure programs.
#

SUBDIRECTORY_OK=Yes
OPTIONS_SPEC=
. $(git --exec-path)/git-sh-setup
require_work_tree
cd_to_toplevel

dotest=$GIT_DIR/.dotest-merge
mv_headers=0
mv_commit_cmd=" "

do_load_variables() {
	prev_head=$(cat "$dotest/prev_head")
	orig_head=$(cat "$dotest/orig_head")
	head_name=$(cat "$dotest/head-name")
	mv_source=$(cat "$dotest/mv_source")
	mv_bugz=$(cat "$dotest/mv_bugz")
	mv_type=$(cat "$dotest/mv_type")
	mv_headers=$(cat "$dotest/mv_headers")
	mv_commit_cmd=$(cat "$dotest/mv_commit_cmd")
	counter=$(cat "$dotest/counter")
	c_opt=$(cat "$dotest/c_opt")
}

is_merge_commit() {
	case "$(git log -n1 --pretty=format:%P $1)" in
	*' '*)
		return 0;;
	esac

	return 1
}

do_cherry_pick() {
	echo Picking `git log --pretty=oneline -n1 $1`
	if is_merge_commit $1; then
		# We now cherry-pick a merge commit ("-m 1" option) by
		# applying its associated patch (relative to first parent).

		merge_opt="-m 1"
	else
		merge_opt=
	fi
	git cherry-pick $merge_opt -n $1 2> /tmp/bulk-cherry-mv-err.$$
	rv=$?
	if grep -q "After resolving the conflicts" /tmp/bulk-cherry-mv-err.$$
	then
		cat <<RESOLVMSG
Automatic cherry-pick failed.  After resolving the conflicts, mark the
corrected paths with 'git add <paths>' or 'git rm <paths>'.
(Do NOT commit before running 'git bulk-cherry-mv --continue'.)
RESOLVMSG
	else
		cat /tmp/bulk-cherry-mv-err.$$
	fi
	rm /tmp/bulk-cherry-mv-err.$$
	return $rv
}

has_MV_header() {
	# only checks for existence, does not fully validate header
	seen_Source=
	seen_MR=
	seen_Type=
	seen_Disposition=
	seen_ChangeID=

	git log -1 --pretty=format:%b $revision > /tmp/bulk-cherry-mv-body.$$
	while read line; do
		case "$line" in
		''|Description:*)
			break ;;
		Source:*)
			[[ "$seen_Source" ]] && return 1
			seen_Source=true ;;
		MR:*)
			[[ "$seen_MR" ]] && return 1
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
	done < /tmp/bulk-cherry-mv-body.$$
	rm /tmp/bulk-cherry-mv-body.$$

	[[ "$seen_Source" && "$seen_MR" && "$seen_Type" &&
	   "$seen_Disposition" && "$seen_ChangeID" ]] &&
		return 0
	return 1
}

#
# TODO: Handle conflict resolution case
#
do_commit_mv() {
#	local oneline="`git log -n1 --pretty=format:%s $revision`"
#	git log -n1 --pretty=format:%b $revision >> $dotest/commit-msg-body.$$
#	echo >> $dotest/commit-msg-body.$$
#	echo "(Cherry-picked from commit $revision)" >> $dotest/commit-msg-body.$$

	#
	# Q: WTF do we use xargs?
	# A: B/C bash does crazy things to parameters when passing them and 
	#    xargs is the easiet way to not loose one's sanity.
	#
	#    See http://ubuntuforums.org/showpost.php?s=e3faa04fdc192707fe0064b043ca570c&p=4187899&postcount=2
	#
	echo $mv_commit_cmd --changeid $(git rev-list --no-walk $revision) $c_opt $revision -a > /tmp/bulk-cherry-mv-args.$$
	xargs -a /tmp/bulk-cherry-mv-args.$$ git commit-mv
	rm /tmp/bulk-cherry-mv-args.$$
}

fail_cherry_pick() {
	echo $counter > $dotest/counter
	cat <<RESOLVMSG

When you are ready to continue, run 'git bulk-cherry-mv --continue'.
If you would prefer to skip this patch, run 'git bulk-cherry-mv --skip'.
Or, to restore the original branch, run 'git bulk-cherry-mv --abort'.
RESOLVMSG
	move_to_original_branch
	die
}

do_main_loop() {
	local num_revs=`wc -l <$dotest/rev-list`

	while [ $counter -le $num_revs ]; 
	do
		revision=`head -$counter $dotest/rev-list | tail -1`
		do_cherry_pick $revision || fail_cherry_pick
		do_commit_mv

		counter=$(($counter + 1))
	done

	# If commit had no changes, MERGE_MSG was left behind.  Remove it.
	rm -f .git/MERGE_MSG
}

move_to_original_branch() {
	case "$head_name" in
	refs/*)
		message="Bulk cherry-pick finished"
		git update-ref -m "$message" \
			$head_name $(git rev-parse HEAD) &&
		git symbolic-ref HEAD $head_name ||
		die "Could not move back to $head_name"
		;;
	esac
}

do_return_to_branch() {
	move_to_original_branch
	rm -rf $dotest
	echo "Bulk cherry-pick finished"
}

merges_ok=
edit=

while test $# != 0
do
	case "$1" in
	--version)
		echo mvgit version @@MVGIT_VERSION@@
		exit 0
		;;
	--continue)
		if [ $# != 1 ] ; then
			echo "--continue is not the last argument"
			exit 1
		fi
		git diff-files --quiet || {
			echo "You must edit all merge conflicts and then mark them as resolved"
			echo "using 'git add <paths>' or 'git rm <paths>'."
			exit 1
		}
		if test -d "$dotest"
		then
			do_load_variables
			rm $GIT_DIR/MERGE_MSG
			revision=`head -$counter $dotest/rev-list | tail -1`
			echo Continuing at `git log --pretty=oneline -n1 $revision`
			do_commit_mv
			counter=$(($counter + 1))
			do_main_loop
			do_return_to_branch
		else
			die "No dotest directory found!"
		fi
		exit
		;;
	--skip)
		if [ $# != 1 ] ; then
			echo "--skip is not the last argument"
			exit 1
		fi
		git reset --hard HEAD || exit $?
		if test -d "$dotest"
		then
			do_load_variables
			rm $GIT_DIR/MERGE_MSG
			revision=`head -$counter $dotest/rev-list | tail -1`
			echo Skipping `git log --pretty=oneline -n1 $revision`
			counter=$(($counter + 1))
			do_main_loop
			do_return_to_branch
		else
			die "No dotest directory found!"
		fi
		exit
		;;
	--abort)
		if [ $# != 1 ] ; then
			echo "--abort is not the last argument"
			exit 1
		fi
		git rerere clear
		if test -d "$dotest"
		then
			do_load_variables
			move_to_original_branch
			git reset --hard $orig_head
			rm -r "$dotest"
			exit
		else
			die "No rebase in progress?"
		fi
		;;
	--source)
		mv_source="$2"
		if [ `echo $mv_source | wc -w` -gt 1 ]
		then
			mv_commit_cmd+="--source \"$mv_source\" "
		else
			mv_commit_cmd+="--source $mv_source "
		fi
	
		mv_headers=$(($mv_headers + 1))
		shift
		;;
	--bugz)
		if [ -n "$2" ]; then
			mv_bugz="$2"
			mv_commit_cmd+="--bugz $mv_bugz "
			mv_headers=$(($mv_headers + 1))
		else
			null_bugz=true
		fi
		shift
		;;
	--type)
		mv_type="$2"
		if [ `echo $mv_type | wc -w` -gt 1 ]
		then
			mv_commit_cmd+="--type \"$mv_type\" "
		else
			mv_commit_cmd+="--type $mv_type "
		fi
		mv_headers=$(($mv_headers + 1))
		shift
		;;
	--disposition)
		mv_disposition="$2"
		if [ `echo $mv_disposition | wc -w` -gt 1 ]
		then
			mv_commit_cmd+="--disposition \"$mv_disposition\" "
		else
			mv_commit_cmd+="--disposition $mv_disposition "
		fi
		mv_headers=$(($mv_headers + 1))
		shift
		;;
	--no-signoff)
		mv_commit_cmd+="--no-signoff "
		;;
	-e|--edit)
		edit=true
		;;
	-x)
		mv_commit_cmd+="-x "
		;; 
	-m)
		merges_ok=true
		;;
	--)
		read_stdin=true
		;;
	-*)
		usage
		exit
		;;
	*)
		break
		;;
	esac
	shift
done

if [ "$edit" = true ]
then
	c_opt=-c
else
	c_opt=-C
	mv_commit_cmd+="--no-edit "
	if [ -z "$mv_bugz" -a -z "$null_bugz" ]
	then
		echo "Either of --edit or --bugz options is required"
		exit 1
	fi
fi

if [ -z $read_stdin ]
then
	if [ $# -lt 1 ] ; then
		echo "argument needed to specify which revision"
		exit 1
	fi

	rev="$1"

	errors="$(
		$(git rev-parse "$rev" 2>&1 >/dev/null | grep fatal:) |
		while read error; do
			echo $error  >&2
			echo $error
		done
	)"
	[[ "$errors" ]] && die

	git rev-list --first-parent --date-order $rev --parents --reverse >/tmp/cherry-pick-list.$$

	has_merges=$(grep ' .* ' /tmp/cherry-pick-list.$$)

	if [[ $has_merges && ! "$merges_ok" ]]; then
		echo "The revisions you have selected to cherry-pick contain merges."
		echo "Please linearize the history or specify -m to enable cherry-picking "
		echo "merge commits."
		rm /tmp/cherry-pick-list.$$
		exit 1
	fi

	sed -i -e 's/ .*//' /tmp/cherry-pick-list.$$

	if [ "$has_merges" ]; then
		start_range=$(git rev-parse --not $rev | tail -1 |
			git rev-list --no-walk --stdin)

		oldest_commit=$(head -1 /tmp/cherry-pick-list.$$)
		parent_of_oldest_commit=$(git rev-parse $oldest_commit^)
		if [ $parent_of_oldest_commit != $start_range ]; then
			echo "Cannot cherry-pick the specified range because it contains commits that are"
			echo "outside of the range's first-parent line."
			rm /tmp/cherry-pick-list.$$
			exit 1
		fi
	fi
else
	echo "Reading revisions from stdin"
	sed -e 's/[ \t].*//; s/#.*//; /^[ \t]*$/d' >/tmp/cherry-pick-list.$$
	[[ -s /tmp/cherry-pick-list.$$ ]] || {
		rm /tmp/cherry-pick-list.$$
		die "No revisions found on stdin."
	}

	has_merges="$(git rev-list --no-walk --parents --stdin </tmp/cherry-pick-list.$$ | grep ' .* ')"

	if [[ $has_merges && ! "$merges_ok" ]]; then
		echo "The revisions contain merges.  Please linearize the history "
		echo "or specify -m to enable cherry-picking merge commits."
		rm /tmp/cherry-pick-list.$$
		exit 1
	fi

	xargs git rev-parse </tmp/cherry-pick-list.$$ 2>&1 >/dev/null |
		grep fatal: | tee /tmp/cherry-pick-errs.$$ >&2
	
	read err </tmp/cherry-pick-errs.$$
	rm /tmp/cherry-pick-errs.$$
	[[ "$err" ]] && rm /tmp/cherry-pick-list.$$ && die

	# set stdin to tty for editing by git-commit
	exec </dev/tty
fi

if [ "$edit" != true ]
then
	if [ -z "$mv_source" -o -z "$mv_disposition" -o -z "$mv_type" ]
	then
		no_headers=
		while read revision
		do
			if ! has_MV_header
			then
				no_headers+="$revision "
			fi
		done </tmp/cherry-pick-list.$$
		if [ -n "$no_headers" ]
		then
			echo "The following commits have no MV header:"
			for revision in $no_headers
			do
				if ! has_MV_header
				then
					git --no-pager log -1 --pretty=oneline $revision
				fi
			done
			echo
			echo "To cherry-pick commits without an MV header, it is necessary to specify either"
			echo "--edit or all of these options: --source, --bugz, --type, --disposition"
			rm /tmp/cherry-pick-list.$$
			exit 1
		fi
	fi
fi

if test -d "$dotest"
then
	rm /tmp/cherry-pick-list.$$
	die "previous dotest directory $dotest still exists." \
		'try git bulk-cherry-mv < --continue | --abort >'
else
	mkdir -p $dotest ||  {
		echo "It seems that I cannot create a $dotest directory, and I wonder if you
		are in the middle of patch application or another rebase.  If that is not
		the case, please rm -fr $dotest and run me again.  I am stopping in case
		you still have something valuable there."
		rm /tmp/cherry-pick-list.$$
		exit 1
	}
fi

# The tree must be really really clean.
git update-index --refresh || exit
diff=$(git diff-index --cached --name-status -r HEAD --)
case "$diff" in
?*)	echo "cannot cherry-pick: your index is not up-to-date"
	echo "$diff"
	rm /tmp/cherry-pick-list.$$
	exit 1
	;;
esac

# Move to a detached head so we can reset in the future
orig_head=$(git rev-parse HEAD^0)
head_name=$(git symbolic-ref HEAD 2> /dev/null)
case "$head_name" in
'')
	head_name="detached HEAD"
	;;
*)
	git checkout "$orig_head" > /dev/null 2>&1 || {
		rm /tmp/cherry-pick-list.$$
		die "could not detach HEAD"
	}
	;;
esac

erev_head=$orig_head
echo "$prev_head" > "$dotest/prev_head"
echo "$orig_head" > "$dotest/orig_head"
echo "$head_name" > "$dotest/head-name"
echo "$mv_source" > "$dotest/mv_source"
echo "$mv_bugz" > "$dotest/mv_bugz"
echo "$mv_type" > "$dotest/mv_type"
echo "$mv_headers" > "$dotest/mv_headers"
echo "$c_opt" > "$dotest/c_opt"
echo "$mv_commit_cmd" > "$dotest/mv_commit_cmd"

export mv_commit_cmd

mv /tmp/cherry-pick-list.$$ $dotest/rev-list

counter=1
do_main_loop
do_return_to_branch


