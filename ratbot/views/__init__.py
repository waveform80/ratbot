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
import datetime
import logging
log = logging.getLogger(__name__)

import pytz
import webhelpers
import webhelpers.number
import webhelpers.date
import webhelpers.text
import webhelpers.misc
import webhelpers.util
import webhelpers.constants
import webhelpers.containers
from pyramid.decorator import reify
from pyramid.renderers import get_renderer
from pyramid.security import has_permission
from pyramid.events import subscriber, BeforeRender

from ratbot import html, markup
from ratbot.models import utcnow
from ratbot.security import Permission, Principal


@subscriber(BeforeRender)
def renderer_globals(event):
    # Add some useful renderer globals
    event['html'] = html
    event['markup'] = markup
    event['datetime'] = datetime
    event['webhelpers'] = webhelpers
    event['has_permission'] = lambda perm: has_permission(perm, event['context'], event['request'])
    event['Permission'] = Permission
    event['Principal'] = Principal
    if event['view']:
        # Debug toolbar (and presumably some other rendering tweens) doesn't
        # have a view
        event['utcnow'] = event['view'].utcnow
        event['utcize'] = lambda ts: pytz.utc.localize(ts)


class BaseView(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    @reify
    def layout(self):
        renderer = get_renderer('../templates/layout.pt')
        return renderer.implementation().macros['layout']

    @reify
    def nav_bar(self):
        renderer = get_renderer('../templates/nav_bar.pt')
        return renderer.implementation().macros['nav-bar']

    @reify
    def flashes(self):
        renderer = get_renderer('../templates/flashes.pt')
        return renderer.implementation().macros['flashes']

    @reify
    def site_title(self):
        return self.request.registry.settings['site.title']

    @reify
    def utcnow(self):
        return utcnow()

