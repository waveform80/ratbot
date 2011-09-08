# -*- coding: utf-8 -*-
"""Setup the ratbot application"""

import logging
from tg import config
from ratbot import model

import transaction


def bootstrap(command, conf, vars):
    from sqlalchemy.exc import IntegrityError
    try:
        u = model.User()
        u.user_name = u'admin'
        u.display_name = u'Administrator'
        u.email_address = u'admin@somedomain.com'
        u.password = u'adminpass'

        model.DBSession.add(u)

        g = model.Group()
        g.group_name = u'admins'
        g.display_name = u'Administrators group'

        g.users.append(u)

        model.DBSession.add(g)

        p = model.Permission()
        p.permission_name = u'admin'
        p.description = u'This permission gives administrative rights to the bearer'
        p.groups.append(g)

        model.DBSession.add(p)

        c = model.Comic()
        c.id = u'mms'
        c.title = u'Major Mass Spec'

        model.DBSession.add(c)

        c = model.Comic()
        c.id = u'name'
        c.title = u'Insert Name Here'

        model.DBSession.add(c)

        c = model.Comic()
        c.id = u'misc'
        c.title = u'Miscellaneous'

        model.DBSession.flush()
    except IntegrityError:
        print 'Warning, there was a problem adding your initial data; it may have already been added'
        transaction.abort()
        raise
    else:
        transaction.commit()
