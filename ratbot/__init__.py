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

import io
import os
import logging
log = logging.getLogger(__name__)

from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_beaker import session_factory_from_settings
from pyramid_mailer import mailer_factory_from_settings
from sqlalchemy import engine_from_config

from ratbot.models import DBSession
from ratbot.views.comics import routes as comic_routes
from ratbot.views.admin import routes as admin_routes
from ratbot.security import (
    RequestWithUser,
    RootContextFactory,
    ComicContextFactory,
    IssueContextFactory,
    PageContextFactory,
    group_finder,
    )


def main(global_config, **settings):
    """Returns the Pyramid WSGI application"""
    # Ensure we're not using production.ini verbatim
    for key in (
            'authn.secret',
            'session.secret',
            'login.google.consumer_key',
            'login.google.consumer_secret',
            'login.facebook.consumer_key',
            'login.facebook.consumer_secret',
            ):
        if settings.get(key) == 'CHANGEME':
            raise ValueError('You must specify a new value for %s' % key)

    # Ensure path is configured appropriately
    files_dir = os.path.normpath(os.path.expanduser(settings['site.files']))
    log.debug('Testing existence of %s', files_dir)
    if not os.path.exists(files_dir):
        os.mkdir(files_dir)
    if not os.path.isdir(files_dir):
        raise ValueError('%s is not a directory' % files_dir)
    log.debug('Testing write access to %s', files_dir)
    try:
        io.open(os.path.join(files_dir, 'foo'), 'wb').close()
    except:
        raise ValueError('No write access to %s' % files_dir)
    finally:
        try:
            os.unlink(os.path.join(files_dir, 'foo'))
        except OSError:
            pass

    session_factory = session_factory_from_settings(settings)
    mailer_factory = mailer_factory_from_settings(settings)
    # XXX Need some way of grabbing the authentication secret from config
    authn_policy = AuthTktAuthenticationPolicy(
        'secret', hashalg='sha512', callback=group_finder)
    authz_policy = ACLAuthorizationPolicy()
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine, info={'site.files': files_dir})

    config = Configurator(
            settings=settings,
            session_factory=session_factory,
            request_factory=RequestWithUser,
            )
    config.include('velruse.providers.google_oauth2')
    config.include('velruse.providers.facebook')
    config.add_google_oauth2_login_from_settings(prefix='login.google.')
    config.add_facebook_login_from_settings(prefix='login.facebook.')
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.registry['mailer'] = mailer_factory
    config.add_static_view('static', 'static', cache_max_age=3600)
    for name, pattern in comic_routes() + admin_routes():
        if '{page' in pattern:
            factory = PageContextFactory
        elif '{issue' in pattern:
            factory = IssueContextFactory
        elif '{comic' in pattern:
            factory = ComicContextFactory
        else:
            factory = RootContextFactory
        config.add_route(name, pattern, factory=factory)
    config.scan()
    return config.make_wsgi_app()

