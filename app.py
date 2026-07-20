import streamlit as st
from pathlib import Path
from datetime import date

# Import your backend
from research_agent_backend import run

st.set_page_config(
    page_title="Blog Writing Agent",
    page_icon="✍️",
    layout="wide",
)

# ---------------- CSS ---------------- #

css_file = Path("style.css")
if css_file.exists():
    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------- Sidebar ---------------- #

with st.sidebar:

    st.markdown("## ✍️ Generate Blog")

    topic = st.text_area(
        "Topic",
        placeholder="Example: Self Attention in Transformers",
        height=120,
    )

    as_of = st.date_input(
        "As of",
        value=date.today(),
    )

    generate = st.button(
        "🚀 Generate",
        use_container_width=True,
    )

    st.divider()

    st.markdown("### 📚 Recent Blogs")

    blog_dir = Path("blogs")
    blog_dir.mkdir(exist_ok=True)

    blogs = sorted(blog_dir.glob("*.md"))

    if blogs:
        for file in blogs[::-1][:10]:
            st.caption(file.name)
    else:
        st.caption("No blogs generated yet.")

# ---------------- Header ---------------- #

st.title("📝 Blog Agent Using Langgraph")
st.caption("Powered by LangGraph + Groq + Gemini")

tabs = st.tabs(
    [
        "📋 Plan",
        "📖 Blog",
        "🖼 Images",
        "📄 Raw Output",
    ]
)

# ---------------- Generate ---------------- #

if generate:

    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()

    with st.spinner("Generating blog..."):

        result = run(
            topic=topic,
            as_of=str(as_of),
        )

        # Convert Pydantic models to dictionaries

        if result.get("plan") is not None:
            result["plan"] = result["plan"].model_dump()

        if result.get("evidence"):
            result["evidence"] = [
                e.model_dump()
                for e in result["evidence"]
            ]

        # Save markdown

        title = result["plan"]["blog_title"]

        filename = (
            title.replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
            + ".md"
        )

        (blog_dir / filename).write_text(
            result["final"],
            encoding="utf-8",
        )

        st.session_state["result"] = result

# ---------------- Display ---------------- #

if "result" in st.session_state:

    result = st.session_state["result"]

    # =====================================================
    # PLAN TAB
    # =====================================================

    with tabs[0]:

        plan = result["plan"]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Audience",
            plan["audience"],
        )

        col2.metric(
            "Tone",
            plan["tone"],
        )

        col3.metric(
            "Sections",
            len(plan["tasks"]),
        )

        st.divider()

        rows = []

        for task in plan["tasks"]:

            rows.append(
                {
                    "ID": task["id"],
                    "Title": task["title"],
                    "Words": task["target_words"],
                    "Research": task["requires_research"],
                    "Code": task["requires_code"],
                }
            )

        st.dataframe(
            rows,
            hide_index=True,
            use_container_width=True,
        )

    # =====================================================
    # BLOG TAB
    # =====================================================

    with tabs[1]:

        st.markdown(result["final"])

    # =====================================================
    # IMAGES TAB
    # =====================================================

    with tabs[2]:

        specs = result.get("image_specs", [])

        if not specs:

            st.info("No images generated.")

        else:

            images_dir = Path("images")

            for img in specs:

                path = images_dir / img["filename"]

                if path.exists():

                    st.image(
                        str(path),
                        use_container_width=True,
                    )

                    st.caption(img["caption"])

                else:

                    st.warning(
                        f"Image not found: {img['filename']}"
                    )

                    st.caption(img["caption"])

    # =====================================================
    # RAW OUTPUT TAB
    # =====================================================

    with tabs[3]:

        st.json(result)