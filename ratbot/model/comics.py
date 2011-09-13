# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
from datetime import datetime
import sys

from sqlalchemy import Table, ForeignKey, ForeignKeyConstraint, Column
from sqlalchemy.types import Unicode, Integer, DateTime, LargeBinary
from sqlalchemy.orm import relationship, synonym
from ratbot.model import DeclarativeBase, metadata, DBSession

__all__ = ['Comic', 'Issue', 'Page']


class Comic(DeclarativeBase):
    """
    Comic definition.
    """

    __tablename__ = 'comics'

    id = Column(Unicode(20), primary_key=True)
    title = Column(Unicode(100), nullable=False, unique=True)
    description = Column(Unicode, default='', nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    author = Column(Unicode(100), ForeignKey('users.user_name'))
    issues = relationship('Issue', backref='comic')

    def __repr__(self):
        return '<Comic: id=%s>' % self.id

    def __unicode__(self):
        return self.title


class Issue(DeclarativeBase):
    """
    Comic issue definition.
    """

    __tablename__ = 'issues'

    comic_id = Column(Unicode(20), ForeignKey('comics.id'), primary_key=True)
    number = Column(Integer, primary_key=True)
    title = Column(Unicode(100), nullable=False)
    description = Column(Unicode, default='', nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    pages = relationship('Page', backref='issue')

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
                self.comic_id, self.number)


    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
                self.comic.title, self.number, self.title)


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
    number = Column(Integer, primary_key=True)
    created = Column(DateTime, default=datetime.now, nullable=False)
    published = Column(DateTime, default=datetime.now, nullable=False)
    vector = Column(LargeBinary(10485760))
    bitmap = Column(LargeBinary(10485760))
    thumbnail = Column(LargeBinary(1048576))

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
                self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
                self.issue.comic.title, self.issue.number, self.issue.title, self.page_number)
