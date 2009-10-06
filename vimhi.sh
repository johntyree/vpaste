#!/bin/bash

# Copyright (C) 2009 Andy Spencer - Public domain

input="$1"
output="$2"
modeline="$3"

# Add the modeline inline to the file then
# remove it after the file is loaded.
ex -u vimrc             \
	"+1d"           \
	"+TOhtml"       \
	"+sav! $output" \
	"+qall!"        \
	<(echo "vim: $modeline"; cat "$input") \
	2>/dev/null 1>&2
