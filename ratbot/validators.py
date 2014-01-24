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


from formencode import (
    ForEach,
    Invalid,
    validators,
    )

from ratbot.markup import MARKUP_LANGUAGES
from ratbot.models import (
    DBSession,
    Comic,
    Issue,
    Page,
    User,
    )


class ValidPositiveInt(validators.Int):
    def __init__(self):
        super(ValidPositiveInt, self).__init__(not_empty=True, min=0)


class ValidUser(validators.OneOf):
    def __init__(self):
        super(ValidUser, self).__init__(
            DBSession.query(User.id), not_empty=True)


class ValidUserId(validators.Email):
    def __init__(self):
        super(ValidUserId, self).__init__(not_empty=True)


class ValidUserName(validators.UnicodeString):
    def __init__(self):
        super(ValidUserName, self).__init__(
            not_empty=True, max=User.__table__.c.name.type.length)


class ValidUserAdmin(validators.Bool):
    pass


class ValidMarkupLanguage(validators.OneOf):
    def __init__(self):
        super(ValidMarkupLanguage, self).__init__(
            MARKUP_LANGUAGES.keys(), not_empty=True)


class ValidDescription(validators.UnicodeString):
    def __init__(self):
        super(ValidDescription, self).__init__(not_empty=False)


class ValidComicId(validators.Regex):
    def __init__(self):
        super(ValidComicId, self).__init__(
            r'^[A-Za-z][A-Za-z0-9_-]{,19}$', not_empty=True, strip=True)


class ValidComicTitle(validators.UnicodeString):
    def __init__(self):
        super(ValidComicTitle, self).__init__(
            not_empty=True, max=Comic.__table__.c.title.type.length)

