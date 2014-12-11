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
import cgi
import shutil
import tempfile
import logging
log = logging.getLogger(__name__)

import pytz
import json
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.view import view_config
from pyramid.security import remember, forget
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from . import BaseView
from ..forms import Form, FormRendererFoundation
from ..markup import MARKUP_LANGUAGES
from ..models import (
    DBSession,
    Page,
    Issue,
    Comic,
    User,
    utcnow,
    )
from ..security import (
    Permission,
    Principal,
    )
from ..schemas import (
    UserSchema,
    ComicSchema,
    IssueSchema,
    PageSchema,
    )


def is_upload(request, name):
    return isinstance(request.POST.get(name), cgi.FieldStorage)


class LoginView(BaseView):
    @view_config(
            context='velruse.AuthenticationComplete')
    def login_complete(self):
        try:
            email = self.context.profile['verifiedEmail']
        except KeyError:
            try:
                # Neither Twitter nor GitHub currently provide verified e-mails
                # in their OAuth response
                if self.context.provider_name == 'github':
                    email = self.context.profile['emails'][0]['value']
                elif self.context.provider_name == 'twitter':
                    email = self.context.profile['accounts'][0]['username'] + '@twitter.com'
                else:
                    return HTTPForbidden()
            except (KeyError, IndexError) as e:
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
            return HTTPFound(location=self.request.route_url('comics'))
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
            return HTTPFound(location=self.request.route_url('comics'))
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
            self.request.session.flash(
                    'Created issue #%d of %s' % (
                        issue.number,
                        self.context.comic.title,
                        ))
            DBSession.flush()
            return HTTPFound(location=
                    self.request.route_url('issues', comic=self.context.comic.id)
                    if self.context.comic.id != 'blog' else
                    self.request.route_url('blog_index', comic='blog')
                    )
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
                came_from=
                    self.request.route_url('issues', comic=self.context.issue.comic_id)
                    if self.context.issue.comic_id != 'blog' else
                    self.request.route_url('blog_index', comic='blog'),
                variable_decode=True)
        if form.validate():
            if bool(self.request.POST.get('delete', '')):
                DBSession.delete(issue)
                self.request.session.flash('Deleted issue #%d of %s' % (
                    issue.number,
                    issue.comic.title,
                    ))
                for i in DBSession.query(Issue).filter(
                        (Issue.comic_id == issue.comic_id) &
                        (Issue.number > issue.number)
                        ).order_by(Issue.number):
                    i.number = i.number - 1
            else:
                form.bind(issue)
                self.request.session.flash('Updated issue #%d of %s' % (
                    issue.number,
                    issue.comic.title,
                    ))
            # Grab a copy of the comic ID before the object becomes invalid
            comic_id = issue.comic_id
            DBSession.flush()
            return HTTPFound(location=
                    self.request.route_url('issues', comic=comic_id)
                    if comic_id != 'blog' else
                    self.request.route_url('blog_index', comic='blog')
                    )
        return dict(
                create=False,
                form=FormRendererFoundation(form),
                )

    @view_config(
            route_name='admin_page_new',
            permission=Permission.edit_comic,
            renderer='../templates/admin/page.pt')
    def page_new(self):
        new_number = DBSession.query(
                func.coalesce(func.max(Page.number), 0) + 1
            ).filter(
                (Page.comic_id==self.context.issue.comic_id) &
                (Page.issue_number==self.context.issue.number)
            ).scalar()
        form = Form(
                self.request,
                defaults={
                    'comic_id': self.context.issue.comic_id,
                    'issue_number': self.context.issue.number,
                    'number': new_number,
                    'created': self.utcnow,
                    'published': self.utcnow,
                    },
                schema=PageSchema,
                variable_decode=True)
        # Separate validation for file fields
        if self.request.method == 'POST':
            if not (is_upload(self.request, 'vector') or is_upload(self.request, 'bitmap')):
                form.errors['vector'] = 'Vector or bitmap image is required'
                form.errors['bitmap'] = 'Vector or bitmap image is required'
            else:
                if is_upload(self.request, 'bitmap'):
                    if self.request.POST['bitmap'].type != 'image/png':
                        form.errors['bitmap'] = 'Bitmap must be a PNG image'
                if is_upload(self.request, 'thumbnail'):
                    if self.request.POST['thumbnail'].type != 'image/png':
                        form.errors['thumbnail'] = 'Bitmap must be a PNG image'
        if form.validate():
            page = form.bind(Page())
            if is_upload(self.request, 'vector'):
                page.vector = self.request.POST['vector'].file
            if is_upload(self.request, 'bitmap'):
                page.bitmap = self.request.POST['bitmap'].file
            if is_upload(self.request, 'thumbnail'):
                page.thumbnail = self.request.POST['thumbnail'].file
            DBSession.add(page)
            self.context.issue.invalidate()
            self.request.session.flash(
                    'Added page %d of %s #%d' % (
                        page.number,
                        self.context.issue.comic.title,
                        self.context.issue.number,
                        ))
            DBSession.flush()
            return HTTPFound(location=
                    self.request.route_url('issues',
                        comic=self.context.issue.comic_id)
                    if self.context.issue.comic_id != 'blog' else
                    self.request.route_url('blog_index', comic='blog'))
        return dict(
                create=True,
                form=FormRendererFoundation(form),
                )

    @view_config(
            route_name='admin_page',
            permission=Permission.edit_comic,
            renderer='../templates/admin/page.pt')
    def page_edit(self):
        page = self.context.page
        form = Form(
                self.request,
                obj=page,
                schema=PageSchema,
                variable_decode=True)
        if self.request.method == 'POST':
            if is_upload(self.request, 'bitmap'):
                if self.request.POST['bitmap'].type != 'image/png':
                    form.errors['bitmap'] = 'Bitmap must be a PNG image'
            if is_upload(self.request, 'thumbnail'):
                if self.request.POST['thumbnail'].type != 'image/png':
                    form.errors['thumbnail'] = 'Bitmap must be a PNG image'
        if form.validate():
            if bool(self.request.POST.get('delete', '')):
                DBSession.delete(page)
                self.request.session.flash('Deleted page %d of %s #%d' % (
                    page.number,
                    page.issue.comic.title,
                    page.issue_number,
                    ))
                for p in DBSession.query(Page).filter(
                        (Page.comic_id == page.comic_id) &
                        (Page.issue_number == page.issue_number) &
                        (Page.number > page.number)
                        ).order_by(Page.number):
                    p.number = p.number - 1
            else:
                if bool(self.request.POST.get('delete_bitmap', '')):
                    page.bitmap = None
                if bool(self.request.POST.get('delete_thumbnail', '')):
                    page.thumbnail = None
                if is_upload(self.request, 'vector'):
                    page.vector = self.request.POST['vector'].file
                if is_upload(self.request, 'bitmap'):
                    page.bitmap = self.request.POST['bitmap'].file
                if is_upload(self.request, 'thumbnail'):
                    page.thumbnail = self.request.POST['thumbnail'].file
                form.bind(page)
                self.request.session.flash('Altered page %d of %s #%d' % (
                    page.number,
                    page.issue.comic.title,
                    page.issue_number,
                    ))
            page.issue.invalidate()
            # Grab a copy of the comic ID before the object becomes invalid
            comic_id = page.comic_id
            DBSession.flush()
            return HTTPFound(location=
                    self.request.route_url('issues', comic=comic_id)
                    if comic_id != 'blog' else
                    self.request.route_url('blog_index', comic='blog'))
        return dict(
                create=False,
                form=FormRendererFoundation(form),
                vector_stat=os.stat(page.vector_filename) if page.vector_filename else None,
                bitmap_stat=os.stat(page.bitmap_filename) if page.bitmap_filename else None,
                thumbnail_stat=os.stat(page.thumbnail_filename) if page.thumbnail_filename else None,
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

