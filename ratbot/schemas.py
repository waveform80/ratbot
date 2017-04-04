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

from formencode import (
    validators,
    Schema,
    )

from .validators import (
    ForEach,
    ValidAuthor,
    ValidUserId,
    ValidUserName,
    ValidUserAdmin,
    ValidMarkupLanguage,
    ValidDescription,
    ValidPositiveInt,
    ValidTimestamp,
    ValidComicId,
    ValidComicTitle,
    ValidIssueTitle,
    ValidLicense,
    )


class BaseSchema(Schema):
    filter_extra_fields = True
    allow_extra_fields = True


class FormSchema(BaseSchema):
    _came_from = validators.UnicodeString()


class UserSchema(FormSchema):
    user_id = ValidUserId()
    name = ValidUserName()
    admin = ValidUserAdmin()
    markup = ValidMarkupLanguage()
    description = ValidDescription()


class ComicSchema(FormSchema):
    comic_id = ValidComicId()
    title = ValidComicTitle()
    author = ValidAuthor()
    license = ValidLicense()
    markup = ValidMarkupLanguage()
    description = ValidDescription()


class IssueSchema(FormSchema):
    comic_id = ValidComicId()
    issue_number = ValidPositiveInt()
    title = ValidIssueTitle()
    created = ValidTimestamp()
    markup = ValidMarkupLanguage()
    description = ValidDescription()


class PageSchema(FormSchema):
    comic_id = ValidComicId()
    issue_number = ValidPositiveInt()
    page_number = ValidPositiveInt()
    created = ValidTimestamp()
    published = ValidTimestamp()
    markup = ValidMarkupLanguage()
    description = ValidDescription()

