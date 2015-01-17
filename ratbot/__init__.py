# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2014 Dave Jones <dave@waveform.org.uk>.
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

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import io
import os
import errno
import logging
log = logging.getLogger(__name__)

from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_beaker import session_factory_from_settings
from pyramid_mailer import mailer_factory_from_settings
from sqlalchemy import engine_from_config

from .licenses import licenses_factory_from_settings


def check_path(path):
    log.debug('Testing existence of %s', path)
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    if not os.path.isdir(path):
        raise ValueError('%s is not a directory' % path)
    log.debug('Testing write access to %s', path)
    try:
        with io.open(os.path.join(path, 'write_test'), 'wb') as f:
            f.close()
    except OSError:
        raise ValueError('No write access to %s' % path)
    finally:
        try:
            os.unlink(os.path.join(path, 'write_test'))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def main(global_config, **settings):
    "Returns the Pyramid WSGI application"

    # Ensure we're not using production.ini verbatim
    for key in (
            'site.store',
            'authn.secret',
            'session.secret',
            'login.google.consumer_key',
            'login.google.consumer_secret',
            'login.facebook.consumer_key',
            'login.facebook.consumer_secret',
            'login.twitter.consumer_key',
            'login.twitter.consumer_secret',
            'login.github.consumer_key',
            'login.github.consumer_secret',
            ):
        if settings.get(key) == 'CHANGEME':
            raise ValueError('You must specify a new value for %s' % key)

    # Ensure path is configured appropriately
    files_dir = os.path.normpath(os.path.expanduser(settings['site.files']))
    licenses_dir = os.path.normpath(os.path.expanduser(settings['licenses.cache_dir']))
    check_path(settings['site.files'])
    check_path(settings['licenses.cache_dir'])

    session_factory = session_factory_from_settings(settings)
    mailer_factory = mailer_factory_from_settings(settings)
    licenses_factory = licenses_factory_from_settings(settings)
    engine = engine_from_config(settings, 'sqlalchemy.')

    # Configure the database session; the session is deliberately separated
    # from the model to enable us to bind it to an engine before importing
    # the model which will then use the bound engine to reflect the database
    from .db_session import DBSession
    DBSession.configure(bind=engine, info={'site.files': files_dir})

    from .security import RequestWithUser, group_finder
    config = Configurator(
            settings=settings,
            session_factory=session_factory,
            request_factory=RequestWithUser,
            )
    if settings.get('login.google.consumer_key'):
        config.include('velruse.providers.google_oauth2')
        config.add_google_oauth2_login_from_settings(prefix='login.google.')
    if settings.get('login.facebook.consumer_key'):
        config.include('velruse.providers.facebook')
        config.add_facebook_login_from_settings(prefix='login.facebook.')
    if settings.get('login.twitter.consumer_key'):
        config.include('velruse.providers.twitter')
        config.add_twitter_login_from_settings(prefix='login.twitter.')
    if settings.get('login.github.consumer_key'):
        config.include('velruse.providers.github')
        config.add_github_login_from_settings(prefix='login.github.')
    config.include('pyramid_chameleon')
    # XXX Need some way of grabbing the authentication secret from config
    authn_policy = AuthTktAuthenticationPolicy(
        'secret', hashalg='sha512', callback=group_finder)
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.registry['mailer'] = mailer_factory
    config.registry['licenses'] = licenses_factory
    config.add_static_view('static', 'static', cache_max_age=3600)

    from .views.comics import routes as comic_routes
    from .views.admin import routes as admin_routes
    from .security import (
        RootContextFactory,
        ComicContextFactory,
        IssueContextFactory,
        PageContextFactory,
        )
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

