# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
from datetime import datetime
import sys

from sqlalchemy import Table, ForeignKey, ForeignKeyConstraint, Column
from sqlalchemy.types import Unicode, Integer, DateTime
from sqlalchemy.orm import relationship, synonym
from ratbot.model import DeclarativeBase, metadata, DBSession

__all__ = ['Comic', 'Issue', 'Page']


class Comic(DeclarativeBase):
    """
    Comic definition.
    """

    __tablename__ = 'comics'

    id = Column(Unicode(16), primary_key=True)
    title = Column(Unicode(256))
    created = Column(DateTime, default=datetime.now)
    author = Column(Unicode(128), ForeignKey('users.user_name'))
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

    comic_id = Column(Unicode(16), ForeignKey('comics.id'), primary_key=True)
    number = Column(Integer, primary_key=True)
    title = Column(Unicode(256))
    created = Column(DateTime, default=datetime.now)
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

    comic_id = Column(Unicode(16), primary_key=True)
    issue_number = Column(Integer, primary_key=True)
    number = Column(Integer, primary_key=True)
    created = Column(DateTime, default=datetime.now)
    published = Column(DateTime, default=datetime.now)
    filename = Column(Unicode(256))

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
                self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
                self.issue.comic.title, self.issue.number, self.issue.title, self.page_number)
