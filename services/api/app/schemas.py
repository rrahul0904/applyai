import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    account_status: str
    onboarding_completed: bool
    onboarding_stage: str


class ProfileWrite(BaseModel):
    headline: str | None = Field(default=None, max_length=240)
    current_title: str | None = Field(default=None, max_length=240)
    summary: str | None = Field(default=None, max_length=4000)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    target_roles: list[str] = Field(default_factory=list, max_length=10)
    location_text: str | None = Field(default=None, max_length=240)
    work_modes: list[str] = Field(default_factory=list, max_length=3)
    minimum_compensation: int | None = Field(default=None, ge=0, le=10_000_000)


class ProfileResponse(ProfileWrite):
    id: uuid.UUID
    user_id: uuid.UUID
    experiences: list["ExperienceWrite"] = Field(default_factory=list)
    education: list["EducationWrite"] = Field(default_factory=list)
    skills: list["SkillWrite"] = Field(default_factory=list)


class ExperienceWrite(BaseModel):
    id: uuid.UUID | None = None
    company_name: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=240)
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = Field(default=None, max_length=4000)
    provenance: str = "USER_ENTERED"


class EducationWrite(BaseModel):
    id: uuid.UUID | None = None
    institution: str = Field(min_length=1, max_length=240)
    degree: str | None = Field(default=None, max_length=240)
    field_of_study: str | None = Field(default=None, max_length=240)
    start_date: str | None = None
    end_date: str | None = None
    provenance: str = "USER_ENTERED"


class SkillWrite(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    provenance: str = "USER_ENTERED"


class ProfileReviewWrite(ProfileWrite):
    experiences: list[ExperienceWrite] = Field(default_factory=list, max_length=40)
    education: list[EducationWrite] = Field(default_factory=list, max_length=20)
    skills: list[SkillWrite] = Field(default_factory=list, max_length=100)


class OnboardingStateWrite(BaseModel):
    stage: str


class OnboardingStateResponse(BaseModel):
    onboarding_stage: str
    onboarding_completed: bool


class ResumeVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    filename: str
    content_type: str
    file_size: int
    upload_status: str
    processing_status: str
    created_at: datetime


class ResumeExtractionResponse(BaseModel):
    id: uuid.UUID
    resume_version_id: uuid.UUID
    status: str
    error_code: str | None
    structured_data: dict | None
    created_at: datetime


class JobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    work_mode: str | None
    minimum_compensation: int | None
    maximum_compensation: int | None
    compensation_provenance: str | None
    posted_at: datetime | None
    last_seen_at: datetime
    saved: bool = False
    data_origin: str


class JobSearchPage(BaseModel):
    items: list[JobSummary]
    next_cursor: str | None
    returned: int


class JobDetail(JobSummary):
    description: str
    employment_type: str | None
    seniority: str | None
    requirements: list[str]
    skills: list[str]
    source_url: str | None
    status: str


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class ApplicationStatusWrite(BaseModel):
    status: str


class ApplicationEventResponse(BaseModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    created_at: datetime


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    current_status: str
    created_at: datetime
    updated_at: datetime
    events: list[ApplicationEventResponse] = Field(default_factory=list)
    notes: list["ApplicationNoteResponse"] = Field(default_factory=list)


class ApplicationJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    location: str | None


class ApplicationListItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    current_status: str
    created_at: datetime
    updated_at: datetime
    job: ApplicationJobSummary


class ApplicationNoteWrite(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class ApplicationNoteResponse(BaseModel):
    id: uuid.UUID
    body: str
    created_at: datetime
    updated_at: datetime
