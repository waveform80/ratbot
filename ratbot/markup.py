# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2017 Dave Jones <dave@waveform.org.uk>.
#
# This file is part of ratbot comics.
#
# ratbot comics is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# ratbot comics is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# ratbot comics. If not, see <http://www.gnu.org/licenses/>.

import bleach
import webhelpers2
import webhelpers2.html.builder
import webhelpers2.html.tools

MARKUP_LANGUAGES = {
    'text':    'Plain Text',
    'html':    'HTML',
    }

try:
    import markdown
    MARKUP_LANGUAGES['md'] = 'MarkDown'
except ImportError:
    pass

try:
    import docutils
    import docutils.core
    MARKUP_LANGUAGES['rst'] = 'reStructuredText'
except ImportError:
    pass

try:
    import creole
    import creole.html_emitter
    MARKUP_LANGUAGES['creole'] = 'Creole'
except ImportError:
    pass

try:
    import textile
    MARKUP_LANGUAGES['textile'] = 'Textile'
except ImportError:
    pass

ALLOWED_TAGS = set((
    'a', 'abbr', 'acronym', 'address', 'b', 'big', 'blockquote', 'br',
    'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'dd', 'del', 'dfn',
    'div', 'dl', 'dt', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i',
    'img', 'ins', 'kbd', 'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small',
    'span', 'strike', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot',
    'th', 'thead', 'tr', 'tt', 'u', 'ul', 'var'))

P_ATTRS     = ['align']
Q_ATTRS     = ['cite']
LIST_ATTRS  = ['compact', 'type']
CELLH_ATTRS = ['align', 'char', 'charoff']
CELLV_ATTRS = ['valign']
SIZE_ATTRS  = ['width', 'height']
COL_ATTRS   = CELLH_ATTRS + CELLV_ATTRS + ['span', 'width']
CELL_ATTRS  = CELLH_ATTRS + CELLV_ATTRS + SIZE_ATTRS + [
    'abbr',
    'axis',
    'headers',
    'scope',
    'rowspan',
    'colspan',
    'nowrap',
    'bgcolor',
    ]

ALLOWED_ATTRS = {
    '*'          : ['id', 'class', 'title', 'lang', 'dir'],
    'a'          : ['name', 'href'],
    'blockquote' : Q_ATTRS,
    'caption'    : P_ATTRS,
    'col'        : COL_ATTRS,
    'colgroup'   : COL_ATTRS,
    'del'        : Q_ATTRS + ['datetime'],
    'dl'         : ['compact'],
    'h1'         : P_ATTRS,
    'h2'         : P_ATTRS,
    'h3'         : P_ATTRS,
    'h4'         : P_ATTRS,
    'h5'         : P_ATTRS,
    'h6'         : P_ATTRS,
    'hr'         : ['align', 'noshade', 'size', 'width'],
    'img'        : SIZE_ATTRS + [
        'src',
        'alt',
        'align',
        'hspace',
        'vspace',
        'border',
        ],
    'ins'        : Q_ATTRS + ['datetime'],
    'li'         : ['type', 'value'],
    'ol'         : LIST_ATTRS + ['start'],
    'p'          : P_ATTRS,
    'pre'        : ['width'],
    'q'          : Q_ATTRS,
    'table'      : [
        'summary',
        'width',
        'border',
        'frame',
        'rules',
        'cellspacing',
        'cellpadding',
        'align',
        'bgcolor',
        ],
    'tbody'      : CELLH_ATTRS + CELLV_ATTRS,
    'td'         : CELL_ATTRS,
    'tfoot'      : CELLH_ATTRS + CELLV_ATTRS,
    'th'         : CELL_ATTRS,
    'thead'      : CELLH_ATTRS + CELLV_ATTRS,
    'tr'         : CELLH_ATTRS + CELLV_ATTRS + ['bgcolor'],
    'ul'         : LIST_ATTRS,
}

def render(language, source):
    if language == 'text':
        html = bleach.linkify(
            webhelpers2.html.tools.text_to_html(source))
    elif language == 'html':
        html = source
    elif language == 'md':
        html = markdown.markdown(source)
    elif language == 'textile':
        html = textile.textile(source)
    elif language == 'rst':
        overrides = {
            'input_encoding':       'unicode',
            'doctitle_xform':       False,
            'initial_header_level': 2,
            }
        html = docutils.core.publish_parts(
                source=source, writer_name='html',
                settings_overrides=overrides)['fragment']
    elif language == 'creole':
        html = creole.html_emitter.HtmlEmitter(
                creole.Parser(source).parse()).emit()
    else:
        raise ValueError('Unknown markup language %s' % language)
    # Sanitize all HTML output with bleach (don't rely on safe-mode of
    # converters above as they're not necessarily as good and sometimes
    # disable useful features like embedding HTML in MarkDown)
    return webhelpers2.html.builder.literal(bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS))

