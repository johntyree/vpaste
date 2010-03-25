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

# Remove url codings from stdin
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
	awk -v "bnd=$1" '{
		if ($0 == "--"bnd"\r")     { st=1;     }
		if ($0 == "--"bnd"--\r")   { st=0;     }
		if (st == 2)               { print $0; }
		if ($0 == "\r" && st == 1) { st=2;     }
	}' | head -c -2 | head -c $((128*1024))
	# Remove trailing ^M's that come with CGI
	# Limit size to 128K
}

# Print out a generic header
function header {
	echo "Content-Type: $1; charset=UTF-8"
	echo
}

# Format a file for viewing 
function do_print {
	if [ -f "./$1" ]; then
		input="$1"
	elif [ -f "db/$1" ]; then
		input="db/$1"
		trim='1,/^$/d' # sed command to remove cruft
	else
		echo "Status: 404 Not Found"
		header text/plain
		echo "File '$1' not found"
		return
	fi


	if [[ "$REQUEST_URI" == *'?'* ]]; then
		# Create a temp file with the provided modeline
		output="$(mktemp)"
		tmp="$(mktemp)"
		sed "1a$(get_modeline)" "$input" > "$tmp"

		# - I have some plugins in ~/.vim
		# - Run ex in a pty to trick it into thinking that it
		#   has a real terminal, note that we also have to set
		#   term=xterm-256color in vimrc
		HOME=/home/andy \
		/home/andy/bin/pty ex -nXZ -i NONE -u vimrc \
			'+set bexpr= fde= fdt= fex= inde= inex= key= pa= pexpr' \
			'+set iconstring= ruf= stl= tal=' \
			"+set titlestring=$1\ -\ vpaste.net" \
			'+set noml'     \
			'+2d|'$trim     \
			'+%s/\r//g'     \
			'+TOhtml'       \
			"+sav! $output" \
			'+qall!'        \
			"$tmp" </dev/null >/dev/null 2>&1

		header text/html
		cat "$output" 
		rm "$tmp" "$output"
	else
		header text/plain
		sed "$trim" "$input"
	fi
}


# Upload handler
function do_upload {
	text=$(cut_file "$1")
	if [ -z "$text" ]; then
		header text/plain
		echo "No text pasted"
		exit
	fi
	output="$(mktemp db/XXXXX)"
	uri="$url$(basename "$output")${QUERY_STRING:+"?"}"
	(get_modeline
	 echo "Date: $(date -R)"
	 echo "From: $REMOTE_ADDR"
	 echo
	 echo "$text") > "$output"
	echo "Status: 302 Found"
	echo "Location: $uri"
	header text/plain
	echo "$uri"
}

# Default index page
function do_help {
filetypes=$(
	ls /usr/share/vim/vim*/syntax/ /home/andy/.vim/syntax/ |
	sed -n '/^\(syntax\|manual\|synload\|2html\|colortest\|hitest\).vim$/d; s/.vim$//p' |
	sort | uniq
)
uploads=$(ls -t db | head -n 5)

header text/html
cat - <<EOF
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
	<head>
		<title>vpaste.net - Vim based pastebin</title>
		<meta http-equiv="Content-type" content="text/html;charset=UTF-8" />
		<meta name="description" content="vpaste: Vim based pastebin" />
		<meta name="keywords" content="vpaste,paste,pastebin,vim" />
		<style type="text/css">
			* { margin:0; padding:0; }
			body { margin:1em; }
			h4 { margin:1em 0 0 0; }
			blockquote,dd,dl,p,pre,ul { margin:0 0 0 2em; }
			dt { font-weight:bold; padding:0.5em 0 0 0; }
			blockquote { width:50em; font-size:small; }
			span { font-family:monospace; }
		</style>
	</head>
	<body>
		<form id="form" method="post" action="?" enctype="multipart/form-data">
		<div style="margin:0 0 1.5em 0;">
		<textarea name="text" cols="80" rows="25" style="width:100%; height:20em;"></textarea>
		<select onchange="document.getElementById('form').action =
			document.location + '?ft=' + this.value;">
		<option value="" selected="selected" disabled="disabled">Filetype</option>
		<option value="">None</option>
		$(for ft in $filetypes; do
			echo "<option>$ft</option>"
		done)
		</select>
		<input type="submit" value="Paste" />
		</div>
		</form>

		<h4>NAME</h4>
		<p>vpaste: Vim based pastebin</p>

		<h4>SYNOPSIS</h4>
		<div>
		<pre> vpaste file [option=value,..]</pre>
		<pre> &lt;command&gt; | vpaste [option=value,..]</pre>
		<br />
		<pre> &lt;command&gt; | curl -F 'x=&lt;-' $url[?option=value,..]</pre>
		<br />
		<pre> :map vp :exec "w !vpaste ft=".&amp;ft&lt;CR&gt;</pre>
		<pre> :vmap vp &lt;ESC&gt;:exec "'&lt;,'&gt;w !vpaste ft=".&amp;ft&lt;CR&gt;</pre>
		</div>

		<h4>DESCRIPTION</h4>
		<p>Add <b>?[option[=value],..]</b> to make your text a rainbow.</p>
		<p>Options specified when uploading are used as defaults.</p>

		<h4>OPTIONS</h4>
		<dl>
		<dt>ft, filetype={filetype}</dt>
		<dd>A filetype to use for highlighting, see above menu for supported types</dd>
		<dt>bg, background={light|dark}</dt>
		<dd>Background color to use for the page</dd>
		<dt>et, expandtab</dt>
		<dd>Expand tabs to spaces</dd>
		<dt>ts, tabstop=[N]</dt>
		<dd>Number of spaces to use for tabs when <b>et</b> is set</dd>
		<dt>...</dt>
		<dd>See :help modeline for more information</dd>
		</dl>

		<h4>BUGS</h4>
		<ul>
		<li>Using strange filetypes (ft=2html) may result in strange output.</li>
		<li><a href="mailto:andy753421@gmail.com?subject=vpaste bug">Other?</a></li>
		</ul>

		<h4>SOURCE</h4>
		<ul>
		<li><a href="vpaste?ft=sh">vpaste</a></li>
		<li><a href="index.cgi?ft=sh">index.cgi</a>
		    <a href="vimrc?ft=vim">vimrc</a>
		    <a href="htaccess?ft=apache">htaccess</a>
		    <a href="robots.txt?ft=robots">robots.txt</a>
		    <a href="sitemap.xml?ft=xml">sitemap.xml</a></li>
		<li><a href="2html.patch?ft=diff">2html.patch</a></li>
		<li><a href="https://lug.rose-hulman.edu/svn/misc/trunk/htdocs/vpaste/">Subversion</a></li>
		</ul>

		<h4>LATEST UPLOADS</h4>
		<ul>$(for upload in ${uploads[@]}; do
			echo -n "<li>"
			echo -n "<span>$upload</span> "
			echo -n "<a href='$upload'>text</a> "
			echo -n "<a href='$upload?'>rainbow</a>"
			echo "</li>"
		done)</ul>
	</body>
</html>
EOF
}

# Main
url="http://$HTTP_HOST${REQUEST_URI/\?*}"
pathinfo="${REQUEST_URI/*\/}"
pathinfo="${pathinfo/\?*}"

if [ "$pathinfo" ]; then
	do_print "$pathinfo"
elif [ "$CONTENT_TYPE" ]; then
	do_upload "${CONTENT_TYPE/*boundary\=/}"
else
	do_help
fi
