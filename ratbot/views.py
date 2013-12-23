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

import pytz
from pyramid.decorator import reify
from pyramid.renderers import get_renderer
from pyramid.response import Response, FileResponse
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from sqlalchemy.orm import aliased

from ratbot.models import (
    DBSession,
    Page,
    Issue,
    Comic,
    utcnow,
    )


class BaseView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def layout(self):
        renderer = get_renderer('templates/layout.pt')
        return renderer.implementation().macros['layout']

    @reify
    def nav_bar(self):
        renderer = get_renderer('templates/nav_bar.pt')
        return renderer.implementation().macros['nav-bar']

    @reify
    def site_title(self):
        return self.request.registry.settings['site.title']


class ComicsView(BaseView):
    @view_config(
            route_name='index',
            renderer='templates/index.pt')
    def index(self):
        first_page = aliased(Page)
        all_pages = aliased(Page)
        latest_issues = DBSession.query(Issue).join(all_pages).join(first_page).filter(
                (first_page.published != None) &
                (first_page.published <= utcnow()) &
                (first_page.number == 1) &
                (all_pages.published != None) &
                (all_pages.published <= utcnow())
                ).order_by(all_pages.published.desc()).from_self(Issue).distinct()[:6]
        return {
                'latest_issues': latest_issues,
                }

    @view_config(
            route_name='blog',
            renderer='templates/blog.pt')
    def blog(self):
        return {}

    @view_config(
            route_name='bio',
            renderer='templates/bio.pt')
    def bio(self):
        return {}

    @view_config(
            route_name='links',
            renderer='templates/links.pt')
    def links(self):
        return {}

    @view_config(
            route_name='comics',
            renderer='templates/comics.pt')
    def comics(self):
        return {
                'comics': DBSession.query(Comic),
                }

    @view_config(
            route_name='issues',
            renderer='templates/issues.pt')
    def issues(self):
        issues = self.context.comic.published_issues.order_by(Issue.number.desc())
        return {
                'issues': issues,
                }

    @view_config(
            route_name='issue',
            renderer='templates/page.pt')
    def issue(self):
        self.context.page = self.context.issue.first_page
        return {
                'page_count': self.context.issue.published_pages.count(),
                }

    @view_config(route_name='issue_thumb')
    def issue_thumb(self):
        page = self.context.issue.first_page
        page.create_thumbnail()
        return FileResponse(page.thumbnail_filename)

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
            renderer='templates/page.pt')
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


class AdminView(BaseView):
    pass
