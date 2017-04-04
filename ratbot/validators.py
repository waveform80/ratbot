# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2016 Dave Jones <dave@waveform.org.uk>.
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

import datetime as dt

from formencode import (
    ForEach,
    Invalid,
    validators,
    )
from pyramid.threadlocal import get_current_registry

from .markup import MARKUP_LANGUAGES
from .models import (
    DBSession,
    Comic,
    Issue,
    Page,
    User,
    )


class ValidPositiveInt(validators.Int):
    def __init__(self):
        super(ValidPositiveInt, self).__init__(not_empty=True, min=1)


class ValidTimestamp(validators.DateValidator):
    def __init__(self):
        super(ValidTimestamp, self).__init__(not_empty=True)

    def _to_python(self, value, state):
        try:
            formats = {
                16: ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'),
                19: ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'),
                }[len(value)]
        except KeyError:
            raise ValueError('Invalid length for datetime representation: %d' % len(value))
        for f in formats:
            try:
                return dt.datetime.strptime(value, f)
            except ValueError:
                pass
        raise ValueError('Invalid datetime value: %s' % value)

    def _from_python(self, value, state):
        return value.strftime('%Y-%m-%dT%H:%M:%S')


class ValidAuthor(validators.OneOf):
    def __init__(self):
        super(ValidAuthor, self).__init__(list=[], hideList=True, not_empty=True)

    def validate_python(self, value, state):
        self.list = [s for (s,) in DBSession.query(User.user_id)]
        super(ValidAuthor, self).validate_python(value.user_id, state)

    def _to_python(self, value, state):
        return DBSession.query(User).get(value)

    def _from_python(self, value, state):
        return value.user_id


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


class ValidIssueTitle(validators.UnicodeString):
    def __init__(self):
        super(ValidIssueTitle, self).__init__(
            not_empty=True, max=Issue.__table__.c.title.type.length)


class ValidLicense(validators.OneOf):
    def __init__(self):
        super(ValidLicense, self).__init__(list=[], hideList=True)

    def validate_python(self, value, state):
        self.list = get_current_registry()['licenses']().keys()
        super(ValidLicense, self).validate_python(value.id, state)

    def _to_python(self, value, state):
        return get_current_registry()['licenses']()[value]

    def _from_python(self, value, state):
        return value.id

