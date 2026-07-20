from typing import TypedDict,List,Annotated, Literal, Optional
from pydantic import BaseModel, Field
import operator


class Task(BaseModel):
    id: int
    title: str

    goal: str = Field(...,description="one sentence describing what the reader should be able to do/understand after this section")
    bullets: List[str] = Field(min_length=1,max_length=3,description="1-3 concrete, non-overlapping subpoints to cover in this section."
    )
    target_words: int = Field(..., description="Target word count for this section (120-350).")
    tags: List[str] = Field(default_factory=list)
    requires_research: bool=False
    requires_citations: bool=False
    requires_code: bool=False

class Plan(BaseModel):
    blog_title: str
    audience: str= Field(..., description="Who this blog is for.")
    tone: str = Field(..., description="Writing tone (for example, practical, crisp, technical).")
    constraints: List[str] =Field(default_factory=list)
    tasks: List[Task]

class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] =None
    snippet: Optional[str]=None
    source: Optional[str] =None
class RouterDecision(BaseModel):
    needs_research: bool
    mode: Literal["closed_book","hybrid","open_book"]
    queries: List[str]=Field(default_factory=list)

class EvidencePack(BaseModel):
    evidence: List[EvidenceItem]=Field(default_factory=list)

class ImageSpec(BaseModel):
    section_title: str = Field(
    description="Exact markdown heading including ##, for example: ## Self-Attention Mechanism"
    )
    # placeholder: str=Field(description="for example, [[Image_1]]")
    filename: str=Field(description="Save under images/, e.g. gkv_flow.png")
    alt: str
    caption: str
    prompt: str=Field(description="Prompt to send to the image model")
    size: Literal["1024x1024","1024x1536","1536x1024"]="1024x1024"
    quality: Literal["low","medium","high"]="medium"

# class ImagePlaceholder(BaseModel):
#     md_with_placeholder: str
#     images: List[ImageSpec]=Field(default_factory=list)
class ImagePlan(BaseModel):
    images: List[ImageSpec] = Field(default_factory=list)

class State(TypedDict):
    topic: str
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]
    sections: Annotated[List[tuple[int, str]], operator.add]
    as_of: str
    recency_days: int
    merged_md: str
    # md_with_placeholder: str
    image_specs: List[dict]

    final: str