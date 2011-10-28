from datetime import datetime
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import Unicode, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from migrate import *

DeclarativeBase = declarative_base()
metadata = DeclarativeBase.metadata

class User(DeclarativeBase):
    __tablename__ = 'users'

    user_name = Column(Unicode(128), primary_key=True)
    email_address = Column(Unicode(256), unique=True, nullable=False, info={'rum': {'field':'Email'}})
    display_name = Column(Unicode(256))
    _password = Column('password', Unicode(128), info={'rum': {'field':'Password'}})
    created = Column(DateTime, default=datetime.now)

class News(DeclarativeBase):
    __tablename__ = 'news'

    id = Column(Integer, autoincrement=True, primary_key=True)
    title = Column(Unicode(100), nullable=False)
    content = Column(Unicode, nullable=False)
    published = Column(DateTime, default=datetime.now, nullable=False)
    created = Column(DateTime, default=datetime.now, nullable=False)
    author = Column(Unicode(100), ForeignKey('users.user_name', ondelete="SET NULL", onupdate="CASCADE"))


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    News.__table__.create()

def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    News.__table__.drop()
