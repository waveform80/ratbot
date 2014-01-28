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

# Python 3 compatibility
from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import io
import os
import os.path
import sys
import logging
import tempfile
import shutil
from datetime import datetime
from contextlib import closing

import pytz
import rsvg
import cairo
from PIL import Image
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import NameObject, createStringObject
from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    CheckConstraint,
    Column,
    Index,
    func,
    event,
    )
from sqlalchemy.types import (
    Boolean,
    Unicode,
    UnicodeText,
    Integer,
    DateTime,
    )
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    synonym,
    )
from sqlalchemy.orm.exc import (
    NoResultFound,
    MultipleResultsFound,
    )
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from zope.sqlalchemy import ZopeTransactionExtension
from pyramid.decorator import reify
from pyramid.threadlocal import get_current_registry

from ratbot.util import ZipFile, ZIP_STORED


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


__all__ = [
    'DBSession',
    'Base',
    'Comic',
    'Issue',
    'Page',
    'User',
    'utcnow',
    ]


# Maximum size of a page thumbnail
THUMB_RESOLUTION = (200, 300)

# Horizontal size to render bitmaps of a vector
BITMAP_WIDTH = 900

# The resolution to use when generating PDFs from vectors
PDF_DPI = 72.0

# The maximum size of temporary spools until they rollover onto the disk for
# backing storage
SPOOL_LIMIT = 1024*1024


# Ensure SQLite uses foreign keys properly
@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


def utcnow():
    "Returns the current UTC timestamp with a UTC timezone"
    return pytz.utc.localize(datetime.utcnow())


def tz_property(attr):
    "Makes a timezone aware property from an underlying datetime attribute"
    def getter(self):
        d = getattr(self, attr)
        if d is not None:
            if d.tzinfo is None:
                return pytz.utc.localize(d)
            else:
                return d.astimezone(pytz.utc)
    def setter(self, value):
        if value.tzinfo is None:
            setattr(self, attr, value)
        else:
            setattr(self, attr, value.astimezone(pytz.utc).replace(tzinfo=None))
    return property(getter, setter)


def file_property(filename_attr, create_method=None):
    "Makes a file-object property based on the filename_attr attribute"
    def getter(self):
        if create_method:
            getattr(self, create_method)()
        fname = getattr(self, filename_attr)
        if os.path.exists(fname):
            return io.open(fname, 'rb')
    def setter(self, value):
        fname = getattr(self, filename_attr)
        if value:
            fd, path = tempfile.mkstemp(dir=os.path.split(fname)[0])
            try:
                with io.open(fd, 'wb') as temp:
                    shutil.copyfileobj(value, temp)
            except:
                os.unlink(path)
                raise
            os.rename(path, fname)
        else:
            try:
                os.unlink(fname)
            except OSError:
                pass
    return property(getter, setter)


def updated_property(filename_attr):
    "Makes a file-last-modified property based on the filename_attr attribute"
    def getter(self):
        fname = getattr(self, filename_attr)
        if os.path.exists(fname):
            return datetime.utcfromtimestamp(os.stat(fname).st_mtime)
    return property(getter)


class Page(Base):
    """
    Represents one page of a comic issue. A Page belongs to exactly one Issue.
    """

    __tablename__ = 'pages'
    __table_args__ = (
        ForeignKeyConstraint(['comic_id', 'issue_number'], ['issues.comic_id', 'issues.number']),
        {},
        )

    comic_id = Column(Unicode(20), primary_key=True)
    issue_number = Column(Integer, primary_key=True)
    number = Column(
            Integer, CheckConstraint('number >= 1'), primary_key=True)
    _created = Column(
            'created', DateTime, default=datetime.utcnow, nullable=False)
    _published = Column(
            'published', DateTime, default=datetime.utcnow, nullable=True)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(UnicodeText, default='', nullable=False)

    created = synonym('_created', descriptor=tz_property('_created'))
    published = synonym('_published', descriptor=tz_property('_published'))

    thumbnail = file_property('thumbnail_filename', 'create_thumbnail')
    bitmap = file_property('bitmap_filename', 'create_bitmap')
    vector = file_property('vector_filename')

    thumbnail_updated = updated_property('thumbnail_filename')
    bitmap_updated = updated_property('bitmap_filename')
    vector_updated = updated_property('vector_filename')

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
            self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
            self.issue.comic.title, self.issue.number, self.issue.title, self.number)

    @reify
    def thumbnail_filename(self):
        return os.path.join(
            get_current_registry().settings['site.files'],
            'thumbs',
            '%s_%d_%d.png' % (self.comic_id, self.issue_number, self.number)
            )

    @reify
    def bitmap_filename(self):
        return os.path.join(
            get_current_registry().settings['site.files'],
            'bitmaps',
            '%s_%d_%d.png' % (self.comic_id, self.issue_number, self.number)
            )

    @reify
    def vector_filename(self):
        return os.path.join(
            get_current_registry().settings['site.files'],
            'vectors',
            '%s_%d_%d.svg' % (self.comic_id, self.issue_number, self.number)
            )

    def create_thumbnail(self):
        # Ensure a bitmap exists to create the thumbnail from
        self.create_bitmap()
        if (
                os.path.exists(self.bitmap_filename) and
                (not os.path.exists(self.thumbnail_filename) or
                    self.thumbnail_updated < self.bitmap_updated)
                ):
            with closing(self.bitmap) as source:
                img = Image.open(source)
                img.load()
            (tw, th) = THUMB_RESOLUTION
            (iw, ih) = img.size
            if iw > tw or ih > th:
                scale = min(tw / iw, th / ih)
                iw = int(round(iw * scale))
                ih = int(round(ih * scale))
                img = img.convert('RGB').resize((iw, ih), Image.ANTIALIAS)
                with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as stream:
                    img.save(stream, 'PNG', optimize=1)
                    stream.seek(0)
                    self.thumbnail = stream
            else:
                with closing(self.bitmap) as source:
                    self.thumbnail = source

    def create_bitmap(self):
        if (
                os.path.exists(self.vector_filename) and
                (not os.path.exists(self.bitmap_filename) or
                    self.bitmap_updated < self.vector_updated)
                ):
            # Load the SVG file with librsvg (using copyfileobj is a bit of a
            # dirty hack given that svg isn't a file-like object, but too
            # tempting given that it's got a simple write() method for loading)
            svg = rsvg.Handle()
            with closing(self.vector) as source:
                shutil.copyfileobj(source, svg)
            svg.close()
            # Convert the vector to a bitmap
            surface = cairo.ImageSurface(
                cairo.FORMAT_RGB24, BITMAP_WIDTH,
                int(BITMAP_WIDTH * svg.props.height / svg.props.width))
            context = cairo.Context(surface)
            # Paint the background of the surface white
            context.set_source_rgb(1.0, 1.0, 1.0)
            context.rectangle(0, 0, surface.get_width(), surface.get_height())
            context.fill()
            # Render the SVG onto the surface
            context.scale(
                    surface.get_width() / svg.props.width,
                    surface.get_height() / svg.props.height)
            svg.render_cairo(context)
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as stream:
                surface.write_to_png(stream)
                stream.seek(0)
                self.bitmap = stream

    @reify
    def first(self):
        return DBSession.query(Page).filter(
            (Page.comic_id == self.comic_id) &
            (Page.issue_number == self.issue_number) &
            (Page.published != None) &
            (Page.published <= utcnow())
            ).order_by(Page.number).first()

    @reify
    def last(self):
        return DBSession.query(Page).filter(
            (Page.comic_id == self.comic_id) &
            (Page.issue_number == self.issue_number) &
            (Page.published != None) &
            (Page.published <= utcnow())
            ).order_by(Page.number.desc()).first()

    @reify
    def prior(self):
        return DBSession.query(Page).filter(
            (Page.comic_id == self.comic_id) &
            (Page.issue_number == self.issue_number) &
            (Page.published != None) &
            (Page.published <= utcnow()) &
            (Page.number < self.number)
            ).order_by(Page.number.desc()).first()

    @reify
    def next(self):
        return DBSession.query(Page).filter(
            (Page.comic_id == self.issue.comic.id) &
            (Page.issue_number == self.issue_number) &
            (Page.published != None) &
            (Page.published <= utcnow()) &
            (Page.number > self.number)
            ).order_by(Page.number).first()


class Issue(Base):
    """
    Represents an issue of a comic (an issue has zero or more pages).
    """

    __tablename__= 'issues'

    comic_id = Column(Unicode(20), ForeignKey('comics.id'), primary_key=True)
    number = Column(Integer, CheckConstraint('number >= 1'), primary_key=True)
    title = Column(Unicode(500), nullable=False)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(Unicode, default='', nullable=False)
    _created = Column(
            'created', DateTime, default=datetime.utcnow, nullable=False)
    pages = relationship(Page, backref='issue', order_by=[Page.number])

    created = synonym('_created', descriptor=tz_property('_created'))

    archive = file_property('archive_filename', 'create_archive')
    pdf = file_property('pdf_filename', 'create_pdf')

    archive_updated = updated_property('archive_filename')
    pdf_updated = updated_property('pdf_filename')

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
            self.comic_id, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
            self.comic.title, self.number, self.title)

    def invalidate(self):
        # Called whenever the pages change to expire the cached archive and
        # PDF files
        self.archive = None
        self.pdf = None

    @reify
    def archive_filename(self):
        return os.path.join(
            get_current_registry().settings['site.files'],
            'archives',
            '%s_%d.zip' % (self.comic_id, self.number)
            )

    @reify
    def pdf_filename(self):
        return os.path.join(
            get_current_registry().settings['site.files'],
            'pdfs',
            '%s_%d.pdf' % (self.comic_id, self.number)
            )

    def create_archive(self):
        if not self.published_pages.count():
            self.archive = None
        elif (not os.path.exists(self.archive_filename) or
                self.archive_updated < self.published):
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as temp:
                # We don't bother with compression here as PNGs are already
                # compressed (and zip usually can't do any better)
                with ZipFile(temp, 'w', ZIP_STORED) as archive:
                    archive.comment = '%s - Issue #%d - %s\n\n%s' % (
                            self.comic.title,
                            self.number,
                            self.title,
                            self.description,
                            )
                    for page in self.published_pages:
                        page.create_bitmap()
                        archive.write(page.bitmap, '%02d.png' % page.number)
                temp.seek(0)
                self.archive = temp

    def create_pdf(self):
        if not self.published_pages.count():
            self.pdf = None
        elif (not os.path.exists(self.pdf_filename) or
                    self.pdf_updated < self.published):
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as temp:
                # Use cairo to generate a PDF for each page's SVG.
                # XXX To create the PDF surface we need the SVG's DPI and size.
                # Here we simply assume that all SVGs have the same DPI and the
                # size as the first in the issue
                # XXX What if a page only has a bitmap?
                for page in self.published_pages:
                    svg = rsvg.Handle()
                    shutil.copyfileobj(page.vector, svg)
                    svg.close()
                    surface = cairo.PDFSurface(temp,
                            PDF_DPI / svg.props.dpi_x * svg.props.width,
                            PDF_DPI / svg.props.dpi_y * svg.props.height)
                    context = cairo.Context(surface)
                    context.scale(
                            PDF_DPI / svg.props.dpi_x,
                            PDF_DPI / svg.props.dpi_y)
                    break
                for page in self.published_pages:
                    svg = rsvg.Handle()
                    shutil.copyfileobj(page.vector, svg)
                    svg.close()
                    svg.render_cairo(context)
                    context.show_page()
                surface.finish()
                # Use PyPdf to rewrite the metadata on the file (cairo provides
                # no PDF metadata manipulation). This involves generating a new
                # PDF with new metadata and copying the pages over
                temp.seek(0)
                pdf_in = PdfFileReader(temp)
                pdf_out = PdfFileWriter()
                pdf_info = pdf_out._info.getObject()
                pdf_info.update(pdf_in.documentInfo)
                pdf_info.update({
                    NameObject('/Title'): createStringObject('%s - Issue #%d - %s' % (
                        self.comic.title,
                        self.number,
                        self.title,
                        )),
                    NameObject('/Author'): createStringObject(
                        self.comic.author_user.display_name if self.comic.author_user else
                        'Anonymous'
                        ),
                    })
                for page in range(pdf_in.getNumPages()):
                    pdf_out.addPage(pdf_in.getPage(page))
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as temp:
                pdf_out.write(temp)
                temp.seek(0)
                self.pdf = temp

    @property
    def published_pages(self):
        return DBSession.query(Page).filter(
            (Page.comic_id == self.comic_id) &
            (Page.issue_number == self.number) &
            (Page.published != None) &
            (Page.published <= utcnow())
            )

    @reify
    def first_page(self):
        return self.published_pages.order_by(Page.number).first()

    @reify
    def last_page(self):
        return self.published_pages.order_by(Page.number.desc()).first()

    @reify
    def prior(self):
        return DBSession.query(Issue).join(Page).filter(
            (Issue.comic_id == self.comic_id) &
            (Issue.number < self.number) &
            (Page.published != None) &
            (Page.published <= utcnow())
            ).order_by(Issue.number.desc()).first()

    @reify
    def next(self):
        return DBSession.query(Issue).join(Page).filter(
            (Issue.comic_id == self.comic_id) &
            (Issue.number > self.number) &
            (Page.published != None) &
            (Page.published <= utcnow())
            ).order_by(Issue.number).first()

    @reify
    def published(self):
        # XXX Should be able to derive this from the published_pages query above
        try:
            return DBSession.query(func.max(Page.published)).filter(
                (Page.comic_id == self.comic_id) &
                (Page.issue_number == self.number) &
                (Page.published != None) &
                (Page.published <= utcnow())
                ).scalar()
        except NoResultFound:
            return None


class Comic(Base):
    """
    Represents a comic series, encapsulating a set of issues.
    """

    __tablename__ = 'comics'

    id = Column(Unicode(20), primary_key=True)
    title = Column(Unicode(200), nullable=False, unique=True)
    author_id = Column(
            Unicode(200), ForeignKey('users.id'), nullable=False)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(UnicodeText, default='', nullable=False)
    _created = Column(
            'created', DateTime, default=datetime.utcnow, nullable=False)
    issues = relationship(Issue, backref='comic', order_by=[Issue.number])

    def __repr__(self):
        return '<Comic: id=%s>' % self.id

    def __unicode__(self):
        return self.title

    @property
    def published_issues(self):
        return DBSession.query(Issue).join(Page).filter(
                (Issue.comic_id == self.id) &
                (Page.published != None) &
                (Page.published <= utcnow())
                )

    @property
    def first_issue(self):
        return self.published_issues.order_by(Issue.number).first()

    @property
    def latest_issue(self):
        return self.published_issues.order_by(Issue.number.desc()).first()


class User(Base):
    """
    Represents a comic reader or author on the site. All authentication is
    handled by third-party providers so here we only store the user's site
    authorizations.
    """

    __tablename__ = 'users'

    id = Column(Unicode(200), primary_key=True)
    name = Column(Unicode(200), nullable=False)
    admin = Column(Boolean, default=False, nullable=False)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(UnicodeText, default='', nullable=False)
    comics = relationship(Comic, backref='author')

    def __repr__(self):
        return '<User: id=%s>' % self.id

    def __unicode__(self):
        return self.name

    @reify
    def issues(self):
        return DBSession.query(Issue).join(Page).join(User).filter(
            (User.id == self.id)
            ).distinct()

