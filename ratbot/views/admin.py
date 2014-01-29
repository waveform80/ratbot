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
from pyramid.security import remember, forget
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from ratbot.forms import Form, FormRendererFoundation
from ratbot.markup import MARKUP_LANGUAGES
from ratbot.views import BaseView
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
from ratbot.schemas import (
    UserSchema,
    ComicSchema,
    IssueSchema,
    PageSchema,
    )


class LoginView(BaseView):
    @view_config(
            context='velruse.AuthenticationComplete',
            renderer='../templates/admin/login.pt')
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
    @reify
    def markup_languages(self):
        return MARKUP_LANGUAGES

    @view_config(
            route_name='admin_index',
            permission=Permission.view_admin,
            renderer='../templates/admin/index.pt')
    def index(self):
        comics_query = DBSession.query(
                Comic,
                User.name,
                func.count(Issue.number),
            ).outerjoin(Issue).join(User).group_by(
                Comic,
                User.name
            ).order_by(
                Comic.title
            )
        users_query = DBSession.query(User).order_by(User.name)
        return {
                'comics': comics_query,
                'users': users_query,
                }

    @view_config(
            route_name='admin_user_new',
            permission=Permission.create_user,
            renderer='../templates/admin/user.pt')
    def user_new(self):
        form = Form(
                self.request,
                schema=UserSchema,
                variable_decode=True)
        if form.validate():
            user = form.bind(User())
            DBSession.add(user)
            self.request.session.flash('Created user %s' % user.id)
            DBSession.flush()
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(
                create=True,
                form=FormRendererFoundation(form),
                )

    @view_config(
            route_name='admin_user',
            permission=Permission.edit_user,
            renderer='../templates/admin/user.pt')
    def user_edit(self):
        user = DBSession.query(User).get(self.request.matchdict['user'])
        form = Form(
                self.request,
                obj=user,
                schema=UserSchema,
                variable_decode=True)
        if form.validate():
            if bool(self.request.POST.get('delete', '')):
                DBSession.delete(user)
                self.request.session.flash('Deleted user %s' % user.id)
            else:
                form.bind(user)
                self.request.session.flash('Updated user %s' % user.id)
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(
                create=False,
                form=FormRendererFoundation(form),
                )

    @view_config(
            route_name='admin_comic_new',
            permission=Permission.create_comic,
            renderer='../templates/admin/comic.pt')
    def comic_new(self):
        form = Form(
                self.request,
                schema=ComicSchema,
                variable_decode=True)
        if form.validate():
            comic = form.bind(Comic())
            DBSession.add(comic)
            self.request.session.flash('Created comic %s' % comic.id)
            DBSession.flush()
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(
                create=True,
                form=FormRendererFoundation(form),
                authors=DBSession.query(User.id, User.name).order_by(User.name),
                )

    @view_config(
            route_name='admin_comic',
            permission=Permission.edit_comic,
            renderer='../templates/admin/comic.pt')
    def comic_edit(self):
        comic = self.context.comic
        form = Form(
                self.request,
                obj=comic,
                schema=ComicSchema,
                variable_decode=True)
        if form.validate():
            if bool(self.request.POST.get('delete', '')):
                DBSession.delete(comic)
                self.request.session.flash('Deleted comic "%s"' % comic.title)
            else:
                form.bind(comic)
                self.request.session.flash('Updated comic "%s"' % comic.title)
            DBSession.flush()
            return HTTPFound(location=self.request.route_url('admin_index'))
        return dict(
                create=False,
                form=FormRendererFoundation(form),
                authors=DBSession.query(User.id, User.name).order_by(User.name),
                )

    @view_config(
            route_name='admin_issue_new',
            permission=Permission.edit_comic,
            renderer='../templates/admin/issue.pt')
    def issue_new(self):
        new_number = DBSession.query(
                func.coalesce(func.max(Issue.number), 0) + 1
            ).filter(
                (Issue.comic_id==self.context.comic.id)
            ).scalar()
        form = Form(
                self.request,
                defaults={
                    'comic_id': self.context.comic.id,
                    'number': new_number,
                    'created': self.utcnow,
                    },
                schema=IssueSchema,
                variable_decode=True)
        if form.validate():
            issue = form.bind(Issue())
            DBSession.add(issue)
            self.request.session.flash('Created issue %d' % issue.number)
            DBSession.flush()
            return HTTPFound(
                    location=self.request.route_url('issues',
                        comic=self.context.comic.id))
        return dict(
                create=True,
                form=FormRendererFoundation(form),
                )

    @view_config(
            route_name='admin_issue',
            permission=Permission.edit_comic,
            renderer='../templates/admin/issue.pt')
    def issue_edit(self):
        issue = self.context.issue
        form = Form(
                self.request,
                obj=issue,
                schema=IssueSchema,
                variable_decode=True)
        if form.validate():
            if bool(self.request.POST.get('delete', '')):
                DBSession.delete(issue)
                self.request.session.flash('Deleted "%s" issue #%d' % (issue.comic.title, issue.number))
            else:
                form.bind(issue)
                self.request.session.flash('Updated "%s" issue #%d' % (issue.comic.title, issue.number))
            # Grab a copy of the comic ID before the object becomes invalid
            comic_id = issue.comic_id
            DBSession.flush()
            return HTTPFound(
                    location=self.request.route_url('issues', comic=comic_id))
        return dict(
                create=False,
                form=FormRendererFoundation(form),
                )


def routes():
    return (
            ('admin_index',     r'/admin/index.html'),
            ('admin_user',      r'/admin/users/{user}.html'),
            ('admin_user_new',  r'/admin/users/create.do'),
            ('admin_comic',     r'/admin/comics/{comic}.html'),
            ('admin_comic_new', r'/admin/comics/create.do'),
            ('admin_issues',    r'/admin/issues/{comic}/index.html'),
            ('admin_issue',     r'/admin/issues/{comic}/{issue:\d+}.html'),
            ('admin_issue_new', r'/admin/issues/{comic}/create.do'),
            ('admin_pages',     r'/admin/pages/{comic}/{issue:\d+}/index.html'),
            ('admin_page',      r'/admin/pages/{comic}/{issue:\d+}/{page:\d+}.html'),
            ('admin_page_new',  r'/admin/pages/{comic}/{issue:\d+}/create.do'),
            ('logout',          r'/logout.do')
            )

