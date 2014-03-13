#!/bin/bash
# git-blame-feature FEATURE
# searches for string FEATURE in the kernel and returns a list of commits that provide the lines that match
# FEATURE is intended to be a kernel config option
#
FEATURE=$1
commits=`mktemp -t gbf-com-XXX`
search=`mktemp -t gbf-ag-XXX`

echo "Lines matching ${FEATURE}:"
ag -w ${FEATURE} >> ${search}
cat ${search}

IFS=":"

cat ${search} | while read filename lineno comment
do
	if [[ ${filename} != *Kconfig ]]
	then
		echo "warning: ${FEATURE} matched in non-Kconfig file ${filename}!" >&2
	else
		git blame -sL ${lineno},+1 ${filename} >> ${commits}
	fi
done

ag -w CONFIG_${FEATURE} > ${search}
cat ${search}

cat ${search} | while read filename lineno comment
do
	git blame -sL ${lineno},+1 ${filename} >> ${commits}
done

echo "Commits:"
sort ${commits} | awk '{print $1}' | uniq | xargs -l git log --oneline -1 

rm ${commits} ${search}
