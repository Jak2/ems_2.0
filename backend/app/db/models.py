from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    phone = Column(String(64), nullable=True)
    department = Column(String(128), nullable=True)
    position = Column(String(128), nullable=True)
    raw_text = Column(Text, nullable=True)
