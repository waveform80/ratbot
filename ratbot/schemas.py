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
    validators,
    Schema,
    )

from ratbot.validators import (
    ForEach,
    ValidUserId,
    ValidUserName,
    ValidUserAdmin,
    )


class BaseSchema(Schema):
    filter_extra_fields = True
    allow_extra_fields = True


class FormSchema(BaseSchema):
    _came_from = validators.UnicodeString()


class UserSchema(FormSchema):
    id = ValidUserId()
    name = ValidUserName()
    admin = ValidUserAdmin()

