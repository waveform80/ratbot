# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
from datetime import datetime
import sys

from sqlalchemy import Table, ForeignKey, ForeignKeyConstraint, CheckConstraint, Column
from sqlalchemy.types import Unicode, Integer, DateTime, LargeBinary
from sqlalchemy.orm import relationship, synonym
from ratbot.model import DeclarativeBase, metadata, DBSession
from ratbot.model.auth import User
from PIL import Image
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


__all__ = ['Comic', 'Issue', 'Page', 'News']


class News(DeclarativeBase):
    """
    News article definition.
    """

    __tablename__ = 'news'

    id = Column(Integer, autoincrement=True, primary_key=True)
    title = Column(Unicode(100), nullable=False)
    content = Column(Unicode, nullable=False)
    published = Column(DateTime, default=datetime.now, nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    author = Column(Unicode(100), ForeignKey('users.user_name',
        ondelete="SET NULL", onupdate="CASCADE"))
    auth_user = relationship(User, backref='articles')

    def __repr__(self):
        return '<News: id=%d>' % self.id

    def __unicode__(self):
        return self.title


class Page(DeclarativeBase):
    """
    Issue page definition.
    """

    __tablename__ = 'pages'
    __table_args__ = (
        ForeignKeyConstraint(['comic_id', 'issue_number'], ['issues.comic_id', 'issues.number']),
        {},
    )

    comic_id = Column(Unicode(20), primary_key=True)
    issue_number = Column(Integer, primary_key=True)
    number = Column(Integer, CheckConstraint('number >= 1'), primary_key=True)
    created = Column(DateTime, default=datetime.now, nullable=False)
    published = Column(DateTime, default=datetime.now, nullable=False)
    vector = Column(LargeBinary(10485760))
    _bitmap = Column('bitmap', LargeBinary(10485760))
    thumbnail = Column(LargeBinary(1048576))

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
                self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
                self.issue.comic.title, self.issue.number, self.issue.title, self.page_number)

    def _get_bitmap(self):
        return self._bitmap

    def _set_bitmap(self, value):
        maxh = 200
        maxw = 200
        self._bitmap = value
        s = StringIO(value)
        im = Image.open(s)
        (w, h) = im.size
        if w > maxw or h > maxh:
            scale = min(float(maxw) / w, float(maxh) / h)
            neww = int(round(w * scale))
            newh = int(round(h * scale))
            im = im.convert('RGB').resize((neww, newh), Image.ANTIALIAS)
            s = StringIO()
            im.save(s, 'PNG', optimize=1)
        self.thumbnail = s.getvalue()

    bitmap = synonym('_bitmap', descriptor=property(_get_bitmap, _set_bitmap))

    @property
    def first(self):
        result = self.issue.comic.issues[0].pages[0]
        if result != self:
            return result
        else:
            return None

    @property
    def previous(self):
        if self.number > 1:
            return self.issue.pages[self.number - 2]
        elif self.issue_number > 1:
            return self.issue.comic.issues[self.issue_number - 2].pages[-1]
        else:
            return None

    @property
    def next(self):
        if self.number < self.issue.pages[-1].number:
            return self.issue.pages[self.number]
        elif self.issue_number < self.issue.comic.issues[-1].number:
            return self.issue.comic.issues[self.issue_number].pages[0]
        else:
            return None

    @property
    def last(self):
        result = self.issue.comic.issues[-1].pages[-1]
        if result != self:
            return result
        else:
            return None


class Issue(DeclarativeBase):
    """
    Comic issue definition.
    """

    __tablename__ = 'issues'

    comic_id = Column(Unicode(20), ForeignKey('comics.id'), primary_key=True)
    number = Column(Integer, CheckConstraint('number >= 1'), primary_key=True)
    title = Column(Unicode(100), nullable=False)
    description = Column(Unicode, default=u'', nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    pages = relationship('Page', backref='issue', order_by=[Page.number])

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
                self.comic_id, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
                self.comic.title, self.number, self.title)


class Comic(DeclarativeBase):
    """
    Comic definition.
    """

    __tablename__ = 'comics'

    id = Column(Unicode(20), primary_key=True)
    title = Column(Unicode(100), nullable=False, unique=True)
    description = Column(Unicode, default=u'', nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    author = Column(Unicode(100), ForeignKey('users.user_name'))
    issues = relationship('Issue', backref='comic', order_by=[Issue.number])

    def __repr__(self):
        return '<Comic: id=%s>' % self.id

    def __unicode__(self):
        return self.title

