# -*- coding: utf-8 -*-
"""Comic Controller"""

from datetime import datetime
from tg import cache, config, expose, abort, request, response
from tg.i18n import ugettext as _, lazy_ugettext as l_
from tg.controllers.util import etag_cache
from repoze.what import predicates
from paste.deploy.converters import asint

from ratbot.lib.base import BaseController
from ratbot.model import DBSession, Comic, Issue, Page
from sqlalchemy.orm.exc import NoResultFound

__all__ = ['ComicController']

class ComicController(BaseController):
    """
    The comic controller for the ratbot application.
    """
    @expose('ratbot.templates.comics')
    def index(self):
        return dict(
            method='comics',
            comics=DBSession.query(Comic).order_by(Comic.id),
        )

    @expose('ratbot.templates.comic')
    def view(self, comic, issue, page):
        issue = int(issue)
        page = int(page)
        try:
            page = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).one()
            return dict(
                method='comic',
                comics=DBSession.query(Comic).order_by(Comic.title),
                page=page
            )
        except NoResultFound:
            abort(404)

    @expose(content_type='image/png')
    def thumb(self, comic, issue, page):
        issue = int(issue)
        page = int(page)
        def get_value():
            p = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return (p.thumbnail, p.thumbnail_updated)
        thumbnail_cache = cache.get_cache('thumbnail', expire=asint(config.get('cache_expire', 3600)))
        try:
            (thumbnail, thumbnail_updated) = thumbnail_cache.get_value(
                key=(comic, issue, page),
                createfunc=get_value,
            )
            if thumbnail_updated:
                etag_cache(thumbnail_updated.isoformat())
                response.last_modified = thumbnail_updated
            return thumbnail
        except NoResultFound:
            abort(404)

    @expose(content_type='image/png')
    def png(self, comic, issue, page):
        issue = int(issue)
        page = int(page)
        def get_value():
            p = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return (p.bitmap, p.bitmap_updated)
        bitmap_cache = cache.get_cache('bitmap', expire=asint(config.get('cache_expire', 3600)))
        try:
            (bitmap, bitmap_updated) = bitmap_cache.get_value(
                key=(comic, issue, page),
                createfunc=get_value,
            )
            if bitmap_updated:
                etag_cache(bitmap_updated.isoformat())
                response.last_modified = bitmap_updated
            return bitmap
        except NoResultFound:
            abort(404)

    @expose(content_type='image/svg+xml')
    def svg(self, comic, issue, page):
        issue = int(issue)
        page = int(page)
        def get_value():
            p = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return (p.vector, p.vector_updated)
        vector_cache = cache.get_cache('vector', expire=asint(config.get('cache_expire', 3600)))
        try:
            (vector, vector_updated) = vector_cache.get_value(
                key=(comic, issue, page),
                createfunc=get_value,
            )
            if vector_updated:
                etag_cache(vector_updated.isoformat())
                response.last_modified = vector_updated
            return vector
        except NoResultFound:
            abort(404)

    @expose(content_type='application/pdf')
    def pdf(self, comic, issue):
        issue = int(issue)
        def get_value():
            i = DBSession.query(Issue).\
                filter(Issue.comic_id==comic).\
                filter(Issue.number==issue).one()
            return (i.pdf, i.pdf_updated)
        response.headers['Content-Disposition'] = 'attachment;filename=%s-%s.pdf' % (comic, issue)
        pdf_cache = cache.get_cache('pdf', expire=asint(config.get('cache_expire', 3600)))
        try:
            (pdf, pdf_updated) = pdf_cache.get_value(
                key=(comic, issue),
                createfunc=get_value,
            )
            if pdf_updated:
                etag_cache(pdf_updated.isoformat())
                response.last_modified = pdf_updated
            return pdf
        except NoResultFound:
            abort(404)

    @expose(content_type='application/zip')
    def archive(self, comic, issue):
        issue = int(issue)
        def get_value():
            i = DBSession.query(Issue).\
                filter(Issue.comic_id==comic).\
                filter(Issue.number==issue).one()
            return (i.archive, i.archive_updated)
        response.headers['Content-Disposition'] = 'attachment;filename=%s-%s.zip' % (comic, issue)
        archive_cache = cache.get_cache('archive', expire=asint(config.get('cache_expire', 3600)))
        try:
            (archive, archive_updated) = archive_cache.get_value(
                key=(comic, issue),
                createfunc=get_value,
            )
            if archive_updated:
                etag_cache(archive_updated.isoformat())
                response.last_modified = archive_updated
            return archive
        except NoResultFound:
            abort(404)
