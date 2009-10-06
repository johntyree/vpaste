#!/bin/bash

# Copyright (C) 2009 Andy Spencer
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# Remove url codings form stdin
function urldecode {
	sed -e 's/%\([0-9A-F][0-9A-F]\)/\\\\\x\1/g' | xargs echo -e
}

# Extract an uploaded file from standard input
# $1 is the boundary delimiter for the file
function cut_file {
	awk "
		/--$1/          {st=1};
		st==2           {print \$0};
		/$1--/          {st=0};
		/^\\r$/ && st==1 {st=2};
	" | head -c -2
	# Remove trailing ^M's that come with CGI
}

# Format a file for viewing 
function do_print {
	[ -f "$1" ] && input="$1" || input="db/$1" 
	output="$(mktemp)"
	modeline="$(echo $QUERY_STRING | urldecode)"

	# I have some plugins in ~/.vim
	#
	# Run vimhi.sh in screen to trick it into thinking
	# that it has a real terminal, not that we also have to
	# set term=xterm-256color in vimrc
	HOME=/home/andy \
	screen -D -m ./vimhi.sh "$input" "$output" "$modeline"
	cat "$output" 
}


# Upload handler
function do_upload {
	output="$(mktemp db/XXXXX)"
	uri="$SCRIPT_URI$(basename "$output")"
	cut_file "$1" > "$output"
	echo "$uri"
}

# Default index page
function do_help {
cat - <<EOF
<html>
	<body>
	<p>Usage:</p>
	<pre>   cat foo | curl -F 'x=<-' $SCRIPT_URI</pre>
	<p>Source:</p>
	<ul>
	<li><a href="index.cgi?ft=sh">index.cgi</a>
	<li><a href="vimhi.sh?ft=sh">vimhi.sh</a>
	<li><a href="vimrc?ft=vim">vimrc</a>
	<li><a href="htaccess?ft=apache">htaccess</a>
	</ul>
	<p>Latest uploads:</p><ul>
	$(for i in $(ls -t db | head -n 5); do
		uri="$SCRIPT_URI$i"
		echo "<li><a href='$uri'>$uri</a>"
	done)
	</ul>
	</body>
</html>
EOF
}

# Main
pathinfo="${SCRIPT_URL/*vpaste\/}"
boundary="${CONTENT_TYPE/*boundary\=/}"

# Print out a generic header
echo Content-Type: text/html; charset=UTF-8
echo

if [ "$pathinfo" ]; then
	do_print "$pathinfo"
elif [ "$CONTENT_TYPE" ]; then
	do_upload "$boundary"
else
	do_help
fi
