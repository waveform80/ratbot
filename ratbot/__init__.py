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
from pyramid_beaker import session_factory_from_settings
from pyramid_mailer import mailer_factory_from_settings
from sqlalchemy import engine_from_config

from ratbot.models import DBSession


ROUTES = {
    'index':           r'/',
    'bio':             r'/bio.html',
    'links':           r'/links.html',
    'comics':          r'/comics.html',
    'issues':          r'/comics/{comic_id}.html',
    'issue':           r'/comics/{comic_id}/{issue_number:\d+}.html',
    'issue_thumb':     r'/comics/{comic_id}-{issue_number:\d+}.png',
    'issue_archive':   r'/comics/{comic_id}-{issue_number:\d+}.zip',
    'issue_pdf':       r'/comics/{comic_id}-{issue_number:\d+}.pdf',
    'page':            r'/comics/{comic_id}/{issue_number:\d+}/{page_number:\d+}.html',
    'page_bitmap':     r'/comics/images/{comic_id}/{issue_number:\d+}/{page_number:\d+}.png',
    'page_vector':     r'/comics/images/{comic_id}/{issue_number:\d+}/{page_number:\d+}.svg',
    'page_thumb':      r'/comics/thumbs/{comic_id}/{issue_number:\d+}/{page_number:\d+}.png',
    }


def main(global_config, **settings):
    """Returns the Pyramid WSGI application"""
    # Check we're not using production.ini verbatim
    for key in ('authn.secret', 'session.secret'):
        if settings.get(key) == 'CHANGEME':
            raise ValueError('You must specify a new value for %s' % key)

    files_dir = settings['site.files']
    for d in (
            files_dir,
            os.path.join(files_dir, 'thumbs'),
            os.path.join(files_dir, 'bitmaps'),
            os.path.join(files_dir, 'vectors'),
            os.path.join(files_dir, 'archives'),
            os.path.join(files_dir, 'pdfs'),
            ):
        log.debug('Testing existence of %s', d)
        if not os.path.exists(d):
            os.mkdir(d)
        if not os.path.isdir(d):
            raise ValueError('%s is not a directory' % d)
        log.debug('Testing write access to %s', d)
        try:
            io.open(os.path.join(d, 'foo'), 'wb').close()
        except:
            raise ValueError('No write access to %s' % d)
        finally:
            try:
                os.unlink(os.path.join(d, 'foo'))
            except OSError:
                pass

    session_factory = session_factory_from_settings(settings)
    mailer_factory = mailer_factory_from_settings(settings)
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    config = Configurator(
            settings=settings,
            session_factory=session_factory)
    config.registry['mailer'] = mailer_factory
    config.add_static_view('static', 'static', cache_max_age=3600)
    for name, url in ROUTES.items():
        factory = None
        config.add_route(name, url, factory=factory)
    config.scan()
    return config.make_wsgi_app()

