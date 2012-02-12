# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
from datetime import datetime
import sys
import zipfile
import logging

from tg import cache
from sqlalchemy import Table, ForeignKey, ForeignKeyConstraint, CheckConstraint, Column, func, and_, or_
from sqlalchemy.types import Unicode, Integer, DateTime, LargeBinary
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from ratbot.model import DeclarativeBase, metadata, DBSession
from ratbot.model.auth import User
from PIL import Image
from pyPdf import PdfFileWriter, PdfFileReader
from pyPdf.generic import NameObject, createStringObject
import rsvg
import cairo
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
    _vector = Column('vector', LargeBinary(10485760))
    _vector_updated = Column('vector_updated', DateTime)
    _bitmap = Column('bitmap', LargeBinary(10485760))
    _bitmap_updated = Column('bitmap_updated', DateTime)
    _thumbnail = Column('thumbnail', LargeBinary(1048576))
    _thumbnail_updated = Column('thumbnail_updated', DateTime)

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
                self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
                self.issue.comic.title, self.issue.number, self.issue.title, self.page_number)

    def _get_thumbnail(self):
        THUMB_MAXWIDTH = 200
        THUMB_MAXHEIGHT = 200
        if not self.thumbnail_updated or self.thumbnail_updated < self.bitmap_updated:
            # Scale the bitmap down to a thumbnail
            s = StringIO(self.bitmap)
            im = Image.open(s)
            (w, h) = im.size
            if w > THUMB_MAXWIDTH or h > THUMB_MAXHEIGHT:
                scale = min(float(THUMB_MAXWIDTH) / w, float(THUMB_MAXHEIGHT) / h)
                w = int(round(w * scale))
                h = int(round(h * scale))
                im = im.convert('RGB').resize((w, h), Image.ANTIALIAS)
                s = StringIO()
                im.save(s, 'PNG', optimize=1)
            self.thumbnail = s.getvalue()
        return self._thumbnail

    def _set_thumbnail(self, value):
        thumbnail_cache = cache.get_cache('thumbnail', expire=3600)
        thumbnail_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        self._thumbnail = value
        if value:
            self._thumbnail_updated = datetime.now()
        else:
            self._thumbnail_updated = None

    def _get_thumbnail_updated(self):
        return self._thumbnail_updated

    def _set_thumbnail_updated(self):
        raise NotImplementedError

    def _get_bitmap(self):
        BITMAP_WIDTH = 900
        if not self.bitmap_updated or self.bitmap_updated < self.vector_updated:
            # Load the SVG file
            svg = rsvg.Handle()
            svg.write(self.vector)
            svg.close()
            # Convert vector to the main bitmap value
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, BITMAP_WIDTH, int(float(BITMAP_WIDTH) * svg.props.height / svg.props.width))
            context = cairo.Context(surface)
            context.scale(float(surface.get_width()) / svg.props.width, float(surface.get_height()) / svg.props.height)
            svg.render_cairo(context)
            s = StringIO()
            surface.write_to_png(s)
            self.bitmap = s.getvalue()
        return self._bitmap

    def _set_bitmap(self, value):
        bitmap_cache = cache.get_cache('bitmap', expire=3600)
        bitmap_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        self._bitmap = value
        if value:
            self._bitmap_updated = datetime.now()
        else:
            self._bitmap_updated = None
        # Invalidate the bitmap archive in the owning issue
        self.issue.archive = None

    def _get_bitmap_updated(self):
        return self._bitmap_updated

    def _set_bitmap_updated(self):
        raise NotImplementedError

    def _get_vector(self):
        return self._vector

    def _set_vector(self, value):
        vector_cache = cache.get_cache('vector', expire=3600)
        vector_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        self._vector = value
        if value:
            self._vector_updated = datetime.now()
        else:
            self._vector_updated = None
        # Invalidate the PDF in the owning issue
        self.issue.pdf = None

    def _get_vector_updated(self):
        return self._vector_updated

    def _set_vector_updated(self):
        raise NotImplementedError

    bitmap = synonym('_bitmap', descriptor=property(_get_bitmap, _set_bitmap))
    bitmap_updated = synonym('_bitmap_updated', descriptor=property(_get_bitmap_updated, _set_bitmap_updated))
    vector = synonym('_vector', descriptor=property(_get_vector, _set_vector))
    vector_updated = synonym('_vector_updated', descriptor=property(_get_vector_updated, _set_vector_updated))
    thumbnail = synonym('_thumbnail', descriptor=property(_get_thumbnail, _set_thumbnail))
    thumbnail_updated = synonym('_thumbnail_updated', descriptor=property(_get_thumbnail_updated, _set_thumbnail_updated))

    @property
    def first(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.issue.comic.id).\
            filter(Page.published <= datetime.now()).\
            order_by(Page.issue_number, Page.number).first()

    @property
    def previous(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.issue.comic.id).\
            filter(Page.published <= datetime.now()).\
            filter(or_(
                Page.issue_number < self.issue.number,
                and_(Page.issue_number == self.issue.number, Page.number < self.number)
            )).\
            order_by(Page.issue_number.desc(), Page.number.desc()).first()

    @property
    def next(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.issue.comic.id).\
            filter(Page.published <= datetime.now()).\
            filter(or_(
                Page.issue_number > self.issue.number,
                and_(Page.issue_number == self.issue.number, Page.number > self.number)
            )).\
            order_by(Page.issue_number, Page.number).first()

    @property
    def last(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.issue.comic.id).\
            filter(Page.published <= datetime.now()).\
            order_by(Page.issue_number.desc(), Page.number.desc()).first()


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
    _archive = Column('archive', LargeBinary(10485760))
    _archive_updated = Column('archive_updated', DateTime)
    _pdf = Column('pdf', LargeBinary(10485760))
    _pdf_updated = Column('pdf_updated', DateTime)

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
                self.comic_id, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
                self.comic.title, self.number, self.title)

    def invalidate(self):
        # Called whenever the pages change to expire the cached archive and PDF
        # columns
        self.archive = None
        self.pdf = None

    def _get_archive(self):
        if not self.archive_updated or self.archive_updated < self.published:
            if not self.published_pages:
                self.archive = None
            else:
                s = StringIO()
                # We don't bother with compression here as PNGs are already
                # compressed
                archive = zipfile.ZipFile(s, 'w', zipfile.ZIP_STORED)
                archive.comment = '%s - Issue #%d - %s\n\n%s' % (
                        self.comic.title,
                        self.number,
                        self.title,
                        self.description)
                for page in self.published_pages:
                    archive.writestr('%02d.png' % page.number, page.bitmap)
                archive.close()
                self.archive = s.getvalue()
        return self._archive

    def _set_archive(self, value):
        archive_cache = cache.get_cache('archive', expire=3600)
        archive_cache.remove_value(key=(self.comic_id, self.number))
        self._archive = value
        if value:
            self._archive_updated = datetime.now()
        else:
            self._archive_updated = None

    def _get_archive_updated(self):
        return self._archive_updated

    def _set_archive_updated(self, value):
        raise NotImplementedError

    def _get_pdf(self):
        PDF_DPI = 72.0
        if not self.pdf_updated or self.pdf_updated < self.published:
            if not self.published_pages:
                self.pdf = None
            else:
                # Use cairo to generate a PDF from each page's SVG. To create
                # the PDF surface we need the SVG's DPI and size. Here we
                # simply assume that all SVGs have the same DPI and size as the
                # first in the issue
                # XXX What if a page only has a bitmap?
                pdf_data = StringIO()
                for page in self.published_pages:
                    svg = rsvg.Handle()
                    svg.write(page.vector)
                    svg.close()
                    surface = cairo.PDFSurface(pdf_data,
                        PDF_DPI / svg.props.dpi_x * svg.props.width,
                        PDF_DPI / svg.props.dpi_y * svg.props.height)
                    context = cairo.Context(surface)
                    context.scale(PDF_DPI / svg.props.dpi_x, PDF_DPI / svg.props.dpi_y)
                    break
                for page in self.published_pages:
                    svg = rsvg.Handle()
                    svg.write(page.vector)
                    svg.close()
                    svg.render_cairo(context)
                    context.show_page()
                surface.finish()
                # Use PyPdf to rewrite the metadata on the file (cairo provides
                # no PDF metadata manipulation). This involves generating a new
                # PDF with new metadata and copying the pages over
                pdf_data.seek(0)
                pdf_in = PdfFileReader(pdf_data)
                pdf_out = PdfFileWriter()
                pdf_info = pdf_out._info.getObject()
                pdf_info.update(pdf_in.documentInfo)
                pdf_info.update({
                    NameObject('/Title'): createStringObject(u'%s - Issue #%d - %s' % (self.comic.title, self.number, self.title)),
                    NameObject('/Author'): createStringObject(self.comic.author.display_name if self.comic.author else u'Anonymous'),
                })
                for page in range(pdf_in.getNumPages()):
                    pdf_out.addPage(pdf_in.getPage(page))
                s = StringIO()
                pdf_out.write(s)
                self.pdf = s.getvalue()
        return self._pdf

    def _set_pdf(self, value):
        pdf_cache = cache.get_cache('pdf', expire=3600)
        pdf_cache.remove_value(key=(self.comic_id, self.number))
        self._pdf = value
        if value:
            self._pdf_updated = datetime.now()
        else:
            self._pdf_updated = None

    def _get_pdf_updated(self):
        return self._pdf_updated

    def _set_pdf_updated(self, value):
        raise NotImplementedError

    archive = synonym('_archive', descriptor=property(_get_archive, _set_archive))
    archive_updated = synonym('_archive_updated', descriptor=property(_get_archive_updated, _set_archive_updated))
    pdf = synonym('_pdf', descriptor=property(_get_pdf, _set_pdf))
    pdf_updated = synonym('_pdf_updated', descriptor=property(_get_pdf_updated, _set_pdf_updated))

    @property
    def published(self):
        try:
            return DBSession.query(func.max(Page.published)).\
                filter(Page.comic_id == self.comic_id).\
                filter(Page.issue_number == self.number).\
                filter(Page.published <= datetime.now()).one()[0]
        except NoResultFound:
            return None

    @property
    def published_pages(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.comic_id).\
            filter(Page.issue_number == self.number).\
            filter(Page.published <= datetime.now()).\
            order_by(Page.number).all()

    @property
    def first_page(self):
        return DBSession.query(Page).\
            filter(Page.comic_id == self.comic_id).\
            filter(Page.issue_number == self.number).\
            filter(Page.published <= datetime.now()).\
            order_by(Page.number).first()


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

    @property
    def published_issues(self):
        return DBSession.query(Issue).\
            join(Page).\
            filter(Issue.comic_id == self.id).\
            filter(Page.published <= datetime.now()).\
            distinct().\
            order_by(Issue.number).all()

    @property
    def first_issue(self):
        return DBSession.query(Issue).\
            join(Page).\
            filter(Issue.comic_id == self.id).\
            filter(Page.published <= datetime.now()).\
            distinct().\
            order_by(Issue.number).first()

    @property
    def latest_issue(self):
        return DBSession.query(Issue).\
            join(Page).\
            filter(Issue.comic_id == self.id).\
            filter(Page.published <= datetime.now()).\
            distinct().\
            order_by(Issue.number.desc()).first()

