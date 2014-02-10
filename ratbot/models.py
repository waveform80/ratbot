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
import tempfile
import shutil
import threading
import atexit
import logging
from datetime import datetime
from contextlib import closing
log = logging.getLogger(__name__)

import pytz
import rsvg
import cairo
import transaction
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
from zope.sqlalchemy import register
from pyramid.decorator import reify

from ratbot.zip import ZipFile, ZIP_STORED
from ratbot.locking import SELock


__all__ = [
    'FilesThread',
    'DBSession',
    'Base',
    'Comic',
    'Issue',
    'Page',
    'User',
    'utcnow',
    ]


# Global database session factory
DBSession = scoped_session(sessionmaker())
register(DBSession)

# SQLAlchemy mapper base class
Base = declarative_base()

# Maximum size of a page thumbnail
THUMB_RESOLUTION = (200, 300)

# Horizontal size to render bitmaps of a vector
BITMAP_WIDTH = 900

# The resolution to use when generating PDFs from vectors
PDF_DPI = 72.0

# The maximum size of temporary spools until they rollover onto the disk for
# backing storage
SPOOL_LIMIT = 1024*1024


class FilesThread(threading.Thread):
    """
    The singleton files thread is periodically woken up to check which files
    exist in the site.files dir, and remove any that don't have a corresponding
    entry in the database. It is woken up after any COMMIT or ROLLBACK
    operation that follows changes to any filename attribute.
    """
    def __init__(self):
        super(FilesThread, self).__init__()
        self.lock = SELock()
        self._event = threading.Event()
        self._changed = False
        self._change_lock = threading.Lock()
        self._terminated = False
        atexit.register(self.stop)
        self.start()

    def after_txn(self, session):
        self.clean()

    def clean(self):
        with self._change_lock:
            if self._changed:
                self._changed = False
                self._event.set()

    def changed(self):
        with self._change_lock:
            self._changed = True

    def run(self):
        try:
            while not self._terminated:
                if self._event.wait(1):
                    self._event.clear()
                    with self.lock.exclusive, transaction.manager:
                        files_dir = DBSession.info['site.files']
                        log.info('FileThread sweeping %s' % files_dir)
                        to_delete = set(
                                os.path.join(files_dir, f)
                                for f in os.listdir(files_dir)
                                if f.endswith(('.svg', '.png', '.pdf', '.zip'))
                                )
                        for page in DBSession.query(Page):
                            for filename in (
                                    page.vector_filename,
                                    page.bitmap_filename,
                                    page.thumbnail_filename,
                                    ):
                                if filename:
                                    to_delete.remove(filename)
                        for issue in DBSession.query(Issue):
                            for filename in (
                                    issue.archive_filename,
                                    issue.pdf_filename,
                                    ):
                                if filename:
                                    to_delete.remove(filename)
                        log.info('FileThread found %d files to remove' % len(to_delete))
                        for filename in to_delete:
                            try:
                                log.info('FileThread removing %s' % filename)
                                os.unlink(filename)
                            except IOError as e:
                                log.error('Failed to remove %s' % filename)
                                log.error(str(e))
        finally:
            # Need to close the session we've been using here as some DBAPI
            # implementations won't close our session back in the main thread
            DBSession.remove()

    def stop(self):
        self._terminated = True
        self.join()

FilesThread = FilesThread()


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


def filename_property(attr):
    "Makes a filename property which checks the directory in its setter"
    def getter(self):
        return getattr(self, attr)
    def setter(self, value):
        if value != getattr(self, attr):
            if value:
                files_dir = DBSession.info['site.files']
                value_dir, filename = os.path.split(value)
                if os.path.normpath(files_dir) != os.path.normpath(value_dir):
                    raise ValueError(
                        'Invalid directory: %s is not under %s' % (value, files_dir))
            setattr(self, attr, value)
            FilesThread.changed()
    return property(getter, setter)


def file_property(filename_attr, prefix='tmp', suffix='.tmp', create_method=None):
    "Makes a file-object property based on a filename_attr attribute"
    def getter(self):
        if create_method:
            getattr(self, create_method)()
        fname = getattr(self, filename_attr)
        if fname:
            return io.open(fname, 'rb')
    def setter(self, value):
        if value is None:
            setattr(self, filename_attr, None)
        else:
            with FilesThread.lock.shared:
                with tempfile.NamedTemporaryFile(
                        dir=DBSession.info['site.files'],
                        prefix=prefix,
                        suffix=suffix,
                        delete=False) as f:
                    shutil.copyfileobj(value, f)
                    setattr(self, filename_attr, f.name)
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
        ForeignKeyConstraint(
            ['comic_id', 'issue_number'],
            ['issues.comic_id', 'issues.number'],
            onupdate='CASCADE',
            ondelete='CASCADE',
            ),
        {},
        )

    comic_id = Column(Unicode(20), primary_key=True)
    issue_number = Column(Integer, primary_key=True, autoincrement=False)
    number = Column(Integer, CheckConstraint('number >= 1'), primary_key=True, autoincrement=False)

    _created = Column('created', DateTime, default=datetime.utcnow, nullable=False)
    created = synonym('_created', descriptor=tz_property('_created'))

    _published = Column('published', DateTime, default=datetime.utcnow, nullable=True)
    published = synonym('_published', descriptor=tz_property('_published'))

    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(UnicodeText, default='', nullable=False)

    _thumbnail = Column('thumbnail', Unicode(200))
    thumbnail_filename = synonym('_thumbnail', descriptor=filename_property('_thumbnail'))
    thumbnail_updated = updated_property('thumbnail_filename')
    thumbnail = file_property('thumbnail_filename', prefix='thumb_', suffix='.png',
            create_method='create_thumbnail')

    _bitmap = Column('bitmap', Unicode(200))
    bitmap_filename = synonym('_bitmap', descriptor=filename_property('_bitmap'))
    bitmap_updated = updated_property('bitmap_filename')
    bitmap = file_property('bitmap_filename', prefix='page_', suffix='.png',
            create_method='create_bitmap')

    _vector = Column('vector', Unicode(200))
    vector_filename = synonym('_vector', descriptor=filename_property('_vector'))
    vector_updated = updated_property('vector_filename')
    vector = file_property('vector_filename', prefix='page_', suffix='.svg')

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
            self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
            self.issue.comic.title, self.issue.number, self.issue.title, self.number)

    def create_thumbnail(self):
        # Ensure a bitmap exists to create the thumbnail from
        self.create_bitmap()
        if (
                self.bitmap_filename and
                (not self.thumbnail_filename or
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
                self.vector_filename and
                (not self.bitmap_filename or
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

    comic_id = Column(Unicode(20),
            ForeignKey('comics.id', onupdate='CASCADE', ondelete='CASCADE'),
            primary_key=True)
    number = Column(Integer, CheckConstraint('number >= 1'),
            primary_key=True, autoincrement=False)
    title = Column(Unicode(500), nullable=False)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(Unicode, default='', nullable=False)

    _created = Column('created', DateTime, default=datetime.utcnow, nullable=False)
    created = synonym('_created', descriptor=tz_property('_created'))

    _archive = Column('archive', Unicode(200))
    archive_filename = synonym('_archive', descriptor=filename_property('_archive'))
    archive_updated = updated_property('archive_filename')
    archive = file_property('archive_filename', prefix='issue_', suffix='.zip',
            create_method='create_archive')

    _pdf = Column('pdf', Unicode(200))
    pdf_filename = synonym('_pdf', descriptor=filename_property('_pdf'))
    pdf_updated = updated_property('pdf_filename')
    pdf = file_property('pdf_filename', prefix='issue_', suffix='.pdf',
            create_method='create_pdf')

    pages = relationship(
            Page, backref='issue', order_by=[Page.number],
            cascade='all, delete-orphan', passive_deletes=True)

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

    def create_archive(self):
        if not self.published_pages.count():
            self.archive = None
        elif (not self.archive_filename or self.archive_updated < self.published):
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
        elif (not self.pdf_filename or self.pdf_updated < self.published):
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
                        self.comic.author.name if self.comic.author else
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
    author_id = Column(Unicode(200),
            ForeignKey('users.id', onupdate='CASCADE', ondelete='RESTRICT'),
            nullable=False)
    markup = Column(Unicode(8), default='html', nullable=False)
    description = Column(UnicodeText, default='', nullable=False)

    _created = Column('created', DateTime, default=datetime.utcnow, nullable=False)
    created = synonym('_created', descriptor=tz_property('_created'))

    issues = relationship(
            Issue, backref='comic', order_by=[Issue.number],
            cascade='all, delete-orphan', passive_deletes=True)

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


# Notify the FilesThread about various occurrences
@event.listens_for(DBSession, 'after_rollback')
@event.listens_for(DBSession, 'after_commit')
def clean_after_txn(session):
    FilesThread.clean()

@event.listens_for(Page, 'after_insert')
@event.listens_for(Page, 'after_delete')
@event.listens_for(Issue, 'after_delete')
@event.listens_for(Comic, 'after_delete')
def changed_after_insdel(mapper, connection, target):
    FilesThread.changed()

from sqlite3 import Connection as SQLite3Connection

# Ensure SQLite uses foreign keys properly
@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

