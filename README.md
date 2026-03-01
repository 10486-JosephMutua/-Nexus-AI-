# Nexus AI (Enhanced Edition)
> **Week 2 of the 12-Week AI Sprint: Bridging Theory and Practice.**

Nexus AI is a multi-source synthesis agent designed to solve the problem of "scattered context." Most RAG applications only let you chat with a single PDF. Nexus builds a bridge between two different media formats—theoretical documents (PDFs) and practical lectures (YouTube)—allowing the AI to cross‑examine both simultaneously.

---

## Key Features

- **Multi-Source Synthesis:** Ingests a PDF and a YouTube transcript into a unified vector space for comparative analysis.
- **Agentic Contradiction Detection:** A LangGraph node that acts as a judge, flagging factual disagreements or "deltas" between sources.
- **Coverage Gap Analysis:** Identifies topics explained in the video that were missing from the textbook.
- **Citation Traceability:** UI links let users see which source (and which page) a specific claim came from.
- **Efficient Ingestion:** Uses SHA-256 content hashing to prevent redundant processing of previously uploaded documents.

---

## The Tech Stack

- **Brain:** [LangGraph](https://github.com/langchain-ai/langgraph) (stateful multi-node reasoning)
- **Inference:** Llama-3-70b via [Groq](https://groq.com/)
- **Vector Storage:** [ChromaDB](https://www.trychroma.com/)
- **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (local / open source)
- **Package Manager:** [uv](https://github.com/astral-sh/uv)
- **Frontend:** Flask + Tailwind Typography + Marked.js

---

## Installation & Setup

### 1) Prerequisites

Install the required package manager:

```bash
pip install uv
```

### 2) Clone and sync the repo

```bash
git clone https://github.com/10486-JosephMutua/-Nexus-AI-.git
cd -Nexus-AI-
uv sync
```

### 3) Environment variables

Create a `.env` file in the project root and add your keys:

```
GROQ_API_KEY=gsk_your_key_here
```

### 4) Run the application

```bash
uv run app.py
```

Open http://127.0.0.1:5001 in your browser.

## Brain Workflow

Nexus uses a cyclic graph architecture rather than a linear chain. The main steps are:

- **Retrieve:** Gather the most relevant chunks (e.g., top 15) from all sources.
- **Detect Conflicts:** Analyze chunks to find factual disagreements.
- **Gap Analysis:** Map unique information provided by each source.
- **Synthesize:** Generate a final, grounded answer with full source citations.
