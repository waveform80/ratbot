# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
import os.path
import sys
from datetime import datetime
from contextlib import closing
import sys
import zipfile
import logging
import tempfile

from tg import cache, config
from sqlalchemy import ForeignKey, ForeignKeyConstraint, CheckConstraint, Column, func, and_, or_
from sqlalchemy.types import Unicode, Integer, DateTime
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from ratbot.model import DeclarativeBase, metadata, DBSession
from ratbot.model.auth import User
from PIL import Image
from pyPdf import PdfFileWriter, PdfFileReader
from pyPdf.generic import NameObject, createStringObject
from paste.deploy.converters import asint
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

    def __repr__(self):
        return '<Page: comic=%s, issue=%d, page=%d>' % (
                self.comic_id, self.issue_number, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s", page #%d' % (
                self.issue.comic.title, self.issue.number, self.issue.title, self.page_number)

    def _get_thumbnail(self):
        THUMB_MAXWIDTH = 200
        THUMB_MAXHEIGHT = 200
        if os.path.exists(self.bitmap_filename) and (not os.path.exists(self.thumbnail_filename) or self.thumbnail_updated < self.bitmap_updated):
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
        if os.path.exists(self.thumbnail_filename):
            with open(self.thumbnail_filename, 'rb') as f:
                return f.read()

    def _set_thumbnail(self, value):
        thumbnail_cache = cache.get_cache('thumbnail', expire=asint(config.get('cache_expire', 3600)))
        thumbnail_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        if value:
            tmpfd, tmppath = tempfile.mkstemp(dir=config['dbfiles_dir'])
            try:
                with closing(os.fdopen(tmpfd, 'wb')) as tmpfile:
                    tmpfile.write(value)
            except:
                os.unlink(tmppath)
                raise
            if sys.platform.startswith('win'):
                try:
                    os.unlink(self.thumbnail_filename)
                except OSError:
                    pass
            os.rename(tmppath, self.thumbnail_filename)
        else:
            try:
                os.unlink(self.thumbnail_filename)
            except OSError:
                pass

    def _get_bitmap(self):
        BITMAP_WIDTH = 900
        if os.path.exists(self.vector_filename) and (not os.path.exists(self.bitmap_filename) or self.bitmap_updated < self.vector_updated):
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
        if os.path.exists(self.bitmap_filename):
            with open(self.bitmap_filename, 'rb') as f:
                return f.read()

    def _set_bitmap(self, value):
        bitmap_cache = cache.get_cache('bitmap', expire=asint(config.get('cache_expire', 3600)))
        bitmap_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        if value:
            tmpfd, tmppath = tempfile.mkstemp(dir=config['dbfiles_dir'])
            try:
                with closing(os.fdopen(tmpfd, 'wb')) as tmpfile:
                    tmpfile.write(value)
            except:
                os.unlink(tmppath)
                raise
            if sys.platform.startswith('win'):
                try:
                    os.unlink(self.bitmap_filename)
                except OSError:
                    pass
            os.rename(tmppath, self.bitmap_filename)
        else:
            try:
                os.unlink(self.bitmap_filename)
            except OSError:
                pass

    def _get_vector(self):
        if os.path.exists(self.vector_filename):
            with open(self.vector_filename, 'rb') as f:
                return f.read()

    def _set_vector(self, value):
        vector_cache = cache.get_cache('vector', expire=asint(config.get('cache_expire', 3600)))
        vector_cache.remove_value(key=(self.comic_id, self.issue_number, self.number))
        if value:
            tmpfd, tmppath = tempfile.mkstemp(suffix='.svg', dir=config['dbfiles_dir'])
            try:
                with closing(os.fdopen(tmpfd, 'wb')) as tmpfile:
                    tmpfile.write(value)
            except:
                os.unlink(tmppath)
                raise
            if sys.platform.startswith('win'):
                try:
                    os.unlink(self.vector_filename)
                except OSError:
                    pass
            os.rename(tmppath, self.vector_filename)
        else:
            try:
                os.unlink(self.vector_filename)
            except OSError:
                pass

    bitmap = property(_get_bitmap, _set_bitmap)
    vector = property(_get_vector, _set_vector)
    thumbnail = property(_get_thumbnail, _set_thumbnail)

    @property
    def thumbnail_filename(self):
        return os.path.join(
            config['dbfiles_dir'],
            '%s_%d_%d_thumb.png' % (self.comic_id, self.issue_number, self.number)
        )

    @property
    def thumbnail_updated(self):
        if os.path.exists(self.thumbnail_filename):
            return datetime.fromtimestamp(os.stat(self.thumbnail_filename).st_mtime)

    @property
    def bitmap_filename(self):
        return os.path.join(
            config['dbfiles_dir'],
            '%s_%d_%d.png' % (self.comic_id, self.issue_number, self.number)
        )

    @property
    def bitmap_updated(self):
        if os.path.exists(self.bitmap_filename):
            return datetime.fromtimestamp(os.stat(self.bitmap_filename).st_mtime)

    @property
    def vector_filename(self):
        return os.path.join(
            config['dbfiles_dir'],
            '%s_%d_%d.svg' % (self.comic_id, self.issue_number, self.number)
        )

    @property
    def vector_updated(self):
        if os.path.exists(self.vector_filename):
            return datetime.fromtimestamp(os.stat(self.vector_filename).st_mtime)

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
        if self.pages and (not os.path.exists(self.archive_filename) or self.archive_updated < self.published):
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
        if os.path.exists(self.archive_filename):
            with open(self.archive_filename, 'rb') as f:
                return f.read()

    def _set_archive(self, value):
        archive_cache = cache.get_cache('archive', expire=asint(config.get('cache_expire', 3600)))
        archive_cache.remove_value(key=(self.comic_id, self.number))
        if value:
            tmpfd, tmppath = tempfile.mkstemp(dir=config['dbfiles_dir'])
            try:
                with closing(os.fdopen(tmpfd, 'wb')) as tmpfile:
                    tmpfile.write(value)
            except:
                os.unlink(tmppath)
                raise
            if sys.platform.startswith('win'):
                try:
                    os.unlink(self.archive_filename)
                except OSError:
                    pass
            os.rename(tmppath, self.archive_filename)
        else:
            try:
                os.unlink(self.archive_filename)
            except OSError:
                pass

    def _get_pdf(self):
        PDF_DPI = 72.0
        if self.pages and (not os.path.exists(self.pdf_filename) or self.pdf_updated < self.published):
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
                    NameObject('/Author'): createStringObject(self.comic.author_user.display_name if self.comic.author_user else u'Anonymous'),
                })
                for page in range(pdf_in.getNumPages()):
                    pdf_out.addPage(pdf_in.getPage(page))
                s = StringIO()
                pdf_out.write(s)
                self.pdf = s.getvalue()
        if os.path.exists(self.pdf_filename):
            with open(self.pdf_filename, 'rb') as f:
                return f.read()

    def _set_pdf(self, value):
        pdf_cache = cache.get_cache('pdf', expire=asint(config.get('cache_expire', 3600)))
        pdf_cache.remove_value(key=(self.comic_id, self.number))
        if value:
            tmpfd, tmppath = tempfile.mkstemp(dir=config['dbfiles_dir'])
            try:
                with closing(os.fdopen(tmpfd, 'wb')) as tmpfile:
                    tmpfile.write(value)
            except:
                os.unlink(tmppath)
                raise
            if sys.platform.startswith('win'):
                try:
                    os.unlink(self.pdf_filename)
                except OSError:
                    pass
            os.rename(tmppath, self.pdf_filename)
        else:
            try:
                os.unlink(self.pdf_filename)
            except OSError:
                pass

    archive = property(_get_archive, _set_archive)
    pdf = property(_get_pdf, _set_pdf)

    @property
    def archive_filename(self):
        return os.path.join(
            config['dbfiles_dir'],
            '%s_%d.zip' % (self.comic_id, self.number)
        )

    @property
    def archive_updated(self):
        if os.path.exists(self.archive_filename):
            return datetime.fromtimestamp(os.stat(self.archive_filename).st_mtime)

    @property
    def pdf_filename(self):
        return os.path.join(
            config['dbfiles_dir'],
            '%s_%d.pdf' % (self.comic_id, self.number)
        )

    @property
    def pdf_updated(self):
        if os.path.exists(self.pdf_filename):
            return datetime.fromtimestamp(os.stat(self.pdf_filename).st_mtime)

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

