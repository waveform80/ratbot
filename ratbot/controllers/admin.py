from tg.i18n import lazy_ugettext as l_
from repoze.what import predicates
from tgext.admin.controller import AdminController as BaseAdminController

__all__ = ['AdminController']

class AdminController(BaseAdminController):
    allow_only = predicates.has_permission('admin', msg=l_('Only for admins'))
