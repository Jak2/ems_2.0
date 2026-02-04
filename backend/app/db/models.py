from sqlalchemy import Column, Integer, String, Text, Sequence
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Sequence for auto-generating employeeID in format: 013449
employee_id_seq = Sequence('employee_id_seq', start=1, increment=1)


class Employee(Base):
    __tablename__ = "employees"

    # Primary key (internal, auto-increment)
    id = Column(Integer, primary_key=True, index=True)

    # Custom employee ID (format: 013449) - auto-generated
    employee_id = Column(String(6), unique=True, index=True, nullable=False)

    # Basic Information
    name = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    phone = Column(String(64), nullable=True)

    # Professional Information
    department = Column(String(128), nullable=True)
    position = Column(String(128), nullable=True)

    # Online Presence
    linkedin_url = Column(String(512), nullable=True)

    # Career Information (TEXT for longer content)
    summary = Column(Text, nullable=True)

    # Experience & Education (JSON/TEXT - structured data)
    work_experience = Column(Text, nullable=True)  # JSON array of experiences
    education = Column(Text, nullable=True)        # JSON array of education

    # Skills (JSON/TEXT - arrays)
    technical_skills = Column(Text, nullable=True)     # JSON array
    languages = Column(Text, nullable=True)            # JSON array

    # Additional Information
    hobbies = Column(Text, nullable=True)              # JSON array
    cocurricular_activities = Column(Text, nullable=True)  # JSON array

    # Original CV data
    raw_text = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)  # Clean extracted text from PDF
