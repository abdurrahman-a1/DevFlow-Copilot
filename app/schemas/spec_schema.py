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

class ProjectSpecification(BaseModel):
    project_summary: str = Field(..., min_length=10)
    features: list[FeatureItem] = Field(default_factory=list)
    user_stories: list[UserStoryItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

class GenerateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=200)
    project_description: Optional[str] = None
    raw_text: str = Field(..., min_length=1)

class GenerateResponse(BaseModel):
    project_id: int
    input_id: int
    run_id: int
    artifact_id: int
    model_name: str
    prompt_version: str
    review_status: str
    specification: ProjectSpecification