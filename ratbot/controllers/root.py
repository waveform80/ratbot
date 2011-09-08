# -*- coding: utf-8 -*-
"""Main Controller"""

from tg import expose, flash, require, url, request, redirect
from tg.i18n import ugettext as _, lazy_ugettext as l_
from tgext.admin import AdminConfig
from repoze.what import predicates

from ratbot.lib.base import BaseController
from ratbot.model import DBSession, metadata
from ratbot import model
from ratbot.controllers.admin import AdminController
from ratbot.controllers.error import ErrorController

__all__ = ['RootController']


class RootController(BaseController):
    """
    The root controller for the ratbot application.
    """
    admin = AdminController(model, DBSession, config_type=AdminConfig)
    error = ErrorController()

    @expose('ratbot.templates.index')
    def index(self):
        return dict(page='index')

    @expose('ratbot.templates.bio')
    def bio(self):
        return dict(page='bio')

    @expose('ratbot.templates.comics')
    def comics(self):
        return dict(page='comics')

    @expose('ratbot.templates.environ')
    def environ(self):
        return dict(environment=request.environ)

    @expose('ratbot.templates.data')
    @expose('json')
    def data(self, **kw):
        """This method showcases how you can use the same controller for a data page and a display page"""
        return dict(params=kw)

    @expose('ratbot.templates.login')
    def login(self, came_from=url('/')):
        """Start the user login."""
        login_counter = request.environ['repoze.who.logins']
        if login_counter > 0:
            flash(_('Wrong credentials'), 'warning')
        return dict(page='login', login_counter=str(login_counter),
                    came_from=came_from)

    @expose()
    def post_login(self, came_from='/'):
        """
        Redirect the user to the initially requested page on successful
        authentication or redirect her back to the login page if login failed.
        """
        if not request.identity:
            login_counter = request.environ['repoze.who.logins'] + 1
            redirect('/login',
                params=dict(came_from=came_from, __logins=login_counter))
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
