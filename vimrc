" Andy Spencer 2009-2013 - Public domain

filetype plugin indent on
syntax on

" Defaults
set nocompatible
set encoding=utf-8
set fileencoding=utf-8
set term=xterm-256color
set modelines=10
set background=light

" Xterm settings
let g:xterm_trim_escapes  = 1
let g:xterm_start_pattern = "^$"

" TOhtml settings
let g:html_use_css        = 1
let g:html_use_encoding   = "UTF-8"
let g:html_no_progress    = 1
let g:html_dynamic_folds  = 1
let g:html_use_xhtml      = 1

" Misc
let g:is_bash             = 1

" Override these with modelines
set nowrap noexpandtab
au BufWinEnter * let g:html_expand_tabs = &expandtab
au BufWinEnter * let g:html_pre_wrap    = &wrap
