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

import json
import logging
log = logging.getLogger(__name__)

import pytz
from pyramid.decorator import reify
from pyramid.renderers import get_renderer
from pyramid.response import Response, FileResponse
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.view import view_config
from pyramid.security import remember, forget, has_permission
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from velruse.api import login_url

from ratbot.markup import render
from ratbot.models import (
    DBSession,
    Page,
    Issue,
    Comic,
    User,
    utcnow,
    )
from ratbot.security import (
    Permission,
    Principal,
    )
from ratbot.forms import (
    Form,
    FormRendererFoundation,
    )
from ratbot.schemas import (
    UserSchema,
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

    def render_markup(self, language, source):
        return render(language, source)

    def has_permission(self, permission):
        return has_permission(permission, self.context, self.request)


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
                'Permission': Permission,
                'latest_issues': latest_issues,
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
            renderer='templates/blog.pt')
    def blog_issue(self):
        pages = self.context.issue.published_pages.order_by(Page.number.desc())
        issues = self.context.issue.comic.published_issues.order_by(Issue.number.desc())
        return {
                'pages':  pages,
                'issues': issues,
                }

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
                'comics': DBSession.query(Comic).filter(Comic.id != 'blog'),
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


class LoginView(BaseView):
    @view_config(
            context='velruse.AuthenticationComplete',
            renderer='templates/login.pt')
    def login_complete(self):
        try:
            email = self.context.profile['verifiedEmail']
        except KeyError:
            # No verified e-mail in profile
            return HTTPForbidden()
        try:
            user = DBSession.query(User).filter(User.id == email).one()
        except NoResultFound:
            user = User(id=email, name=self.context.profile.get('displayName', email))
            DBSession.add(user)
            DBSession.flush()
        return HTTPFound(
            location=self.request.route_url('index'),
            headers=remember(self.request, user.id))
        #result = {
        #    'provider_type': self.context.provider_type,
        #    'provider_name': self.context.provider_name,
        #    'profile': self.context.profile,
        #    'credentials': self.context.credentials,
        #    }
        #return {
        #    'result': json.dumps(result, indent=4),
        #    }

    @view_config(
            context='velruse.AuthenticationDenied')
    def login_denied(self):
        return HTTPForbidden()

    @view_config(
            route_name='logout')
    def logout(self):
        return HTTPFound(
            location=self.request.route_url('index'),
            headers=forget(self.request))


class AdminView(BaseView):
    @view_config(
            route_name='admin_index',
            permission=Permission.view_admin,
            renderer='templates/admin.pt')
    def index(self):
        return {
                'comics': DBSession.query(Comic).order_by(Comic.id),
                'users': DBSession.query(User).order_by(User.id),
                }

    @view_config(
            route_name='admin_user_new',
            permission=Permission.create_user,
            renderer='templates/user.pt')
    def user_new(self):
        form = Form(
                self.request,
                schema=UserSchema,
                variable_decode=True)
        if form.validate():
            user = form.bind(User())
            DBSession.add(user)
            DBSession.flush()
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(form=FormRendererFoundation(form))

    @view_config(
            route_name='admin_user',
            permission=Permission.edit_user,
            renderer='templates/user.pt')
    def user_edit(self):
        user = DBSession.query(User).get(self.request.matchdict['user'])
        form = Form(
                self.request,
                obj=user,
                schema=UserSchema,
                variable_decode=True)
        if form.validate():
            form.bind(user)
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(form=FormRendererFoundation(form))
