from __future__ import annotations
from typing import List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI
import logging
import re


logger = logging.getLogger(__name__)

from datetime import date

from classes_for_backend import (
    Task, 
    Plan, 
    EvidenceItem, 
    RouterDecision, 
    EvidencePack, 
    ImagePlan, 
    ImageSpec, 
    State 
    )
from prompts import (
    ROUTER_SYSTEM,
    RESEARCH_SYSTEM,
    ORCHESTRATOR_BLOG_OUTLINE,
    WORKER_MARKDOWN_PROMPT,
    DECIDE_IMAGES_SYSTEM,

    )

from dotenv import load_dotenv
load_dotenv()




groq_llm=ChatGroq(model="llama-3.3-70b-versatile",temperature=0)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
)



def safe_filename(name: str) -> str:
    # Remove illegal Windows filename characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Limit filename length
    return name[:120]

def router_node(state: State)-> dict:
    topic= state["topic"]
    decider=groq_llm.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}")
        ]

    )
    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
    }

def route_next(state: State)-> dict:
    return "research" if state["needs_research"] else "orchestrator"

import json
def _tavily_search(query: str, max_results: int=2)->List[dict]:

    tool=TavilySearchResults(max_results=max_results)
    results=tool.invoke({"query": query})

    normalised: List[dict] = []
    for r in results or []:
        normalised.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "snippet": r.get("content") or r.get("snippet") or "",
                "source": r.get("source"),

            }
        )
    return normalised


def research_node(state: State)->dict:

    queries= (state.get("queries",[]) or [])
    max_results=1
    raw_results: List[dict] = []

    for q in queries:
        raw_results.extend(_tavily_search(q, max_results=max_results))
    
    if not raw_results:
        return {"evidence": []}
    
    compressed_results = []

    for r in raw_results:
        compressed_results.append({
            "title": r["title"],
            "url": r["url"],
            "published_at": r["published_at"],
            "snippet": (r["snippet"] or "")[:200],   # limit to 200 chars
            "source": r["source"],
        })
    
    extractor = groq_llm.with_structured_output(EvidencePack)
    pack=extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{json.dumps(compressed_results, indent=2)}")
        ]
    )
    dedup={}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e
    return {"evidence": list(dedup.values())}

def orchestrator(state: State)->dict:

    evidence=state.get("evidence", [])
    mode=state.get("mode","closed_book")
    plan = groq_llm.with_structured_output(Plan).invoke(
        [
            SystemMessage(content=ORCHESTRATOR_BLOG_OUTLINE),
            HumanMessage(content=f"Topic: {state['topic']}\n"
                         f"Mode: {mode}\n\n"
                         f"Evidence (only use for fresh claims; may be empty):\n"
                         f"{[e.model_dump() for e in evidence] [:16]}"
                         )
        ]
    )
    return {"plan": plan}

def fanout(state: State):
    return [Send(
        "worker", 
        {
            "task": task.model_dump(),
             "topic":state['topic'],
             "mode": state["mode"],
             "plan": state['plan'].model_dump(),
              "evidence": [e.model_dump() for e in state.get("evidence",[])] }
              ) for task in state['plan'].tasks
              ]

def worker(payload: dict)-> dict:
    task = Task(**payload["task"])
    topic = payload["topic"]
    plan = Plan(**payload['plan'])
    evidence=[EvidenceItem(**e) for e in payload.get("evidence",[])]
    mode=payload.get("mode", "closed_book")

    bullet_text = "\n- " + "\n- ".join(task.bullets)

    evidence_text=""
    if evidence:
        evidence_text="\n".join(
            f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}".strip()
            for e in evidence[:20]
        )

    section_md = groq_llm.invoke(
        [
        SystemMessage(content=WORKER_MARKDOWN_PROMPT),
        HumanMessage(
            content=(
                f"Blog title: {plan.blog_title}\n"
                f"Audience: {plan.audience}\n"
                f"Tone: {plan.tone}\n"
                f"Topic: {topic}\n"
                f"Section: {task.title}\n"
                f"Mode: {mode}\n\n"
                f"requires_research: {task.requires_research}\n"
                f"requires_citations: {task.requires_citations}\n"
                f"requires_code: {task.requires_code}\n"
                f"Goal: {task.goal}\n\n"
                f"Target words: {task.target_words}\n"
                f"Bullets: {bullet_text}\n"
                f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
            )
        ),
        ]
    ).content.strip()

    return {"sections": [(task.id, section_md)]}

import re
from pathlib import Path

def merge_content(state: State)-> dict:
    plan=state["plan"]
    ordered_sections=[md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"
    return {"merged_md":merged_md}



def decide_images(state: State)-> dict:
    planner=groq_llm.with_structured_output(ImagePlan)
    merged_md=state["merged_md"]
    plan=state["plan"]
    assert plan is not None

    

    image_plan=planner.invoke(
        [
            SystemMessage(content=DECIDE_IMAGES_SYSTEM),
            HumanMessage(content=f"""
    Topic:
    {state['topic']}

    Below is a complete markdown article.

    Your task is ONLY to decide whether one technical diagram would improve the article.

    Return JSON matching the ImagePlan schema.

    Rules:
    - Return at most ONE image.
    - Do NOT rewrite the article.
    - Do NOT return markdown.
    - Do NOT insert placeholders.
    - section_title must exactly match one existing H2 heading in the article,
    WITHOUT the leading ## because the code will add it automatically.
    - filename should end with .png.
    - prompt should be detailed enough for an image model to generate the diagram.
    - Prefer diagrams such as architectures, workflows, pipelines, or flowcharts.
    - If no image is needed, return:
    {{"images": []}}

    Markdown article:

    {merged_md}
    """)
            ]
        )

    return {
    "image_specs": [img.model_dump() for img in image_plan.images]
    }


    # return {
    #     "md_with_placeholder": image_plan.md_with_placeholder,
    #     "image_specs": [img.model_dump() for img in image_plan.images],
    # }

def _gemini_generate_image_bytes(prompt: str) -> bytes:
    """
    Returns raw image bytes generated by Gemini.
    Requires: pip install google-genai
    Env var: GOOGLE_API_KEY
    """
    from google import genai
    from google.genai import types
    import os

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    resp = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                )
            ],
        ),
    )

    # Depending on SDK version, parts may hang off resp.candidates[0].content.parts
    parts = getattr(resp, "parts", None)
    if not parts and getattr(resp, "candidates", None):
        try:
            parts = resp.candidates[0].content.parts
        except Exception:
            parts = None

    if not parts:
        raise RuntimeError("No image content returned (safety/quota/SDK change).")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data

    raise RuntimeError("No inline image bytes found in response.")

def generate_image_save(state: State) -> dict:
    plan = state["plan"]
    assert plan is not None

    md = state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    if not image_specs:
        Path(f"{plan.blog_title}.md").write_text(md, encoding="utf-8")
        return {"final": md}

    images_dir = Path("images")
    images_dir.mkdir(exist_ok=True)

    # Insert placeholders
    for i, spec in enumerate(image_specs, start=1):
        placeholder = f"[[Image_{i}]]"
        heading = spec['section_title']

        
        if heading in md:
            md = md.replace(
                heading,
                heading + "\n\n" + placeholder,
                1,
            )

    

    # Generate images
    for i, spec in enumerate(image_specs, start=1):
        placeholder = f"[[Image_{i}]]"

        filename = spec["filename"]
        out_path = images_dir / filename

        if not out_path.exists():
            try:
                img_bytes = _gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)

            except Exception as e:
                logger.exception("Image generation failed: %s", e)

                # Remove the placeholder completely
                md = md.replace(placeholder, "")

                continue

        img_md = (
            f"![{spec['alt']}](images/{filename})\n\n"
            f"*{spec['caption']}*"
        )

        md = md.replace(placeholder, img_md)
    blogs_dir = Path("blogs")
    blogs_dir.mkdir(exist_ok=True)

    filename = safe_filename(plan.blog_title) + ".md"

    Path("blogs").mkdir(exist_ok=True)

    Path("blogs", filename).write_text(
        md,
        encoding="utf-8"
    )
    return {"final": md}

reducer_graph=StateGraph(State)
reducer_graph.add_node("merge_content",merge_content)
reducer_graph.add_node("decide_images",decide_images)
reducer_graph.add_node("generate_image_save",generate_image_save)
reducer_graph.add_edge(START,"merge_content")
reducer_graph.add_edge("merge_content", "decide_images")
reducer_graph.add_edge( "decide_images","generate_image_save")
reducer_graph.add_edge("generate_image_save", END)

reducer_subgraph=reducer_graph.compile()


graph = StateGraph(State)

graph.add_node("router", router_node)
graph.add_node("research", research_node)
graph.add_node("orchestrator",orchestrator)
graph.add_node("worker", worker)
graph.add_node("reducer", reducer_subgraph)

graph.add_edge(START, "router")
graph.add_conditional_edges("router", route_next, {"research":"research","orchestrator": "orchestrator"})
graph.add_edge("research","orchestrator")

graph.add_conditional_edges("orchestrator", fanout, ["worker"])
graph.add_edge("worker","reducer")
graph.add_edge("reducer",END)

workflow = graph.compile()

def run(topic: str, as_of: Optional[str]=None):
    if as_of is None:
        as_of = date.today().isoformat()
    res = workflow.invoke(
        {
            "topic":topic,
            "mode":"",
            "needs_research":False,
            "queries":[],
            "evidence":[],
            "plan":None,
            "as_of":as_of,
            "recency_days": 7,
            "merged_md":"",
            # "md_with_placeholder": "",
            "image_specs": [],

            "sections":[],
            "final":"",
            })
    return res