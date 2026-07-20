# Blog Writing Agent Using Langgraph

A blog writing langgraph application that generates complete technical blog posts from a single topic.

The application uses LangGraph to orchestrate multiple AI agents that plan the article, perform research when needed, write each section in parallel, generate image suggestions, and produce a final Markdown blog.

## Features

- Generate complete technical blogs from a topic
- Automatic blog planning and outlining
- Optional web research
- Parallel section generation using LangGraph
- Simple Streamlit interface

## Tech Stack

- Python
- LangGraph
- LangChain
- Groq LLM
- Streamlit
- Tavily Search API
- Google Gemini Image API


## Installation

Clone the repository.

```bash
git https://github.com/Maaz708/blog_agent_using_langgraph
```

Create a virtual environment.

```bash
python -m venv venv
```

Activate it.

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Create a `.env` file.

```env
GROQ_API_KEY=your_key
GOOGLE_API_KEY=your_key
TAVILY_API_KEY=your_key
```



## Running the application

```bash
streamlit run app.py
```

## How it Works

1. Enter a blog topic.
2. The planner creates the article outline.
3. Research is performed if required.
4. Multiple sections are generated in parallel.
5. Image locations are selected.
6. Images are generated (if enabled).
7. The final blog is saved as a Markdown file.

## Future Improvements

- PDF export
- DOCX export
- Multiple image generation
- More image models
- Blog history
- User authentication

