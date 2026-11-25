from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    inputs = relationship("InputDocument", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("GenerationRun", back_populates="project", cascade="all, delete-orphan")


class InputDocument(Base):
    __tablename__ = "input_documents"

    input_id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    input_type = Column(String(50), default="text", nullable=False)
    source_text = Column(Text, nullable=False)
    file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="inputs")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    run_id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="runs")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    artifact_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("generation_runs.run_id"), nullable=False)
    type = Column(String(50), default="specification", nullable=False)
    content_json = Column(Text, nullable=False)
    review_status = Column(String(50), default="draft", nullable=False)
    created_at = Column(DateTime, default=utc_now)

    run = relationship("GenerationRun", back_populates="artifacts")


class EvaluationTest(Base):
    __tablename__ = "evaluation_tests"

    test_id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(String(50), nullable=False)
    category = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    scenario = Column(Text, nullable=False)
    expected_fields = Column(Text, nullable=False)
    structure_valid = Column(Integer, default=1, nullable=False)  # 1 = Pass, 0 = Fail
    completeness_score = Column(Float, default=0.0, nullable=False)
    evidence_fidelity_score = Column(Float, default=0.0, nullable=False)
    uncertainty_score = Column(Float, default=0.0, nullable=False)
    usefulness_score = Column(Float, default=0.0, nullable=False)
    overall_score = Column(Float, default=0.0, nullable=False)
    failure_category = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ReviewFeedback(Base):
    __tablename__ = "review_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.artifact_id"), nullable=False)
    reviewer_note = Column(Text, nullable=True)
    label = Column(String(50), nullable=False)  # approved | edited | rejected
    created_at = Column(DateTime, default=utc_now)