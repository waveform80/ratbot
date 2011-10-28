# -*- coding: utf-8 -*-
"""
Comic model.
"""
import os
from datetime import datetime
import sys
import zipfile

from sqlalchemy import Table, ForeignKey, ForeignKeyConstraint, CheckConstraint, Column, func
from sqlalchemy.types import Unicode, Integer, DateTime, LargeBinary
from sqlalchemy.orm import relationship, synonym
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
        self._bitmap = value
        # Scale the bitmap down to a thumbnail
        THUMB_MAXWIDTH = 200
        THUMB_MAXHEIGHT = 200
        s = StringIO(value)
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
        # Regenerate the issue's archive
        self.issue._generate_archive()

    def _get_vector(self):
        return self._vector

    def _set_vector(self, value):
        self._vector = value
        # Load the SVG file
        svg = rsvg.Handle()
        svg.write(value)
        svg.close()
        # Convert vector to the main bitmap value
        BITMAP_WIDTH = 900
        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, BITMAP_WIDTH, int(float(BITMAP_WIDTH) * svg.props.height / svg.props.width))
        context = cairo.Context(surface)
        context.scale(float(surface.get_width()) / svg.props.width, float(surface.get_height()) / svg.props.height)
        svg.render_cairo(context)
        s = StringIO()
        surface.write_to_png(s)
        self.bitmap = s.getvalue()
        # Regenerate the issue's PDF
        self.issue._generate_pdf()

    bitmap = synonym('_bitmap', descriptor=property(_get_bitmap, _set_bitmap))

    @property
    def first(self):
        result = self.issue.comic.issues[0].published_pages[0]
        if result != self:
            return result
        else:
            return None

    @property
    def previous(self):
        if self.number > 1:
            return self.issue.published_pages[self.number - 2]
        elif self.issue_number > 1:
            return self.issue.comic.issues[self.issue_number - 2].published_pages[-1]
        else:
            return None

    @property
    def next(self):
        if self.number < self.issue.published_pages[-1].number:
            return self.issue.published_pages[self.number]
        elif self.issue_number < self.issue.comic.issues[-1].number:
            return self.issue.comic.issues[self.issue_number].published_pages[0]
        else:
            return None

    @property
    def last(self):
        result = self.issue.comic.issues[-1].published_pages[-1]
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
    archive = Column(LargeBinary(10485760))
    pdf = Column(LargeBinary(10485760))

    def __repr__(self):
        return '<Issue: comic=%s, issue=%d>' % (
                self.comic_id, self.number)

    def __unicode__(self):
        return '%s, issue #%d, "%s"' % (
                self.comic.title, self.number, self.title)

    def _generate_archive(self):
        s = StringIO()
        # We don't bother with compression here as PNGs are already compressed
        archive = zipfile.ZipFile(s, 'w', zipfile.ZIP_STORED)
        archive.comment = '%s - Issue #%d - %s\n\n%s' % (self.comic.title, self.number, self.title, self.description)
        for page in self.published_pages:
            archive.writestr('%02d.png' % page.number, page.bitmap)
        self.archive = s.getvalue()

    def _generate_pdf(self):
        PDF_DPI = 72.0
        # Use cairo to generate a PDF from each page's SVG
        # XXX What if a page only has a bitmap?
        s = StringIO()
        surface = cairo.PDFSurface(s, PDF_DPI / svg.props.dpi_x * svg.props.width, PDF_DPI / svg.props.dpi_y * svg.props.height)
        context = cairo.Context(surface)
        context.scale(PDF_DPI / svg.props.dpi_x, PDF_DPI / svg.props.dpi_y)
        for page in self.published_pages:
            svg = rsvg.Handle()
            svg.write(page.vector)
            svg.close()
            svg.render_cairo(context)
            svg.show_page()
        surface.finish()
        # Use PyPdf to rewrite the metadata on the file (cairo provides no PDF
        # metadata manipulation). This involves generating a new PDF with new
        # metadata and copying the pages over
        s.seek(0)
        pdf_in = PdfFileReader(s)
        pdf_out = PdfFileWriter()
        pdf_info = pdf_out._info.getObject()
        pdf_info.update({
            NameObject('/Title'): createStringObject(u'%s - Issue #%d - %s' % (self.comic.title, self.number, self.title)),
            NameObject('/Author'): createStringObject(self.comic.author.display_name),
            NameObject('/Subject'): createStringObject(pdf_in.documentInfo.subject),
            NameObject('/Creator'): createStringObject(pdf_in.documentInfo.creator),
            NameObject('/Producer'): createStringObject(pdf_in.documentInfo.producer),
        })
        for page in range(pdf_in.getNumPages()):
            pdf_out.addPage(pdf_in.getPage(page))
        t = StringIO()
        pdf_out.write(t)
        self.pdf = t.getvalue()

    @property
    def published(self):
        return DBSession.query(func.max(Page.published)).\
            filter(Page.comic_id==self.comic_id).\
            filter(Page.issue_number==self.numebr).\
            filter(Page.published<=datetime.now()).one()

    @property
    def published_pages(self):
        return DBSession.query(Page).\
            filter(Page.comic_id==self.comic_id).\
            filter(Page.issue_number==self.number).\
            filter(Page.published<=datetime.now()).\
            order_by(Page.number).all()


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
    archive = Column(LargeBinary(10485760))

    @property
    def zip(self):
        pass

    @property
    def pdf(self):
        pass

    def __repr__(self):
        return '<Comic: id=%s>' % self.id

    def __unicode__(self):
        return self.title

