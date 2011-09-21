from sqlalchemy import *
from migrate import *
import ratbot.model

def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind migrate_engine
    # to your metadata
    ratbot.model.metadata.bind = migrate_engine
    ratbot.model.News.__table__.create()

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    ratbot.model.metadata.bind = migrate_engine
    ratbot.model.News.__table__.drop()
