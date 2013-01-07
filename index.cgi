#!/bin/bash

# Copyright (C) 2009-2013 Andy Spencer
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.

# Remove url codings from stdin
function get_modeline {
	echo "$QUERY_STRING" |
	sed -e 's/%\([0-9A-F][0-9A-F]\)/\\\\\x\1/g; s/[,&?]/ /g' |
	xargs echo -e
}
function get_param {
	get_modeline | awk -v "key=$1" 'BEGIN{RS=" "; FS="="}; $1 ~ key {print $2}'
}

# Extract an uploaded file from standard input
#   $1 is the name of the input to extract
function cut_file {
	bnd="${CONTENT_TYPE/*boundary\=/}"
	awk -v "want=$1" -v "bnd=$bnd" '
		BEGIN { RS="\r\n" }

		# reset based on boundaries
		$0 == "--"bnd""     { st=1; next; }
		$0 == "--"bnd"--"   { st=0; next; }
		$0 == "--"bnd"--\r" { st=0; next; }

		# search for wanted file
		st == 1 && $0 ~  "^Content-Disposition:.* name=\""want"\"" { st=2; next; }
		st == 1 && $0 == "" { st=9; next; }

		# wait for newline, then start printing
		st == 2 && $0 == "" { st=3; next; }
		st == 3             { print $0    }
	' | head -c $((128*1024)) # Limit size to 128K
}

# Respond to a request
function respond {
	local allow ctype heads files texts gzip h f
	while [ "$1" ]; do
		case $1 in
			-y) allow="true"; ;;
			-c) ctype="$2"; shift ;;
			-h) heads=("${heads[@]}" "$2"); shift ;;
			-f) files=("${files[@]}" "$2"); shift ;;
		        *)  texts=("${texts[@]}" "$1"); ;;
		esac
		shift
	done

	# Check if the browser supports gzip
	if [[ "$HTTP_ACCEPT_ENCODING" == *'gzip'* ]]; then
		gzip=true
	fi

	# Output header
	if [ "$ctype" ]; then
		echo "Content-Type: $ctype; charset=UTF-8"
	else
		echo "Content-Type: text/plain; charset=UTF-8"
	fi
	if [ "$gzip" ]; then
		echo "Content-Encoding: gzip"
	fi
	if [ "$allow" ]; then
		echo "Access-Control-Allow-Origin: *"
		echo "Access-Control-Allow-Headers: Content-Type"
	fi
	for h in "${heads[@]}"; do
		echo "$h"
	done
	echo

	# Output text messages
	if [ "$texts" ]; then
		if [ "$gzip" ]; then
			echo "${texts[@]}" | gzip
		else
			echo "${texts[@]}"
		fi
		exit
	fi

	# Output body files
	if [ "$files" ]; then
		for f in "${files[@]}"; do
			if   [[   "$gzip" && "$f" != *'.gz' ]]; then
				gzip < "$f"
			elif [[ ! "$gzip" && "$f" == *'.gz' ]]; then
				zcat < "$f"
			else
				cat "$f"
			fi
		done
		exit
	fi

	# Gzip remaining stream
	if [ "$gzip" ]; then
		exec 1> >(gzip)
	fi
}

# Format and output a file
function format {
	# Create a temp file with the provided modeline
	tmp="$(mktemp)"
	sed "\$avim: $(get_modeline)" "$1" > "$tmp"

	# Determine cache name
	md5="$(cat index.cgi vimrc "$tmp" /usr/bin/ex | md5sum -b)"
	out="cache/${md5% *}.htm"
	zip="$out.gz"

	# Cache the file, if needed
	if [ ! -f "$zip" ]; then
		# - I have some plugins in ~/.vim
		# - Run ex in pty to trick it into thinking that it
		#   has a real terminal, note that we also have to set
		#   term=xterm-256color in vimrc
		HOME=/home/andy \
		/home/vpaste/bin/pty \
		/usr/bin/ex -nXZ -i NONE -u vimrc \
			'+sil! set fde= fdt= fex= inde= inex= key= pa= pexpr=' \
			'+sil! set iconstring= ruf= stl= tal=' \
			"+sil! set titlestring=$1\ -\ vpaste.net" \
			'+sil! set noml' \
			'+sil! $d|'$2    \
			'+sil! %s/\r//g' \
			'+sil! TOhtml'   \
			"+sav! $out"     \
			'+qall!'         \
			"$tmp" >/dev/null 2>&1
		gzip "$out"
	fi
	rm "$tmp"

	# Output the file
	respond -y -c "text/html" -f "$zip"
}

# List previous pastes
function do_cmd {
	respond
	case "$1" in
	ls)
		ls -t db | column
		;;
	head)
		awk -v 'rows=4' -v 'cols=60' '
			FNR==1      { gsub(/.*\//, "", FILENAME);
			              print FILENAME
			              print "-----" }
			FNR==1,/^$/ { next }
			/\S/        { i++; printf "%."cols"s\n", $0 }
			i>=rows     { nextfile  }
			ENDFILE     { i=0; print ""  }
		' $(ls -t db/*)
		;;
	stat)
		ls -l --time-style='+%Y %m' db |
		awk -v 'hdr=Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec' '
			BEGIN { printf "%64s\n", hdr }
			NR>1  { cnt[$6+0][$7+0]++ }
			END   { for (y in cnt) {
			          printf "%4d", y
			          for (m=1; m<=12; m++)
			            printf "%5s", cnt[y][m]
			          printf "\n" } }'
		;;
	esac
}

# Format a file for viewing
function do_print {
	if [ -f "./$1" ]; then
		input="$1"
	elif [ -f "db/$1" ]; then
		input="db/$1"
		trim='1,/^$/d' # sed command to remove cruft
	else
		respond -h 'Status: 404 Not Found' \
		        "File '$1' not found"
	fi

	# Check for javascript
	if [[ "$input" == 'embed.js' &&
	      "$HTTP_ACCEPT" != *'html'* ]]; then
		respond -c text/javascript -f "$input"
	fi

	# Check for raw paste
	if [[ "$QUERY_STRING" == 'raw'* ||
	      "$REQUEST_URI"  != *'?'* &&
	      ( "$input"       != 'db/'* ||
	        "$HTTP_ACCEPT" != *'html'* ) ]]; then
		respond
		sed "$trim" "$input"
		exit
	fi

	# Output the file
	format "$input" "$trim"
}

# Format a file for viewing
function do_view {
	format -
}

# Upload handler
function do_upload {
	body=$(cat -)
	spam=$(echo -n "$body" | cut_file "ignoreme")
	text=$(echo -n "$body" | cut_file "(text|x)")
	bans=$(echo -n "$REMOTE_ADDR" | grep -f blacklist)
	[ ! -z "$spam" ] && respond "Spam check.."
	[ ! -z "$bans" ] && respond "You have been banned"
	[   -z "$text" ] && respond "No text pasted"

	# Format and save message
	output="$(mktemp db/XXXXX)"
	cat >"$output" <<-EOF
		vim: $(get_modeline)
		Date: $(date -R)
		From: $REMOTE_ADDR
		User-Agent: $HTTP_USER_AGENT

		$text
	EOF

	# Redirect user
	uri="$url$(basename "$output")"
	respond -h 'Status: 302 Found' \
	        -h "Location: $uri"    \
	        "$uri"
}

# Default index page
function do_help {
	filetypes=$(
		ls /usr/share/vim/vim*/syntax/ /home/andy/.vim/syntax/ |
		sed -n '/^\(syntax\|manual\|synload\|2html\|colortest\|hitest\).vim$/d; s/.vim$//p' |
		sort | uniq
	)
	uploads=$(ls -t db 2>/dev/null | head -n 5)
	filetype=$(get_param '^(ft|filet(y(pe?)?)?)$')
	vpaste='<a href="vpaste?ft=sh">vpaste</a>'
	repo='https://lug.rose-hulman.edu/svn/misc/trunk/htdocs/vpaste/'

	respond -c text/html
	cat <<-EOF
	<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
	  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
	<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
		<head>
			<title>vpaste.net - Vim based pastebin</title>
			<meta http-equiv="Content-type" content="text/html;charset=UTF-8" />
			<meta name="description" content="vpaste: Vim based pastebin" />
			<meta name="keywords" content="vpaste,paste,pastebin,vim" />
			<meta name="google-site-verification" content="OvHF73zD7osJ1VSq9rJxnMFlja36944ud6CiP_iXQnI" />
			<style type="text/css">
				*          { margin: 0;
				             padding: 0; }
				body       { margin: 4em 8em 4em 8em;
				             font-family: sans-serif; }
				input      { padding: 2px 6px 3px 6px; }
				/* Items */
				textarea   { width: 100%;
				             margin-bottom: 0.5em; }
				.buttons   { float: left; }
				.links     { float: right; }
				.links *   { text-decoration: none;
				             margin-left: 0.5em; }
				.box       { display: none;
				             clear: both;
				             margin-top: 2.7em;
				             border-top: solid 1px #888; }
				/* box contents */
				h1         { margin-top: 1.0em;
				             font-size: larger; }
				ul,dd,dl,p { margin: 0 0 0 2em; }
				dt         { font-weight: bold;
				             padding: 0.5em 0 0 0; }
				span       { font-family: monospace; }
				.cmds dd   { font-family: monospace; }
			</style>
			<script type="text/javascript">
				//<![CDATA[
				function show(id) {
					var boxes = document.getElementsByClassName('box')
					for (var i = 0; i < boxes.length; i++) {
						var box = boxes[i]
						if (box.id == id && box.style.display != 'block')
							box.style.display = 'block'
						else
							box.style.display = "none"
					}
				}
				function autoshow() {
					var id  = document.location.toString().replace(/.*#/, '')
					var box = document.getElementById(id)
					if (box) box.style.display = "block"
				}
				//]]>
			</script>
		</head>

		<body onload="autoshow()">
			<form id="form" method="post" action="" enctype="multipart/form-data">
				<div>
					<input style="display:none" type="text" name="ignoreme" value="" />
					<textarea name="text" cols="80" rows="25"></textarea>
				</div>
				<div class="buttons">
					<select onchange="document.getElementById('form').action =
							  document.location + '?ft=' + this.value;">
						<option value="" disabled="disabled">Filetype</option>
						<option value="">None</option>
						$(for ft in $filetypes; do
							echo "<option$(
							[ "$ft" = "$filetype" ] &&
								echo ' selected="selected"'
							)>$ft</option>"
						done)
					</select>
					<input type="submit" value="Paste" />
				</div>
				<div class="links">
					<a href="">vpaste</a> <span>-</span>
					<a href="#usage"   onclick="show('usage'  )">Usage</a>
					<a href="#devel"   onclick="show('devel'  )">Development</a>
					<a href="#uploads" onclick="show('uploads')">Uploads</a>
				</div>
			</form>

			<div class="box" id="usage">
				<h1>Pasting</h1>
				<dl class="cmds">
					<dt>From a shell</dt>
					<dd> $vpaste file [option=value,..]</dd>
					<dd> &lt;command&gt; | $vpaste [option=value,..]</dd>

					<dt>From Vim</dt>
					<dd> :map vp :exec "w !vpaste ft=".&amp;ft&lt;CR&gt;</dd>
					<dd> :vmap vp &lt;ESC&gt;:exec "'&lt;,'&gt;w !vpaste ft=".&amp;ft&lt;CR&gt;</dd>

					<dt>With curl</dt>
					<dd> &lt;command&gt; | curl -F 'text=&lt;-' $url[?option=value,..]</dd>
				</dl>

				<h1>Options</h1>
				<p>Add <b>?option[=value],..</b> to make your text a rainbow.</p>
				<p>Options specified when uploading are saved as defaults.</p>

				<dl>
					<dt>bg, background={light|dark}</dt>
					<dd>Background color to use for the page</dd>
					<dt>et, expandtab</dt>
					<dd>Expand tabs to spaces</dd>
					<dt>fdm, foldmethod=(syntax|indent)</dt>
					<dd>Turn on dynamic code folding</dd>
					<dt>ft, filetype={filetype}</dt>
					<dd>A filetype to use for highlighting, see above menu for supported types</dd>
					<dt>nu, number</dt>
					<dd>Add line numbers</dd>
					<dt>ts, tabstop=[N]</dt>
					<dd>Number of spaces to use for tabs when <b>et</b> is set</dd>
					<dt>...</dt>
					<dd>See :help modeline for more information</dd>
				</dl>
			</div>

			<div class="box" id="devel">
				<h1>License</h1>
				<p>Copyright © 2009-2013
				   Andy Spencer &lt;andy753421@gmail.com&gt;</p>
				<p>See individual files for licenses</p>

				<h1>Source code</h1>
				<dl>
					<dt>Client</dt>
					<dd><a href="vpaste?ft=sh">vpaste</a>
					    <a href="embed.js?ft=javascript">embed.js</a></dd>
					<dt>Server</dt>
					<dd><a href="index.cgi?ft=sh">index.cgi</a>
					    <a href="vimrc?ft=vim">vimrc</a>
					    <a href="htaccess?ft=apache">htaccess</a>
					    <a href="robots.txt?ft=robots">robots.txt</a>
					    <a href="sitemap.xml?ft=xml">sitemap.xml</a>
					    <a href="blacklist?raw">blacklist</a></dd>
					<dt>Patches</dt>
					<dd><a href="2html.patch?ft=diff">2html.patch</a></dd>
					<dt>Subversion</dt>
					<dd><a href="$repo">$repo</a></dd>
				</dl>

				<h1>Bugs</h1>
				<ul>
					<li>Using strange filetypes (ft=2html) may result in strange output.</li>
					<li><a href="mailto:andy753421@gmail.com?subject=vpaste bug">Other?</a></li>
				</ul>
			</div>

			<div class="box" id="uploads">
				<h1>Recent Uploads</h1>
				<ul>$(for upload in ${uploads[@]}; do
				    echo -n "<li>"
				    echo -n "<span>$upload</span> "
				    echo -n "<a href='$upload?raw'>text</a> "
				    echo -n "<a href='$upload'>rainbow</a>"
				    echo "</li>"
				done)
				</ul>
				<p><a href="ls">list all</a></p>
				<p><a href="head">sample all</a></p>
				<p><a href="stat">statistics</a></p>
			</div>
		</body>
	</html>
	EOF
}

# Main
PATH=/bin:/usr/bin
url="http://$HTTP_HOST${REQUEST_URI/\?*}"
pathinfo="${REQUEST_URI/*\/}"
pathinfo="${pathinfo/\?*}"

if [ "$pathinfo" = ls ]; then
	do_cmd ls
elif [ "$pathinfo" = head ]; then
	do_cmd head
elif [ "$pathinfo" = stat ]; then
	do_cmd stat
elif [ "$pathinfo" = view ]; then
	do_view
elif [ "$pathinfo" ]; then
	do_print "$pathinfo"
elif [ "$CONTENT_TYPE" ]; then
	do_upload
else
	do_help
fi
