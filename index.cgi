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
function get_modeline {
	modeline=$(
		echo "$QUERY_STRING" | 
		sed -e 's/%\([0-9A-F][0-9A-F]\)/\\\\\x\1/g; s/[,&]/ /g' |
		xargs echo -e
	)
	echo "vim: $modeline"
}

# Extract an uploaded file from standard input
# $1 is the boundary delimiter for the file
function cut_file {
	awk "
		/--$1/ {st=1};
		st==2  {print \$0};
		/$1--/ {st=0};
		/^\\r$/ && st==1 {st=2};
	" | head -c -2
	# Remove trailing ^M's that come with CGI
}

# Print out a generic header
function start_html {
	echo "Content-Type: text/html; charset=UTF-8"
	echo
}

# Print out a generic header
function start_text {
	echo "Content-Type: text/plain; charset=UTF-8"
	echo
}

# Format a file for viewing 
function do_print {
	if [ -f "$1" ]; then
		input="$1"
	elif [ -f "db/$1" ]; then
		input="db/$1"
		trim='1d' # sed command to remove cruft
	else
		echo "Status: 404"
		start_text
		echo "File '$1' not found"
		return
	fi


	if [[ "$REQUEST_URI" == *'?'* ]]; then
		# Create a temp file with the provided modeline
		output="$(mktemp)"
		tmp="$(mktemp)"
		cat  "$input" >> "$tmp"
		get_modeline  >> "$tmp"

		# - I have some plugins in ~/.vim
		# - Run ex in screen to trick it into thinking that it
		#   has a real terminal, not that we also have to set
		#   term=xterm-256color in vimrc
		HOME=/home/andy \
		screen -D -m ex -u vimrc \
			'+$d|'$trim     \
			'+TOhtml'       \
			"+sav! $output" \
			'+qall!'        \
			"$tmp"

		start_html
		cat "$output" 
		rm "$tmp" "$output"
	else
		start_text
		sed "$trim" "$input"
	fi
}


# Upload handler
function do_upload {
	output="$(mktemp db/XXXXX)"
	uri="$SCRIPT_URI$(basename "$output")"
	(get_modeline; cut_file "$1") > "$output"
	start_text
	echo "$uri${QUERY_STRING:+"?"}"
}

# Default index page
function do_help {
filetypes=$(
	ls /usr/share/vim/vim{72,files}/syntax/ /home/andy/.vim/after/syntax/ |
	sed -n 's/.vim$//p' | sort | uniq
)
uploads=$(ls -t db | head -n 5 | sed "s!^!$SCRIPT_URI!")

start_html
cat - <<EOF
<html>
	<head>
		<style>
		* { margin:0; padding:0; }
		body { margin:1em; }
		h4 { margin:1em 0 0 0; }
		p,ul,dl,dd,pre,blockquote { margin:0 0 0 2em; }
		dt { font-weight:bold; padding:0.5em 0 0 0; }
		blockquote { width:50em; font-size:small; }
		</style>
	</head>
	<body>
		<h4>NAME</h4>
		<p>vpaste: Vim enabled pastebin</p>

		<h4>SYNOPSIS</h4>
		<pre> vpaste file [option=value,..]</pre>
		<pre> &lt;command&gt; | vpaste [option=value,..]</pre>
		<br>
		<pre> &lt;command&gt; | curl -F 'x=<-' $SCRIPT_URI[?option=value,..]</pre>

		<h4>DESCRIPTION</h4>
		<p>Add <b>?[option[=value],..]</b> to make your text a rainbow.</p>
		<p>Options specified when uploading are used as defaults.</p>

		<h4>OPTIONS</h4>
		<dl>
		<dt>ft, filetype={filetype}</dt>
		<dd>A filetype to use for highlighting, see FILETYPES</dd>
		<dt>bg, background={light|dark}</dt>
		<dd>Background color to use for the page</dd>
		<dt>et, expandtab</dt>
		<dd>Expand tabs to spaces</dd>
		<dt>ts, tabstop=[N]</dt>
		<dd>Number of spaces to use for tabs when <b>et</b> is set</dd>
		<dt>...</dt>
		<dd>See :help modeline for more information</dd>
		</dl>

		<h4>SOURCE</h4>
		<ul>
		<li><a href="vpaste?ft=sh">vpaste</a>
		<li><a href="index.cgi?ft=sh">index.cgi</a>
		    <a href="vimrc?ft=vim">vimrc</a>
		    <a href="htaccess?ft=apache">htaccess</a>
		<li><a href="2html-et.patch?ft=diff">2html-et.patch</a>
		</ul>

		<h4>LATEST UPLOADS</h4>
		<ul>$(for uri in ${uploads[@]}; do
			echo "<li><a href='$uri'>$uri</a>"
		done)</ul>

		<h4>FILETYPES</h4>
		<blockquote>$filetypes</blockquote>
	</body>
</html>
EOF
}

# Main
pathinfo="${SCRIPT_URL/*vpaste\/}"
boundary="${CONTENT_TYPE/*boundary\=/}"

if [ "$pathinfo" ]; then
	do_print "$pathinfo"
elif [ "$CONTENT_TYPE" ]; then
	do_upload "$boundary"
else
	do_help
fi
