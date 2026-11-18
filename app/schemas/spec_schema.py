from typing import Literal, Optional
from pydantic import BaseModel, Field


class FeatureItem(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    priority: Literal["high", "medium", "low"]


class UserStoryItem(BaseModel):
    role: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    benefit: str = Field(..., min_length=1)


class ImageEvidence(BaseModel):
    ui_components: list[str] = Field(default_factory=list)
    visible_states: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    absent_or_unclear: list[str] = Field(default_factory=list)


class ProjectSpecification(BaseModel):
    project_summary: str = Field(..., min_length=10)
    features: list[FeatureItem] = Field(..., min_length=1)
    user_stories: list[UserStoryItem] = Field(..., min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)


# --- Day 3 Engineering Artifact Schemas ---

class AcceptanceCriterion(BaseModel):
    story_id: str = Field(..., min_length=1)
    given: str = Field(..., min_length=1)
    when: str = Field(..., min_length=1)
    then: str = Field(..., min_length=1)


class ImplementationPlan(BaseModel):
    frontend: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    apis: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class QATestCase(BaseModel):
    test_id: str = Field(..., min_length=1)
    category: Literal["positive", "negative", "edge"]
    title: str = Field(..., min_length=1)
    steps: list[str] = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)


class CoreEngineeringPack(BaseModel):
    acceptance_criteria: list[AcceptanceCriterion] = Field(..., min_length=1)
    implementation_plan: ImplementationPlan
    qa_test_cases: list[QATestCase] = Field(..., min_length=1)


class DeliveryCommsPack(BaseModel):
    developer_prompt: str = Field(..., min_length=20)
    client_update: str = Field(..., min_length=20)
    release_notes: str = Field(..., min_length=20)


class EngineeringArtifactsBundle(BaseModel):
    acceptance_criteria: list[AcceptanceCriterion]
    implementation_plan: ImplementationPlan
    qa_test_cases: list[QATestCase]
    developer_prompt: str
    client_update: str
    release_notes: str


class GenerateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=200)
    project_description: Optional[str] = None
    raw_text: str = Field(..., min_length=1)


class GenerateResponse(BaseModel):
    project_id: int
    input_id: int
    run_id: int
    artifact_id: int
    input_type: str
    model_name: str
    prompt_version: str
    review_status: str
    image_evidence: Optional[ImageEvidence] = None
    specification: ProjectSpecification


class GenerateArtifactsResponse(BaseModel):
    run_id: int
    project_id: int
    model_name: str
    prompt_versions: list[str]
    review_status: str
    artifacts: EngineeringArtifactsBundle