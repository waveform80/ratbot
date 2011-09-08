# -*- coding: utf-8 -*-
"""Setup the ratbot application"""

import logging
import transaction
from tg import config

def setup_schema(command, conf, vars):
    """Place any commands to setup ratbot here"""
    from ratbot import model
    print "Creating tables"
    model.metadata.create_all(bind=config['pylons.app_globals'].sa_engine)
    transaction.commit()
    from migrate.versioning.shell import main
    from migrate.exceptions import DatabaseAlreadyControlledError
    try:
        main(argv=['version_control'], url=config['sqlalchemy.url'], repository='migration', name='migration')
    except DatabaseAlreadyControlledError:
        print 'Database already under version control'
