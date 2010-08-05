#!/bin/bash
#
# Add a "Signed-off-by" or "Acked-by" line to a set of commits
#

bugz=
disposition=
source=
type=
signoff="Signed-off-by"
changeid=

while test $# != 1 ; do
	case "$1" in
	--version)
		echo mvgit version @@MVGIT_VERSION@@
		exit 0
		;;
	--name)
		name="$2"
		shift
		;;
	--email)
		email="$2"
		shift
		;;
	--ack)
		signoff="Acked-by"
		;;
	--nack)
		signoff="Nacked-by"
		;;
	--bugz)
		bugz="$2"
		shift
		;;
	--disposition)
		disposition="$2"
		shift
		;;
	--source)
		source="$2"
		shift
		;;
	--type)
		type="$2"
		shift
		;;
	--changeid)
		changeid=true
		;;
	-f|--force)
		force="$1"
		;;
	-*)
		echo >&2 "unknown option: $1"
		error=1
		;;
	esac
	shift
done	

if [ -z "$email" ] ; then
	email=$GIT_COMMITTER_EMAIL
fi
if [ -z "$email" ] ; then
	email=`git config --get user.email`
fi
if [ -z "$email" ] ; then
	echo "Either git config user.email or GIT_COMMITTER_EMAIL env variable must be set"
	echo "or --email must be specified"
	error=1
fi

if [ -z "$name" ] ; then
	name="$GIT_COMMITTER_NAME"
fi
if [ -z "$name" ] ; then
	name="`git config --get user.name`"
fi
if [ -z "$name" ] ; then
	echo "Either git config user.name or GIT_COMMITTER_NAME env variable must be set"
	echo "or --name must be specified"
	error=1
fi

if [ ! -z $error ] ; then
	exit 2
fi

signoff_line="$signoff: $name <$email>"
signoff_tmpfile=$(mktemp /tmp/git-signoff-mv.XXXXXX) || exit
trap "rm -f -- \"$signoff_tmpfile\"" EXIT
export signoff_line signoff_tmpfile bugz disposition source type changeid

# from http://sed.sourceforge.net/sed1line.txt
# # delete all trailing blank lines at end of file
# sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'  # works on all seds
# sed -e :a -e '/^\n*$/N;/\n$/ba'        # ditto, except for gsed 3.02.*

# dfarnworth's extension is:
# sed -e :a -e '/^[ \t\n]*$/{$d;N;ba' -e '}'  # works on all seds

# the (ahem) cleanest way to insert a ' in the middle of a '' string
# seems to be with '\'' (ie, drop out of '' string, quote a ',
# then start another '' string to be concatenated with the first
# see the comments above for the original command
# if you have a better way, go for it..
git filter-branch $force --msg-filter '
	sed -e :a -e '\''/^[ \t\n]*$/{$d;N;ba'\'' -e '\''}'\'' >"$signoff_tmpfile"
	# the following sed commands use ctrl-A as a separator because it
	# is extremely unlikely to occur in the MV commit headers
	if [ -n "$bugz" ] ; then
		orig_MR=$(sed -n -e "/^MR:/{s/, .*//; s/.*[ 	]//p; q}" "$signoff_tmpfile")
                echo $orig_MR > /tmp/deleteme1
		if [[ -n $orig_MR ]] && [[ $orig_MR != $bugz ]]; then
                        echo $bugz > /tmp/deleteme2
			sed -i -e "/^$/,/^$/{/^$/,/^Description:/{/^MR:/s.*MR: $orig_MR, $bugz}}" $signoff_tmpfile
		fi
	fi
	if [ -n "$disposition" ]
	then
		sed -i -e "/^$/,/^$/{/^$/,/^Description:/{/^Disposition:/s.*Disposition: $disposition}}" $signoff_tmpfile
	fi
	if [ -n "$source" ]
	then
		sed -i -e "/^$/,/^$/{/^$/,/^Description:/{/^Source:/s.*Source: $source}}" $signoff_tmpfile
	fi
	if [ -n "$type" ]
	then
		sed -i -e "/^$/,/^$/{/^$/,/^Description:/{/^Type:/s.*Type: $type}}" $signoff_tmpfile
	fi
	if [ -n "$changeid" ] && ! grep -q '^ChangeID:' "$signoff_tmpfile"
	then
		sed -i -e "/^$/,/^$/{/^Description:/i \
ChangeID: $GIT_COMMIT
}" "$signoff_tmpfile"
	fi
	cat "$signoff_tmpfile"
	if ! grep -q -F "$signoff_line" "$signoff_tmpfile"; then
		if ! (tail -1 "$signoff_tmpfile" | grep -q -F -- "-by: "); then
			echo
		fi
		echo "$signoff_line"
	fi' $@

rm -rf -- $(git rev-parse --git-dir)/refs/original "$signoff_tmpfile"
trap - EXIT
