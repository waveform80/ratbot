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
from collections import deque
log = logging.getLogger(__name__)

import pytz
import rsvg
import cairo
import transaction
from PIL import Image
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import NameObject, createStringObject
from sqlalchemy import (
    Table,
    ForeignKey,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    CheckConstraint,
    Column,
    func,
    event,
    text,
    )
from sqlalchemy.types import (
    Integer,
    Unicode,
    )
from sqlalchemy.orm import (
    relationship,
    synonym,
    )
from sqlalchemy.orm.exc import (
    NoResultFound,
    MultipleResultsFound,
    )
from sqlalchemy.schema import FetchedValue
from sqlalchemy.ext.declarative import declarative_base
from pyramid.decorator import reify
from pyramid.threadlocal import get_current_registry

from .licenses import License
from .zip import ZipFile, ZIP_STORED
from .locking import SELock
from .db_session import DBSession


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


# SQLAlchemy mapper base class
Base = declarative_base()
Base.metadata.reflect(DBSession.get_bind(), views=True)

# Horizontal size to render bitmaps of a vector
BITMAP_WIDTH = 900

# The maximum size of temporary spools until they rollover onto the disk for
# backing storage
SPOOL_LIMIT = 1024*1024

# Maximum size of a page thumbnail
THUMB_SIZE = (200, 300)

def create_mask():
    """
    Create a mask for fading out the bottom of extremely tall thumbnails which
    are cropped. As the thumbnail limits are fixed, this can be pre-calculated.
    """
    mask = Image.new('L', THUMB_SIZE, color=255)
    pa = mask.load()
    y_from = int(THUMB_SIZE[1] * 0.8)
    y_max = THUMB_SIZE[1]
    for y in range(y_from, THUMB_SIZE[1]):
        for x in range(THUMB_SIZE[0]):
            pa[x, y] = 255 - int(255 * (y - y_from) / (y_max - y_from))
    return mask

# Mask for fading out the bottom of extremely tall thumbnails which are cropped
THUMB_MASK = create_mask()
del create_mask


def adjacent(iterable, obj, key=None):
    """
    Given an *iterable*, and an object *obj*, return the subsequence from
    *iterable* consisting of the object prior to *obj*, *obj* itself, and the
    object following *obj*. In other words, return (prior, this, next). If
    *obj* is the first object in the sequence, prior will be None. If *obj* is
    the last object in the sequence, next will be None. If *obj* is not found
    in the sequence, the function will raise :exc:`ValueError`.

    If *key* is specified, it must be a callable which will return an object
    to match with *obj*.
    """
    if key is None:
        key = lambda x: x
    values = deque(maxlen=3)
    values.append(None)
    i = iter(iterable)
    try:
        values.append(next(i))
    except StopIteration:
        raise ValueError("empty iterable")
    try:
        values.append(next(i))
        while True:
            if key(values[1]) is obj:
                return values
            values.append(next(i))
    except StopIteration:
        values.append(None)
    if key(values[1]) is obj:
        return values
    raise ValueError("%r did not occur in iterable" % obj)


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
        self.daemon = True
        self._event = threading.Event()
        self._changed = False
        self._change_lock = threading.Lock()
        self._terminated = False
        atexit.register(self.stop)
        self.start()

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
                                if f.endswith(('.svg', '.png', '.pdf', '.zip', '.jpg'))
                                )
                        for user in DBSession.query(User):
                            for filename in (
                                    user.bitmap_filename,
                                    ):
                                if filename:
                                    to_delete.remove(filename)
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

    __table__ = Table('pages', Base.metadata,
            # ... all other columns reflected
            Column('prior_page_number', server_onupdate=FetchedValue()),
            Column('next_page_number', server_onupdate=FetchedValue()),
            PrimaryKeyConstraint('comic_id', 'issue_number', 'page_number'),
            ForeignKeyConstraint(
                ['comic_id', 'issue_number'],
                ['issues.comic_id', 'issues.issue_number'],
                onupdate='CASCADE', ondelete='CASCADE'),
            extend_existing=True
            )

    _created = __table__.c.created
    created = synonym('_created', descriptor=tz_property('_created'))

    _published = __table__.c.published
    published = synonym('_published', descriptor=tz_property('_published'))

    _thumbnail = __table__.c.thumbnail
    thumbnail_filename = synonym('_thumbnail', descriptor=filename_property('_thumbnail'))
    thumbnail_updated = updated_property('thumbnail_filename')
    thumbnail = file_property('thumbnail_filename', prefix='thumb_', suffix='.png',
            create_method='create_thumbnail')

    _bitmap = __table__.c.bitmap
    bitmap_filename = synonym('_bitmap', descriptor=filename_property('_bitmap'))
    bitmap_updated = updated_property('bitmap_filename')
    bitmap = file_property('bitmap_filename', prefix='page_', suffix='.png',
            create_method='create_bitmap')

    _vector = __table__.c.vector
    vector_filename = synonym('_vector', descriptor=filename_property('_vector'))
    vector_updated = updated_property('vector_filename')
    vector = file_property('vector_filename', prefix='page_', suffix='.svg')

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
            self.comic_id, self.issue_number, self.page_number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
            self.issue.comic.title, self.issue.issue_number, self.issue.title, self.page_number)

    def create_thumbnail(self):
        # Ensure a bitmap exists to create the thumbnail from
        self.create_bitmap()
        if (
                self.bitmap_filename and
                (not self.thumbnail_filename or
                    self.thumbnail_updated < self.bitmap_updated)
                ):
            with closing(self.bitmap) as source:
                image = Image.open(source)
                image.load()
            scale = THUMB_SIZE[0] / image.size[0]
            tsize = (THUMB_SIZE[0], int(image.size[1] * scale))
            if image.size[0] <= THUMB_SIZE[0] and image.size[1] <= THUMB_SIZE[1]:
                thumb = image
            elif tsize[1] > (THUMB_SIZE[1] * 1.2):
                # Image is way over the defined height limit (by more than 20%).
                # Resize to the defined thumb width, crop to the thumb height,
                # then use the pre-calculated mask to fade out the bottom of
                # the image
                thumb = image.resize(tsize, Image.ANTIALIAS).crop((0, 0) + THUMB_SIZE)
                thumb.putalpha(THUMB_MASK)
            elif (image.size[1] * scale) <= THUMB_SIZE[1]:
                # Image fits nicely within defined thumbnail limits; resize
                # normally
                thumb = image.resize(tsize, Image.ANTIALIAS)
            else:
                # Image is slightly over-height, but no more than 20%. In this
                # case we allow the width to contract to preserve full height
                # of the image in the preview
                tsize = (int(image.size[0] * (THUMB_SIZE[1] / image.size[1])), THUMB_SIZE[1])
                thumb = image.resize(tsize, Image.ANTIALIAS)
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as stream:
                thumb.save(stream, 'PNG', optimize=1)
                stream.seek(0)
                self.thumbnail = stream

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
    def prior_page(self):
        if self.prior_page_number:
            return DBSession.query(Page).get(
                    (self.comic_id, self.issue_number, self.prior_page_number)
                    )

    @reify
    def next_page(self):
        if self.next_page_number:
            return DBSession.query(Page).get(
                    (self.comic_id, self.issue_number, self.next_page_number)
                    )

    @reify
    def is_published(self):
        return self.published is not None and self.published <= utcnow()


class Issue(Base):
    """
    Represents an issue of a comic (an issue has zero or more pages).
    """

    __table__ = Table('issues', Base.metadata,
            # ... all other columns reflected
            Column('published', server_onupdate=FetchedValue()),
            Column('prior_issue_number', server_onupdate=FetchedValue()),
            Column('next_issue_number', server_onupdate=FetchedValue()),
            Column('first_page_number', server_onupdate=FetchedValue()),
            Column('last_page_number', server_onupdate=FetchedValue()),
            Column('page_count', server_onupdate=FetchedValue()),
            PrimaryKeyConstraint('comic_id', 'issue_number'),
            ForeignKeyConstraint(
                ['comic_id'], ['comics.comic_id'],
                onupdate='CASCADE', ondelete='CASCADE'),
            extend_existing=True
            )

    _created = __table__.c.created
    created = synonym('_created', descriptor=tz_property('_created'))

    _archive = __table__.c.archive
    archive_filename = synonym('_archive', descriptor=filename_property('_archive'))
    archive_updated = updated_property('archive_filename')
    archive = file_property('archive_filename', prefix='issue_', suffix='.zip',
            create_method='create_archive')

    _pdf = __table__.c.pdf
    pdf_filename = synonym('_pdf', descriptor=filename_property('_pdf'))
    pdf_updated = updated_property('pdf_filename')
    pdf = file_property('pdf_filename', prefix='issue_', suffix='.pdf',
            create_method='create_pdf')

    pages = relationship(
            Page, backref='issue', order_by=[Page.page_number],
            cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
            self.comic_id, self.issue_number)

    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
            self.comic.title, self.issue_number, self.title)

    def invalidate(self):
        # Called whenever the pages change to expire the cached archive and
        # PDF files
        self.archive = None
        self.pdf = None

    def create_archive(self):
        if not self.published:
            self.archive = None
        elif (not self.archive_filename or self.archive_updated < self.published):
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as temp:
                # We don't bother with compression here as PNGs are already
                # compressed (and zip usually can't do any better)
                with ZipFile(temp, 'w', ZIP_STORED) as archive:
                    archive.comment = ('%s - Issue #%d - %s\n\n%s' % (
                            self.comic.title,
                            self.issue_number,
                            self.title,
                            self.description,
                            )).encode('utf-8')
                    page = self.first_page
                    while page:
                        page.create_bitmap()
                        archive.write(page.bitmap, '%02d.png' % page.page_number)
                        page = page.next_page
                temp.seek(0)
                self.archive = temp

    def create_pdf(self):
        if not self.published:
            self.pdf = None
        elif (not self.pdf_filename or self.pdf_updated < self.published):
            with tempfile.SpooledTemporaryFile(SPOOL_LIMIT) as temp:
                # Create an output PDF surface with an arbitrary size (the
                # size doesn't matter as we'll set it independently for each
                # page below)
                surface = cairo.PDFSurface(temp, 144.0, 144.0)
                context = cairo.Context(surface)
                page = self.first_page
                while page:
                    context.save()
                    try:
                        # Render the page's vector image if it has one
                        if page.vector_filename:
                            svg = rsvg.Handle()
                            shutil.copyfileobj(page.vector, svg)
                            svg.close()
                            surface.set_size(
                                svg.props.width / svg.props.dpi_x * 72.0,
                                svg.props.height / svg.props.dpi_y * 72.0)
                            context.scale(
                                72.0 / svg.props.dpi_x,
                                72.0 / svg.props.dpi_y)
                            svg.render_cairo(context)
                        # Otherwise, render the page's bitmap image (NOTE we
                        # assume all bitmaps are 96dpi here)
                        else:
                            img = cairo.ImageSurface.create_from_png(page.bitmap)
                            surface.set_size(
                                img.get_width() / 96.0 * 72.0,
                                img.get_height() / 96.0 * 72.0)
                            context.scale(72.0 / 96.0, 72.0 / 96.0)
                            context.set_source_surface(img)
                            context.paint()
                        context.show_page()
                    finally:
                        context.restore()
                    page = page.next_page
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
                        self.issue_number,
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

    @reify
    def first_page(self):
        if self.first_page_number:
            return DBSession.query(Page).get(
                    (self.comic_id, self.issue_number, self.first_page_number)
                    )

    @reify
    def last_page(self):
        if self.last_page_number:
            return DBSession.query(Page).get(
                    (self.comic_id, self.issue_number, self.last_page_number)
                    )

    @reify
    def prior_issue(self):
        if self.prior_issue_number:
            return DBSession.query(Issue).get(
                    (self.comic_id, self.prior_issue_number)
                    )

    @reify
    def next_issue(self):
        if self.next_issue_number:
            return DBSession.query(Issue).get(
                    (self.comic_id, self.next_issue_number)
                    )


class Comic(Base):
    """
    Represents a comic series, encapsulating a set of issues.
    """

    __table__ = Table('comics', Base.metadata,
            # ... all other columns reflected
            Column('first_issue_number', server_onupdate=FetchedValue()),
            Column('last_issue_number', server_onupdate=FetchedValue()),
            Column('issue_count', server_onupdate=FetchedValue()),
            Column('latest_publication', server_onupdate=FetchedValue()),
            PrimaryKeyConstraint('comic_id'),
            ForeignKeyConstraint(
                ['author_id'], ['users.user_id'],
                onupdate='CASCADE', ondelete='RESTRICT'),
            extend_existing=True
            )

    _created = __table__.c.created
    created = synonym('_created', descriptor=tz_property('_created'))

    issues = relationship(
            Issue, backref='comic', order_by=[Issue.issue_number],
            cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return '<Comic: comic_id=%s>' % self.comic_id

    def __unicode__(self):
        return self.title

    @property
    def first_issue(self):
        return DBSession.query(Issue).get((self.comic_id, self.first_issue_number))

    @property
    def last_issue(self):
        return DBSession.query(Issue).get((self.comic_id, self.last_issue_number))

    def _get_license(self):
        return get_current_registry()['licenses']()[self.license_id]
    def _set_license(self, value):
        assert isinstance(value, License)
        self.license_id = value.id
    license = property(_get_license, _set_license)


class User(Base):
    """
    Represents a comic reader or author on the site. All authentication is
    handled by third-party providers so here we only store the user's site
    authorizations.
    """

    __table__ = Table('users', Base.metadata,
            PrimaryKeyConstraint('user_id'),
            extend_existing=True
            )

    _bitmap = __table__.c.bitmap
    bitmap_filename = synonym('_bitmap', descriptor=filename_property('_bitmap'))
    bitmap_updated = updated_property('bitmap_filename')
    bitmap = file_property('bitmap_filename', prefix='user_', suffix='.jpg')

    comics = relationship(Comic, backref='author')

    def __repr__(self):
        return '<User: user_id=%s>' % self.user_id

    def __unicode__(self):
        return self.name

    @reify
    def issues(self):
        return DBSession.query(Issue).join(Page).join(User).filter(
            (User.user_id == self.user_id)
            ).distinct()


# Notify the FilesThread about various occurrences
@event.listens_for(DBSession, 'after_rollback')
@event.listens_for(DBSession, 'after_commit')
def clean_after_txn(session):
    FilesThread.clean()

@event.listens_for(User, 'after_insert')
@event.listens_for(User, 'after_update')
@event.listens_for(User, 'after_delete')
@event.listens_for(Page, 'after_insert')
@event.listens_for(Page, 'after_update')
@event.listens_for(Page, 'after_delete')
@event.listens_for(Issue, 'after_delete')
@event.listens_for(Comic, 'after_delete')
def changed_after_insdel(mapper, connection, target):
    FilesThread.changed()

