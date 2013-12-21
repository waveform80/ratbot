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


from pyramid.decorator import reify
from pyramid.security import (
    Allow,
    Everyone,
    Authenticated,
    unauthenticated_userid,
    )

from ratbot.models import (
    DBSession,
    Comic,
    Issue,
    Page,
    )

# Permissions
CREATE_USER      = 'create_user'
EDIT_USER        = 'edit_user'
DESTROY_USER     = 'destroy_user'
CREATE_COMIC     = 'create_comic'
EDIT_COMIC       = 'edit_comic'
DESTROY_COMIC    = 'destroy_comic'
VIEW_COMIC       = 'view_comic'
VIEW_UNPUBLISHED = 'view_unpublished'

# Permission groups
ANONYMOUS_PERMISSIONS = (
        VIEW_COMIC,
        )
AUTHENTICATED_PERMISSIONS = ANONYMOUS_PERMISSIONS + ()
AUTHOR_PERMISSIONS = AUTHENTICATED_PERMISSIONS + (
        CREATE_COMIC,
        EDIT_COMIC,
        DESTROY_COMIC,
        VIEW_UNPUBLISHED,
        )
ADMIN_PERMISSIONS = AUTHOR_PERMISSIONS + (
        CREATE_USER,
        EDIT_USER,
        DESTROY_USER,
        )

AUTHOR_PRINCIPAL = 'author'
ADMIN_PRINCIPAL = 'admin'


def get_user(request):
    user_name = unauthenticated_userid(request)
    if user_name is not None:
        # TODO return a proper user object here
        return user_name

def group_finder(user_name, request):
    user = request.user
    principals = []
    if request.context is not None:
        if user.name == request.context.comic.author:
            principals.append(AUTHOR_PRINCIPAL)
    if user.is_admin:
        principals.append(ADMIN_PRINCIPAL)


class RootContextFactory(object):
    __acl__ = [
        (Allow, Everyone,         ANONYMOUS_PERMISSIONS),
        (Allow, Authenticated,    AUTHENTICATED_PERMISSIONS),
        (Allow, AUTHOR_PRINCIPAL, AUTHOR_PERMISSIONS),
        (Allow, ADMIN_PRINCIPAL,  ADMIN_PERMISSIONS),
        ]

    def __init__(self, request):
        self.comic = None


class ComicContextFactory(RootContextFactory):
    def __init__(self, request):
        super(ComicContextFactory, self).__init__(request)
        self.comic = DBSession.query(Comic).filter(
                (Comic.id == request.matchdict['comic'])
                ).one()


class IssueContextFactory(RootContextFactory):
    def __init__(self, request):
        super(IssueContextFactory, self).__init__(request)
        self.issue = DBSession.query(Issue).filter(
                (Issue.comic_id == request.matchdict['comic']) &
                (Issue.number == request.matchdict['issue'])
                ).one()

    @reify
    def comic(self):
        return self.issue.comic


class PageContextFactory(RootContextFactory):
    def __init__(self, request):
        super(PageContextFactory, self).__init__(request)
        self.page = DBSession.query(Page).filter(
                (Page.comic_id == request.matchdict['comic']) &
                (Page.issue_number == request.matchdict['issue']) &
                (Page.number == request.matchdict['page'])
                ).one()

    @reify
    def issue(self):
        return self.page.issue

    @reify
    def comic(self):
        return self.issue.comic

