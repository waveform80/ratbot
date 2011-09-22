# -*- coding: utf-8 -*-
"""Main Controller"""

from tg import expose, flash, require, url, request, redirect
from tg.i18n import ugettext as _, lazy_ugettext as l_
from repoze.what import predicates

from ratbot.lib.base import BaseController
from ratbot.model import DBSession, News, Issue, Page
from ratbot.controllers.admin import AdminController
from ratbot.controllers.error import ErrorController
from ratbot.controllers.comic import ComicController
from sqlalchemy import func

__all__ = ['RootController']


class RootController(BaseController):
    """
    The root controller for the ratbot application.
    """
    admin = AdminController()
    comics = ComicController()
    error = ErrorController()

    @expose('ratbot.templates.index')
    def index(self):
        news = DBSession.query(News).order_by(News.created.desc()).limit(5)
        issues = list(DBSession.query(Issue, func.max(Page.published)).\
            join(Page).\
            group_by(Issue).\
            order_by(func.max(Page.published).desc()).\
            limit(3).all())
        while len(issues) < 3:
            issues.append((None, None))
        return dict(
            method='index',
            issues=issues,
            news=news,
        )

    @expose('ratbot.templates.bio')
    def bio(self):
        return dict(method='bio')

    @expose('ratbot.templates.login')
    def login(self, came_from=url('/')):
        """Start the user login."""
        login_counter = request.environ['repoze.who.logins']
        if login_counter > 0:
            flash(_('Wrong credentials'), 'warning')
        return dict(
            page='login',
            login_counter=str(login_counter),
            came_from=came_from,
        )

    @expose()
    def post_login(self, came_from='/'):
        """
        Redirect the user to the initially requested page on successful
        authentication or redirect her back to the login page if login failed.
        """
        if not request.identity:
            login_counter = request.environ['repoze.who.logins'] + 1
            redirect('/login', params=dict(came_from=came_from, __logins=login_counter))
        userid = request.identity['repoze.who.userid']
        flash(_('Welcome back, %s!') % userid)
        redirect(came_from)

    @expose()
    def post_logout(self, came_from=url('/')):
        """
        Redirect the user to the initially requested page on logout and say
        goodbye as well.
        """
        flash(_('We hope to see you soon!'))
        redirect(came_from)
