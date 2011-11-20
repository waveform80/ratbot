# -*- coding: utf-8 -*-
"""Comic Controller"""

from datetime import datetime
from tg import expose, abort, request, response
from tg.i18n import ugettext as _, lazy_ugettext as l_
from repoze.what import predicates

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
        try:
            return dict(
                method='comic',
                comics=DBSession.query(Comic).order_by(Comic.title),
                page=DBSession.query(Page).\
                    filter(Page.comic_id==comic).\
                    filter(Page.issue_number==issue).\
                    filter(Page.number==page).one(),
            )
        except NoResultFound:
            abort(404)

    @expose(content_type='image/png')
    def thumb(self, comic, issue, page):
        try:
            page = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return page.thumbnail
        except NoResultFound:
            abort(404)

    @expose(content_type='image/png')
    def png(self, comic, issue, page):
        try:
            page = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return page.bitmap
        except NoResultFound:
            abort(404)

    @expose(content_type='image/svg+xml')
    def svg(self, comic, issue, page):
        try:
            page = DBSession.query(Page).\
                filter(Page.comic_id==comic).\
                filter(Page.issue_number==issue).\
                filter(Page.number==page).\
                filter(Page.published<=datetime.now()).one()
            return page.vector
        except NoResultFound:
            abort(404)

    @expose(content_type='application/pdf')
    def pdf(self, comic, issue):
        response.headers['Content-Disposition'] = 'attachment;filename=%s-%s.pdf' % (comic, issue)
        try:
            issue = DBSession.query(Issue).\
                filter(Issue.comic_id==comic).\
                filter(Issue.number==issue).one()
            return issue.pdf
        except NoResultFound:
            abort(404)

    @expose(content_type='application/zip')
    def archive(self, comic, issue):
        response.headers['Content-Disposition'] = 'attachment;filename=%s-%s.zip' % (comic, issue)
        try:
            issue = DBSession.query(Issue).\
                filter(Issue.comic_id==comic).\
                filter(Issue.number==issue).one()
            return issue.archive
        except NoResultFound:
            abort(404)
