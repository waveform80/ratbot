# -*- coding: utf-8 -*-
"""Comic Controller"""

import datetime
from tg import expose, validate, flash, require, url, request, redirect, tmpl_context
from tg.i18n import ugettext as _, lazy_ugettext as l_
from repoze.what import predicates

from ratbot.lib.base import BaseController
from ratbot.widgets.comics import new_page_form, new_comic_form, alter_comic_form
from ratbot.model import DBSession, metadata, Comic, Issue, Page

__all__ = ['RootController']

class ComicController(BaseController):
    """
    The comic controller for the ratbot application.
    """
    @expose('ratbot.templates.comics')
    def index(self):
        return dict(page='comics')

    @expose('ratbot.templates.comic_form')
    def new_comic(self, **kw):
        tmpl_context.form = new_comic_form
        return dict(
            page='new_comic',
            value=kw
        )

    @expose('ratbot.templates.comic_form')
    def alter_comic(self, old_id, **kw):
        tmpl_context.form = alter_comic_form
        if not kw:
            value = DBSession.query(Comic).filter(Comic.id==old_id).one()
            value.old_id = old_id
        else:
            value = kw
        return dict(
            page='alter_comic',
            value=value,
        )

    @validate(new_comic_form, error_handler=new_comic)
    @expose()
    def create_comic(self, **kw):
        comic = Comic()
        comic.id = kw['id']
        comic.title = kw['title']
        comic.description = kw['description']
        DBSession.add(comic)
        DBSession.flush()
        flash('Comic added successfully')
        redirect('index')

    @validate(alter_comic_form, error_handler=alter_comic)
    @expose()
    def update_comic(self, **kw):
        comic = DBSession.query(Comic).filter(Comic.id==kw['old_id']).one()
        comic.id = kw['id']
        comic.title = kw['title']
        comic.description = kw['description']
        DBSession.add(comic)
        DBSession.flush()
        flash('Comic updated successfully')
        redirect('index')

    @expose('ratbot.templates.new_page_form')
    def new_page(self, **kw):
        tmpl_context.form = new_page_form
        return dict(
            page='new_page',
            value=kw,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @validate(new_page_form, error_handler=new_page)
    @expose()
    def create_page(self, **kw):
        page = Page()
        page.comic_id = kw['comic_id']
        page.issue_number = kw['issue_number']
        page.number = kw['number']
        page.created = datetime.datetime.now()
        page.published = kw['published']
        page.vector = kw['vector'].value
        page.bitmap = kw['bitmap'].value
        DBSession.add(page)
        DBSession.flush()
        flash('Page added successfully')
        redirect('index')

    @expose('ratbot.templates.comic')
    def view(self, comic, issue, page):
        page = DBSession.query(Page).filter(
            Page.comic_id==comic and
            Page.issue_number==issue and
            Page.number==page).one()
        return dict(page='comic', comic=page)

    @expose(content_type='image/png')
    def thumb(self, comic, issue, page):
        page = DBSession.query(Page).filter(
            Page.comic_id==comic and
            Page.issue_number==issue and
            Page.number==page).one()
        return page.thumbnail

    @expose(content_type='image/png')
    def png(self, comic, issue, page):
        page = DBSession.query(Page).filter(
            Page.comic_id==comic and
            Page.issue_number==issue and
            Page.number==page).one()
        return page.bitmap

    @expose(content_type='image/svg+xml')
    def svg(self, comic, issue, page):
        page = DBSession.query(Page).filter(
            Page.comic_id==comic and
            Page.issue_number==issue and
            Page.number==page).one()
        return page.vector
