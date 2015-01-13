# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2014 Dave Jones <dave@waveform.org.uk>.
#
# This file is part of ratbot comics.
#
# ratbot comics is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# ratbot comics is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# ratbot comics. If not, see <http://www.gnu.org/licenses/>.

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import os
import hashlib
import logging
from sqlite3 import Connection as SQLite3Connection
log = logging.getLogger(__name__)

from pyramid.response import FileResponse
from pyramid.httpexceptions import HTTPFound, HTTPMovedPermanently
from pyramid.view import view_config
from sqlalchemy import func, text
from velruse.api import login_url

from . import BaseView
from ..forms import Form, FormRendererFoundation
from ..models import (
    DBSession,
    Page,
    Issue,
    Comic,
    User,
    utcnow,
    adjacent,
    )


class FileResponseEtag(FileResponse):
    """
    A derivative of FileResponse which also provides E-tag based caching.
    """
    def __init__(self, path, request=None, cache_max_age=None,
            content_type=None, content_encoding=None):
        super(FileResponseEtag, self).__init__(path, request, cache_max_age,
                content_type, content_encoding)
        s = os.stat(path)
        h = hashlib.md5()
        h.update(path)
        h.update(str(s.st_size))
        h.update(str(s.st_mtime))
        self.etag = h.hexdigest()


class ComicsView(BaseView):
    @view_config(
            route_name='index',
            renderer='../templates/comics/index.pt')
    def index(self):
        latest_query = DBSession.query('comic_id', 'issue_number', 'page_number', 'published').from_statement(
            text(
                "SELECT comic_id, issue_number, page_number, published "
                "FROM front_pages "
                "ORDER BY published DESC "
                "LIMIT 6")
            )
        return {
                'latest': latest_query,
                'login_url': login_url,
                }

    @view_config(route_name='blog_index')
    def blog_index(self):
        return HTTPFound(
            location=self.request.route_url(
                'blog_issue',
                comic=self.request.matchdict['comic'],
                issue=DBSession.query(func.max(Issue.issue_number)).\
                    filter(Issue.comic_id == self.request.matchdict['comic']).scalar()
                    ))

    @view_config(
            route_name='blog_issue',
            renderer='../templates/comics/blog.pt')
    def blog_issue(self):
        return {}

    @view_config(
            route_name='bio',
            renderer='../templates/comics/bio.pt')
    def bio(self):
        return {
            'authors': DBSession.query(User).\
                    join(Comic).\
                    distinct().\
                    order_by(User.name),
            }

    @view_config(
            route_name='comics',
            renderer='../templates/comics/comics.pt')
    def comics(self):
        return {
            'comics': DBSession.query(Comic).\
                    filter(Comic.comic_id != 'blog').\
                    order_by(Comic.title),
            }

    @view_config(
            route_name='issues',
            renderer='../templates/comics/issues.pt')
    def issues(self):
        return {}

    @view_config(
            route_name='issue',
            renderer='../templates/comics/page.pt')
    def issue(self):
        # XXX Redirect to page
        self.context.page = self.context.issue.first_page
        return self.page()

    @view_config(route_name='issue_archive')
    def issue_archive(self):
        self.context.issue.create_archive()
        return FileResponseEtag(self.context.issue.archive_filename, request=self.request)

    @view_config(route_name='issue_pdf')
    def issue_pdf(self):
        self.context.issue.create_pdf()
        return FileResponseEtag(self.context.issue.pdf_filename, request=self.request)

    @view_config(
            route_name='page',
            renderer='../templates/comics/page.pt')
    def page(self):
        return {}

    @view_config(route_name='page_thumb')
    def page_thumb(self):
        self.context.page.create_thumbnail()
        return FileResponseEtag(self.context.page.thumbnail_filename, request=self.request)

    @view_config(route_name='page_bitmap')
    def page_bitmap(self):
        self.context.page.create_bitmap()
        return FileResponseEtag(self.context.page.bitmap_filename, request=self.request)

    @view_config(route_name='page_vector')
    def page_vector(self):
        return FileResponseEtag(self.context.page.vector_filename, request=self.request)

    # Compatibility views
    @view_config(route_name='compat_index')
    def compat_index(self):
        return HTTPMovedPermanently(location=self.request.route_url('comics'))

    @view_config(route_name='compat_view')
    def compat_view(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'page',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            page=self.request.matchdict['page'],
            ))

    @view_config(route_name='compat_thumb')
    def compat_thumb(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'page_thumb',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            page=self.request.matchdict['page'],
            ))

    @view_config(route_name='compat_png')
    def compat_png(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'page_bitmap',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            page=self.request.matchdict['page'],
            ))

    @view_config(route_name='compat_svg')
    def compat_svg(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'page_vector',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            page=self.request.matchdict['page'],
            ))

    @view_config(route_name='compat_pdf')
    def compat_pdf(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'issue_pdf',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            ))

    @view_config(route_name='compat_archive')
    def compat_archive(self):
        return HTTPMovedPermanently(location=self.request.route_url(
            'issue_archive',
            comic=self.request.matchdict['comic'],
            issue=self.request.matchdict['issue'],
            ))


def routes():
    return (
            ('index',           r'/'),
            ('bio',             r'/bio.html'),
            ('blog_index',      r'/{comic:blog}/index.html'),
            ('blog_issue',      r'/{comic:blog}/{issue:\d+}.html'),
            ('links',           r'/links.html'),
            ('comics',          r'/comics.html'),
            ('issues',          r'/comics/{comic}.html'),
            ('issue',           r'/comics/{comic}/{issue:\d+}.html'),
            ('issue_archive',   r'/comics/{comic}-{issue:\d+}.zip'),
            ('issue_pdf',       r'/comics/{comic}-{issue:\d+}.pdf'),
            ('page',            r'/comics/{comic}/{issue:\d+}/{page:\d+}.html'),
            ('page_bitmap',     r'/comics/images/{comic}/{issue:\d+}/{page:\d+}.png'),
            ('page_vector',     r'/comics/images/{comic}/{issue:\d+}/{page:\d+}.svg'),
            ('page_thumb',      r'/comics/thumbs/{comic}/{issue:\d+}/{page:\d+}.png'),
            # Compatibility routes
            ('compat_index',    r'/comics'),
            ('compat_view',     r'/comics/view/{comic}/{issue:\d+}/{page:\d+}'),
            ('compat_thumb',    r'/comics/thumb/{comic}/{issue:\d+}/{page:\d}'),
            ('compat_png',      r'/comics/png/{comic}/{issue:\d+}/{page:\d}'),
            ('compat_svg',      r'/comics/svg/{comic}/{issue:\d+}/{page:\d}'),
            ('compat_pdf',      r'/comics/pdf/{comic}/{issue:\d+}'),
            ('compat_archive',  r'/comics/archive/{comic}/{issue:\d+}'),
            )
