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

from pyramid.request import Request
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound
from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    )

from .models import (
    DBSession,
    Comic,
    Issue,
    Page,
    User,
    )


class Permission():
    create_user      = 'create_user'
    edit_user        = 'edit_user'
    destroy_user     = 'destroy_user'
    create_comic     = 'create_comic'
    edit_comic       = 'edit_comic'
    destroy_comic    = 'destroy_comic'
    view_admin       = 'view_admin'
    view_comic       = 'view_comic'
    view_unpublished = 'view_unpublished'

    anonymous = (
            view_comic,
            )
    authenticated = anonymous + ()
    author = authenticated + (
            create_comic,
            edit_comic,
            destroy_comic,
            view_unpublished,
            )
    admin = author + (
            create_user,
            edit_user,
            destroy_user,
            view_admin,
            )

class Principal():
    author = 'author'
    admin = 'admin'


class RequestWithUser(Request):
    @reify
    def db(self):
        return DBSession()

    @reify
    def user(self):
        user_id = self.unauthenticated_userid
        if user_id:
            return DBSession.query(User).get(user_id)


class RootContextFactory():
    __acl__ = [
        (Allow, Everyone,         Permission.anonymous),
        (Allow, Authenticated,    Permission.authenticated),
        (Allow, Principal.author, Permission.author),
        (Allow, Principal.admin,  Permission.admin),
        ]

    def __init__(self, request):
        pass


class ComicContextFactory(RootContextFactory):
    def __init__(self, request):
        super().__init__(request)
        self.comic = DBSession.query(Comic).get(request.matchdict['comic'])
        if not self.comic:
            raise HTTPNotFound()


class IssueContextFactory(RootContextFactory):
    def __init__(self, request):
        super().__init__(request)
        self.issue = DBSession.query(Issue).get((
                request.matchdict['comic'],
                int(request.matchdict['issue']),
                ))
        if not self.issue:
            raise HTTPNotFound()

    @reify
    def comic(self):
        return self.issue.comic


class PageContextFactory(RootContextFactory):
    def __init__(self, request):
        super().__init__(request)
        self.page = DBSession.query(Page).get((
                request.matchdict['comic'],
                int(request.matchdict['issue']),
                int(request.matchdict['page']),
                ))
        if not self.page:
            raise HTTPNotFound()

    @reify
    def issue(self):
        return self.page.issue

    @reify
    def comic(self):
        return self.issue.comic


def group_finder(user_name, request):
    user = request.user
    if not user:
        return None
    principals = []
    try:
        context = request.context
    except AttributeError:
        pass
    else:
        if isinstance(context, (ComicContextFactory, IssueContextFactory, PageContextFactory)):
            if user.user_id == context.comic.author_id:
                principals.append(Principal.author)
    if user.admin:
        principals.append(Principal.admin)
    return principals

