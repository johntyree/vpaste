// Copyright (C) 2013 Andy Spencer
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or (at your option) any
// later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
// details.

/* Constants */
var vpaste = 'http://vpaste.net/';

var light  = '#f4f4f4';
var dark   = '#111133';
var border = '#8888dd';

var styles = [
	'background: ' + light + ';',
	'border: solid 1px ' + border + ';',
	'padding: 0.5em;',
	'overflow: auto;',
	'display: block;',
	'white-space: pre;',
	'text-align: left;',
];

/* Globals */
var query;

/* Update Style Sheet */ 
function update_styles(style, name) {
	var text  = style.innerHTML;
	var lines = text.split(/\n/);
	for (var i = 0; i < lines.length; i++) {
		var line = lines[i];
		line = line.replace(/#ffffff/, light);
		line = line.replace(/#000000/, dark);
		if (line.match(/^pre/))
			line = line.replace(/^pre/, '.'+name);
		else if (line.match(/^\./))
			line = '.'+name+' '+line;
		else
			line = '';
		lines[i] = line;
	}
	style.innerHTML = lines.join('\n');
}

/* Embed paste into page  */
function embed_paste(ajax, style, html, name) {
	if (ajax.readyState != 4 && ajax.readyState != 'complete')
		return;
	if (!ajax.responseXML)
		throw new Error('No response XML: ' + ajax.responseText);
	var xml    = ajax.responseXML;
	var vstyle = xml.getElementsByTagName('style')[0];
	var vhtml  = xml.getElementsByTagName('pre')[0];
	update_styles(vstyle, name);
	style.innerHTML += vstyle.innerHTML;
	html.innerHTML   = vhtml.innerHTML.replace(/^\n*/, '');
	html.style.visibility = 'visible';
}

/* Strip whitespace from a paste */
function strip_spaces(text) {
	var prefix = null;
	var lines  = text.replace(/^\s*\n|\n\s*$/g,'').split('\n');
	for (i in lines) {
		if (lines[i].match(/^\s*$/))
			continue;
		var white = lines[i].replace(/\S.*/, '')
		if (prefix === null || white.length < prefix.length)
			prefix = white;
	}
	for (i in lines)
		lines[i] = lines[i].replace(prefix, '');
	return lines.join('\n');
}

/* Start embedding a paste */
function query_paste(method, url, body, html, name) {
	/* Add style tag box */
	var style = document.createElement('style');
	style.type      = "text/css";
	style.innerHTML = '.' + name + ' { ' + styles.join(' ') + ' }';
	document.head.insertBefore(style, document.head.firstChild);

	/* Get AJAX object */
	var ajax = null;
	if (!ajax) ajax = new XMLHttpRequest();
	if (!ajax) ajax = new ActiveXObject('Microsoft.XMLHTTP');
	if (!ajax) throw new Error('Cannot get AJAX object');

	/* Insert default query */
	if (query)
		url = url.replace(/[?]/, '?' + query + ',');

	/* Run AJAX Request */
	ajax.onreadystatechange = function() {
		embed_paste(ajax, style, html, name) };
	ajax.open(method, url, true);
	ajax.setRequestHeader('Accept', 'text/html');
	ajax.overrideMimeType('application/xhtml+xml');
	ajax.send(body);
}

/* Start embedding a paste */
function start_embed() {
	/* Get current paste information */
	var scripts = document.getElementsByTagName('script');
	var script  = scripts[scripts.length-1];
	var text    = strip_spaces(script.textContent);
	var name    = 'vpaste_s' + scripts.length;
	var regex   = /^[^?]*[?]?(([a-zA-Z0-9.]*)[?&, ]?(.*))$/;
	var parts   = script.src.match(regex);

	/* Handle header tags */
	if (!text && !parts[2] || !document.body)
		return query = parts[1];

	/* Add paste box */
	var html = document.createElement('pre');
	html.innerHTML = 'Loading..';
	html.className = script.className + ' vpaste ' + name;
	script.parentNode.appendChild(html);

	/* Query the paste */
	if (text)
		query_paste('POST', vpaste+'view?'+parts[1],
			text, html, name);
	else
		query_paste('GET', vpaste+parts[2]+'?'+parts[3],
			null, html, name);
}

/* Convert all code tags to pastes */
function format_code(tagName, className) {
	if (!tagName)
		tagName = 'code';
	var tags = document.getElementsByTagName(tagName);
	for (var i = 0; i < tags.length; i++) {
		var tag = tags[i];
		if (className && tag.className != className)
			continue;
		var name  = 'vpaste_c' + i;
		var text  = strip_spaces(tag.textContent);
		var query = tag.getAttribute('title');
		tag.className     += ' ' + name;
		query_paste('POST', vpaste+'view?'+query,
				text, tag, name);
	}
}

start_embed();
