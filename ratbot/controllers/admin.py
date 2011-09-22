# -*- coding: utf-8 -*-
"""Comic Controller"""

from tg import expose, validate, flash, require, redirect, request, tmpl_context, url
from tg.i18n import ugettext as _, lazy_ugettext as l_
from repoze.what import predicates

from ratbot.lib.base import BaseController
from ratbot.widgets.comics import new_page_form, new_comic_form, alter_comic_form, new_issue_form, alter_issue_form, new_news_form, alter_news_form
from ratbot.widgets.auth import new_user_form, new_group_form, new_permission_form, alter_user_form, alter_group_form, alter_permission_form
from ratbot.model import DBSession, News, Comic, Issue, Page, User, Group, Permission
import transaction

__all__ = ['AdminController']

class AdminController(BaseController):
    allow_only = predicates.has_permission('admin', msg=l_('Only for admins'))

    @expose('json')
    def issues(self, comic):
        return dict(data=[issue.number for issue in DBSession.query(Issue).filter(Issue.comic_id==comic)])

    @expose('json')
    def pages(self, comic, issue):
        return dict(data=[page.number for page in DBSession.query(Page).filter(Page.comic_id==comic).filter(Page.issue_number==issue)])

    @expose('ratbot.templates.admin')
    def index(self):
        return dict(
            method='admin_index',
            news=DBSession.query(News).order_by(News.id),
            comics=DBSession.query(Comic).order_by(Comic.id),
            issues=DBSession.query(Issue).order_by(Issue.comic_id, Issue.number),
            pages=DBSession.query(Page).order_by(Page.comic_id, Page.issue_number, Page.number),
            users=DBSession.query(User).order_by(User.user_name),
            groups=DBSession.query(Group).order_by(Group.group_name),
            permissions=DBSession.query(Permission).order_by(Permission.permission_name),
        )

    @expose('ratbot.templates.user_form')
    def new_user(self, **kw):
        tmpl_context.form = new_user_form
        return dict(
            method='new_user',
            value=kw,
            group_names=DBSession.query(Group.group_name, Group.group_name),
        )

    @expose('ratbot.templates.user_form')
    def alter_user(self, old_id, **kw):
        tmpl_context.form = alter_user_form
        if not kw:
            value = DBSession.query(User).filter(User.user_name==old_id).one()
            value.old_id = old_id
        else:
            value = kw
        return dict(
            method='alter_user',
            value=value,
            group_names=DBSession.query(Group.group_name, Group.group_name),
        )

    @expose('ratbot.templates.confirmation')
    def remove_user(self, user_name):
        return dict(
            method='remove_user',
            prompt='Are you sure you wish to delete user "%s"?' % user_name,
            params=dict(user_name=user_name),
            action=url('/admin/delete_user'),
        )

    @validate(new_user_form, error_handler=new_user)
    @expose()
    def insert_user(self, **kw):
        user = User()
        user.user_name = kw['user_name']
        user.email_address = kw['email_address']
        user.display_name = kw['display_name']
        user.password = kw['password']
        user.group_names = kw['group_names']
        DBSession.add(user)
        DBSession.flush()
        transaction.commit()
        flash('User added successfully')
        redirect('index')

    @validate(alter_user_form, error_handler=alter_user)
    @expose()
    def update_user(self, old_id, **kw):
        user = DBSession.query(User).filter(User.user_name==old_id).one()
        user.user_name = kw['user_name']
        user.email_address = kw['email_address']
        user.display_name = kw['display_name']
        user.group_names = kw['group_names']
        if user.password != kw['password']:
            user.password = kw['password']
        DBSession.flush()
        transaction.commit()
        flash('User updated successfully')
        redirect('index')

    @expose()
    def delete_user(self, user_name, confirm):
        user = DBSession.query(User).filter(User.user_name==user_name).one()
        DBSession.delete(user)
        DBSession.flush()
        transaction.commit()
        flash('User deleted successfully')
        redirect('index')

    @expose('ratbot.templates.group_form')
    def new_group(self, **kw):
        tmpl_context.form = new_group_form
        return dict(
            method='new_group',
            value=kw,
            user_names=DBSession.query(User.user_name, User.user_name),
            permission_names=DBSession.query(Permission.permission_name, Permission.permission_name),
        )

    @expose('ratbot.templates.group_form')
    def alter_group(self, old_id, **kw):
        tmpl_context.form = alter_group_form
        if not kw:
            value = DBSession.query(Group).filter(Group.group_name==old_id).one()
            value.old_id = old_id
        else:
            value = kw
        return dict(
            method='alter_group',
            value=value,
            user_names=DBSession.query(User.user_name, User.user_name),
            permission_names=DBSession.query(Permission.permission_name, Permission.permission_name),
        )

    @expose('ratbot.templates.confirmation')
    def remove_group(self, group_name):
        return dict(
            method='remove_group',
            prompt='Are you sure you wish to delete group "%s"?' % group_name,
            params=dict(group_name=group_name),
            action=url('/admin/delete_group'),
        )

    @validate(new_group_form, error_handler=new_group)
    @expose()
    def insert_group(self, **kw):
        group = Group()
        group.group_name = kw['group_name']
        group.display_name = kw['display_name']
        group.user_names = kw['user_names']
        group.permission_names = kw['permission_names']
        DBSession.add(group)
        DBSession.flush()
        transaction.commit()
        flash('Group added successfully')
        redirect('index')

    @validate(alter_group_form, error_handler=alter_group)
    @expose()
    def update_group(self, old_id, **kw):
        group = DBSession.query(Group).filter(Group.group_name==old_id).one()
        group.group_name = kw['group_name']
        group.display_name = kw['display_name']
        group.user_names = kw['user_names']
        group.permission_names = kw['permission_names']
        DBSession.flush()
        transaction.commit()
        flash('Group updated successfully')
        redirect('index')

    @expose()
    def delete_group(self, group_name, confirm):
        group = DBSession.query(Group).filter(Group.group_name==group_name).one()
        DBSession.delete(group)
        DBSession.flush()
        transaction.commit()
        flash('Group deleted successfully')
        redirect('index')

    @expose('ratbot.templates.permission_form')
    def new_permission(self, **kw):
        tmpl_context.form = new_permission_form
        return dict(
            method='new_permission',
            value=kw,
            group_names=DBSession.query(Group.group_name, Group.group_name),
        )

    @expose('ratbot.templates.permission_form')
    def alter_permission(self, old_id, **kw):
        tmpl_context.form = alter_permission_form
        if not kw:
            value = DBSession.query(Permission).filter(Permission.permission_name==old_id).one()
            value.old_id = old_id
        else:
            value = kw
        return dict(
            method='alter_permission',
            value=value,
            group_names=DBSession.query(Group.group_name, Group.group_name),
        )

    @expose('ratbot.templates.confirmation')
    def remove_permission(self, permission_name):
        return dict(
            method='remove_permission',
            prompt='Are you sure you wish to delete permission "%s"?' % permission_name,
            params=dict(permission_name=permission_name),
            action=url('/admin/delete_permission'),
        )

    @validate(new_permission_form, error_handler=new_permission)
    @expose()
    def insert_permission(self, **kw):
        permission = Permission()
        permission.permission_name = kw['permission_name']
        permission.description = kw['description']
        permission.group_names = kw['group_names']
        DBSession.add(permission)
        DBSession.flush()
        transaction.commit()
        flash('Permission added successfully')
        redirect('index')

    @validate(alter_permission_form, error_handler=alter_permission)
    @expose()
    def update_permission(self, old_id, **kw):
        permission = DBSession.query(Permission).filter(Permission.permission_name==old_id).one()
        permission.permission_name = kw['permission_name']
        permission.description = kw['description']
        permission.group_names = kw['group_names']
        DBSession.flush()
        transaction.commit()
        flash('Permission updated successfully')
        redirect('index')

    @expose()
    def delete_permission(self, permission_name, confirm):
        permission = DBSession.query(Permission).filter(Permission.permission_name==permission_name).one()
        DBSession.delete(permission)
        DBSession.flush()
        transaction.commit()
        flash('Permission deleted successfully')
        redirect('index')

    @expose('ratbot.templates.news_form')
    def new_news(self, **kw):
        tmpl_context.form = new_news_form
        return dict(
            method='new_news',
            value=kw,
        )

    @expose('ratbot.templates.news_form')
    def alter_news(self, id, **kw):
        tmpl_context.form = alter_news_form
        if not kw:
            value = DBSession.query(News).filter(News.id==id).one()
        else:
            value = kw
        return dict(
            method='alter_news',
            value=value,
        )

    @expose('ratbot.templates.confirmation')
    def remove_news(self, id):
        news = DBSession.query(News).filter(News.id==id).one()
        return dict(
            method='remove_news',
            prompt='Are you sure you wish to delete article "%s"?' % news.title,
            params=dict(id=id),
            action=url('/admin/delete_news'),
        )

    @validate(new_news_form, error_handler=new_news)
    @expose()
    def insert_news(self, **kw):
        news = News()
        news.title = kw['title']
        news.published = kw['published']
        news.content = kw['content']
        news.author = request.identity['repoze.who.userid']
        DBSession.add(news)
        DBSession.flush()
        transaction.commit()
        flash('News article added successfully')
        redirect('index')

    @validate(alter_news_form, error_handler=alter_news)
    @expose()
    def update_news(self, **kw):
        news = DBSession.query(News).filter(News.id==kw['id']).one()
        news.title = kw['title']
        news.published = kw['published']
        news.content = kw['content']
        DBSession.flush()
        transaction.commit()
        flash('News article updated successfully')
        redirect('index')

    @expose()
    def delete_news(self, id, confirm):
        news = DBSession.query(News).filter(Comic.id==id).one()
        DBSession.delete(news)
        DBSession.flush()
        transaction.commit()
        flash('News article deleted successfully')
        redirect('index')

    @expose('ratbot.templates.comic_form')
    def new_comic(self, **kw):
        tmpl_context.form = new_comic_form
        return dict(
            method='new_comic',
            value=kw,
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
            method='alter_comic',
            value=value,
        )

    @expose('ratbot.templates.confirmation')
    def remove_comic(self, id):
        return dict(
            method='remove_comic',
            prompt='Are you sure you wish to delete comic "%s"?' % id,
            params=dict(id=id),
            action=url('/admin/delete_comic'),
        )

    @validate(new_comic_form, error_handler=new_comic)
    @expose()
    def insert_comic(self, **kw):
        comic = Comic()
        comic.id = kw['id']
        comic.title = kw['title']
        comic.description = kw['description']
        comic.author = request.identity['repoze.who.userid']
        DBSession.add(comic)
        DBSession.flush()
        transaction.commit()
        flash('Comic added successfully')
        redirect('index')

    @validate(alter_comic_form, error_handler=alter_comic)
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

    @expose()
    def delete_comic(self, id, confirm):
        comic = DBSession.query(Comic).filter(Comic.id==id).one()
        DBSession.delete(comic)
        DBSession.flush()
        transaction.commit()
        flash('Comic deleted successfully')
        redirect('index')

    @expose('ratbot.templates.issue_form')
    def new_issue(self, **kw):
        tmpl_context.form = new_issue_form
        return dict(
            method='new_issue',
            value=kw,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @expose('ratbot.templates.issue_form')
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

    @expose('ratbot.templates.confirmation')
    def remove_issue(self, comic_id, number):
        return dict(
            method='remove_issue',
            prompt='Are you sure you wish to delete issue "%d" of comic "%s"?' % (int(number), comic_id),
            params=dict(comic_id=comic_id, number=int(number)),
            action=url('/admin/delete_issue'),
        )

    @validate(new_issue_form, error_handler=new_issue)
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

    @expose()
    def delete_issue(self, comic_id, number, confirm):
        issue = DBSession.query(Issue).\
            filter(Issue.comic_id==comic_id).\
            filter(Issue.number==number).one()
        DBSession.delete(issue)
        DBSession.flush()
        transaction.commit()
        flash('Issue deleted successfully')
        redirect('index')

    @expose('ratbot.templates.page_form')
    def new_page(self, **kw):
        tmpl_context.form = new_page_form
        return dict(
            method='new_page',
            value=kw,
            comic_ids=DBSession.query(Comic.id, Comic.title),
        )

    @expose('ratbot.templates.confirmation')
    def remove_issue(self, comic_id, issue_number, number):
        return dict(
            method='remove_page',
            prompt='Are you sure you wish to delete page %d of issue %d of comic "%s"?' % (int(number), int(issue_number), comic_id),
            params=dict(
                comic_id=comic_id,
                issue_number=int(issue_number),
                number=int(number)
            ),
            action=url('/admin/delete_page'),
        )

    @validate(new_page_form, error_handler=new_page)
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

    @expose()
    def delete_issue(self, comic_id, issue_number, number, confirm):
        page = DBSession.query(Page).\
            filter(Page.comic_id==comic_id).\
            filter(Page.issue_number==issue_number).\
            filter(Page.number==number).one()
        DBSession.delete(page)
        DBSession.flush()
        transaction.commit()
        flash('Page deleted successfully')
        redirect('index')

