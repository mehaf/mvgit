#!/bin/sh

USAGE='[--append] [--patchprefix prefix] [--seriesfile <filename>] [--startnumber <num>] [--outputdir <dir>] <rev>'

SUBDIRECTORY_OK=Yes
OPTIONS_SPEC=
. $(git --exec-path)/git-sh-setup
set_reflog_action rebase
require_work_tree
cd_to_toplevel

outputdir="/tmp/patches"
seriesfile="series"
startnum=1

while test $# != 0
do
	case "$1" in
	--outputdir)
		outputdir="$2"
		shift;
		;;
	--seriesfile)
		seriesfile="$2"
		shift;
		;;
	--patchprefix)
		patchprefix="$2"
		shift;
		;;
	--append)
		append=1
		;;
	--startnumber)
		startnum=$2
		numbered=true
		shift
		;;
	*)
		break
		;;
	esac
	shift
done

if [ $# -ne 1 ]
then
	usage
	exit 1;
fi	
rev="$1"

#
# Validate that the rev given in the commaind line is an actual
# revision in the tree.
#
git-rev-parse --verify $rev > /dev/null 2>&1
if [ $? -ne 0 ]
then
	exit 1
fi

#
# Check for linear history.
# We don't allow quitl exporting out of non-linear histories as
# we are not guaranteed a clean set of patches that will apply on
# top of each other.
#
revcount=`git-rev-list --no-merges $rev.. | wc -l`
merge_revcount=`git-rev-list $rev.. | wc -l`

if [ $revcount -ne $merge_revcount ]
then
	echo "The revisions you have selected to export contain merges"
	echo "Please linearize the history before exporting to quilt"
	exit 1;
fi

#
# FIXME: Stupid error... I do not fully grok redirect
#
if [ ! -d $outputdir ]
then
	mkdir -p $outputdir 2>&1 > /dev/null || \
		die "Could not create $outputdir"
elif [ -f $outputdir ]
then
	die "$outputdir exists and is a regular file"
elif [ ! -w $outputdir ]
then
	die "$outputdir is not writeable"
fi

git-format-patch --start-number $startnum $rev > $outputdir/${seriesfile}_tmp.$$

#
# Cleanup patch names
#
for patch in `cat $outputdir/${seriesfile}_tmp.$$`
do
	new_patchname=`echo -n $patch | sed s/-/_/g`

	if [ -z $numbered ]
	then	
		new_patchname=`echo -n $new_patchname | sed s/^[0-9][0-9][0-9][0-9]_//`
	fi

	mv $patch $outputdir/${patchprefix}${new_patchname}
	echo ${patchprefix}${new_patchname} >> \
		$outputdir/${seriesfile}_clean_tmp.$$
done

rm $outputdir/${seriesfile}_tmp.$$

if [ -z $append ]
then
	mv $outputdir/${seriesfile}_clean_tmp.$$ $outputdir/$seriesfile
else
	cat $outputdir/${seriesfile}_clean_tmp.$$ >> $outputdir/$seriesfile
	rm $outputdir/${seriesfile}_clean_tmp.$$
fi


