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

import logging
log = logging.getLogger(__name__)

from pyramid.response import Response, FileResponse
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from sqlalchemy import func
from velruse.api import login_url

from ratbot.forms import Form, FormRendererFoundation
from ratbot.views import BaseView
from ratbot.models import (
    DBSession,
    Page,
    Issue,
    Comic,
    User,
    utcnow,
    )


class ComicsView(BaseView):
    @view_config(
            route_name='index',
            renderer='../templates/comics/index.pt')
    def index(self):
        sub = DBSession.query(
                Page.comic_id,
                Page.issue_number,
                func.max(Page.published).label('published'),
            ).filter(
                (Page.published != None) &
                (Page.published <= self.utcnow)
            ).group_by(
                Page.comic_id,
                Page.issue_number,
            ).subquery()
        latest_query = DBSession.query(
                sub.c.comic_id,
                sub.c.issue_number,
                func.min(Page.number).label('number'),
            ).join(
                Page,
                (Page.comic_id == sub.c.comic_id) &
                (Page.issue_number == sub.c.issue_number)
            ).group_by(
                sub.c.comic_id,
                sub.c.issue_number,
            ).order_by(sub.c.published.desc())
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
                issue=DBSession.query(func.max(Issue.number)).\
                    filter(Issue.comic_id == self.request.matchdict['comic']).scalar()
                    ))

    @view_config(
            route_name='blog_issue',
            renderer='../templates/comics/blog.pt')
    def blog_issue(self):
        pages = self.context.issue.published_pages.order_by(Page.number.desc())
        issues = self.context.issue.comic.published_issues.order_by(Issue.number.desc())
        return {
                'pages':  pages,
                'issues': issues,
                }

    @view_config(
            route_name='bio',
            renderer='../templates/comics/bio.pt')
    def bio(self):
        return {
                'authors': DBSession.query(User).join(Comic).distinct().order_by(User.name),
                }

    @view_config(
            route_name='comics',
            renderer='../templates/comics/comics.pt')
    def comics(self):
        latest_page = DBSession.query(
                Page.comic_id,
                func.max(Page.published).label('published'),
            ).filter(
                (Page.published != None) &
                (Page.published <= self.utcnow)
            ).group_by(
                Page.comic_id,
            ).subquery()
        latest_issue = DBSession.query(
                Page.comic_id,
                func.max(Page.issue_number).label('number'),
            ).join(
                latest_page,
                (Page.comic_id == latest_page.c.comic_id) &
                (Page.published == latest_page.c.published)
            ).group_by(
                Page.comic_id,
            ).subquery()
        comics_query = DBSession.query(
                Comic,
                latest_issue.c.number.label('issue_number'),
                func.min(Page.number).label('number'),
            ).outerjoin(
                latest_issue,
                (Comic.id == latest_issue.c.comic_id)
            ).outerjoin(
                Page,
                (Page.comic_id == latest_issue.c.comic_id) &
                (Page.issue_number == latest_issue.c.number) &
                (Page.published != None) &
                (Page.published <= self.utcnow)
            ).filter(
                (Comic.id != 'blog')
            ).group_by(Comic, latest_issue.c.number).order_by(Comic.title)
        return {
                'comics': comics_query,
                }

    @view_config(
            route_name='issues',
            renderer='../templates/comics/issues.pt')
    def issues(self):
        issues_query = DBSession.query(
                Issue,
                func.min(Page.number),
                func.max(Page.published),
            ).outerjoin(Page).filter(
                (Issue.comic_id == self.context.comic.id)
            ).group_by(Issue).order_by(Issue.number.desc())
        return {
                'issues': issues_query,
                }

    @view_config(
            route_name='issue',
            renderer='../templates/comics/page.pt')
    def issue(self):
        self.context.page = self.context.issue.first_page
        return {
                'page_count': self.context.issue.published_pages.count(),
                }

    @view_config(route_name='issue_archive')
    def issue_archive(self):
        self.context.issue.create_archive()
        return FileResponse(self.context.issue.archive_filename)

    @view_config(route_name='issue_pdf')
    def issue_pdf(self):
        self.context.issue.create_pdf()
        return FileResponse(self.context.issue.pdf_filename)

    @view_config(
            route_name='page',
            renderer='../templates/comics/page.pt')
    def page(self):
        return {
                'page_count': self.context.issue.published_pages.count(),
                }

    @view_config(route_name='page_thumb')
    def page_thumb(self):
        self.context.page.create_thumbnail()
        return FileResponse(self.context.page.thumbnail_filename)

    @view_config(route_name='page_bitmap')
    def page_bitmap(self):
        self.context.page.create_bitmap()
        return FileResponse(self.context.page.bitmap_filename)

    @view_config(route_name='page_vector')
    def page_vector(self):
        return FileResponse(self.context.page.vector_filename)


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
            )
