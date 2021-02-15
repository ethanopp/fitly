from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..utils import config

# Use mysql db if provided in config else use local sqlite
if config.get("database", 'host'):
    SQLALCHEMY_DATABASE_URL = "mysql+pymysql://{}:{}@{}/{}?host={}?port={}".format(config.get("database", 'user'),
                                                                                   config.get("database", 'password'),
                                                                                   config.get("database", 'host'),
                                                                                   config.get("database", 'db_name'),
                                                                                   config.get("database", 'host'),
                                                                                   config.get("database", 'port')
                                                                                   )
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

else:
    SQLALCHEMY_DATABASE_URL = 'sqlite:///./config/fitness.db'

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
