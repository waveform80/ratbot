# -*- coding: utf-8 -*-
"""Comic Controller"""

from tg import expose, validate, flash, require, redirect, tmpl_context
from tg.i18n import ugettext as _, lazy_ugettext as l_
from repoze.what import predicates

from ratbot.lib.base import BaseController
from ratbot.widgets.comics import new_page_form, new_comic_form, alter_comic_form, new_issue_form, alter_issue_form
from ratbot.model import DBSession, Comic, Issue, Page
import transaction

__all__ = ['AdminController']

class AdminController(BaseController):
    allow_only = predicates.has_permission('admin', msg=l_('Only for admins'))

    @expose('ratbot.templates.comic_form')
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    def new_comic(self, **kw):
        tmpl_context.form = new_comic_form
        return dict(
            method='new_comic',
            value=kw,
        )

    @expose('ratbot.templates.comic_form')
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    def alter_comic(self, old_id, **kw):
        tmpl_context.form = alter_comic_form
        if not kw:
            value = DBSession.query(Comic).filter(Comic.id==old_id).one()
            value.old_id = old_id
        else:
            value = kw
        return dict(
            method='alter_comic',
            value=value,
        )

    @validate(new_comic_form, error_handler=new_comic)
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    @expose()
    def insert_comic(self, **kw):
        comic = Comic()
        comic.id = kw['id']
        comic.title = kw['title']
        comic.description = kw['description']
        DBSession.add(comic)
        DBSession.flush()
        transaction.commit()
        flash('Comic added successfully')
        redirect('index')

    @validate(alter_comic_form, error_handler=alter_comic)
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    @expose()
    def update_comic(self, **kw):
        comic = DBSession.query(Comic).filter(Comic.id==kw['old_id']).one()
        comic.id = kw['id']
        comic.title = kw['title']
        comic.description = kw['description']
        DBSession.flush()
        transaction.commit()
        flash('Comic updated successfully')
        redirect('index')

    @expose('ratbot.templates.issue_form')
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    def new_issue(self, **kw):
        tmpl_context.form = new_issue_form
        return dict(
            method='new_issue',
            value=kw,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @expose('ratbot.templates.issue_form')
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    def alter_issue(self, old_comic, old_number, **kw):
        tmpl_context.form = alter_issue_form
        if not kw:
            value = DBSession.query(Issue).\
                filter(Issue.comic_id==old_comic).\
                filter(Issue.number==old_number).one()
            value.old_comic = old_comic
            value.old_number = old_number
        else:
            value = kw
        return dict(
            method='alter_issue',
            value=value,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @validate(new_issue_form, error_handler=new_issue)
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    @expose()
    def insert_issue(self, **kw):
        issue = Issue()
        issue.comic_id = kw['comic_id']
        issue.number = kw['number']
        issue.title = kw['title']
        issue.description = kw['description']
        DBSession.add(issue)
        DBSession.flush()
        transaction.commit()
        flash('Issue added successfully')
        redirect('index')

    @validate(alter_issue_form, error_handler=alter_issue)
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    @expose()
    def update_issue(self, **kw):
        issue = DBSession.query(Issue).\
            filter(Issue.comic_id==kw['old_comic']).\
            filter(Issue.number==kw['old_number']).one()
        issue.comic_id = kw['comic_id']
        issue.number = kw['number']
        issue.title = kw['title']
        issue.description = kw['description']
        DBSession.flush()
        transaction.commit()
        flash('Comic updated successfully')
        redirect('index')

    @expose('ratbot.templates.new_page_form')
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    def new_page(self, **kw):
        tmpl_context.form = new_page_form
        return dict(
            method='new_page',
            value=kw,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @validate(new_page_form, error_handler=new_page)
    @require(predicates.has_permission('admin', msg=l_('Only for admins')))
    @expose()
    def insert_page(self, **kw):
        page = Page()
        page.comic_id = kw['comic_id']
        page.issue_number = kw['issue_number']
        page.number = kw['number']
        page.published = kw['published']
        page.vector = kw['vector'].value
        page.bitmap = kw['bitmap'].value
        DBSession.add(page)
        DBSession.flush()
        transaction.commit()
        flash('Page added successfully')
        redirect('index')

