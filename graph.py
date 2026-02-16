import logging
import json
import re
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger("NEXUS_BRAIN")

# ===== ENHANCED STATE WITH NEW FIELDS =====
class GraphState(TypedDict):
    question: str
    context: str
    answer: str
    pdf_docs: List[Any]  # Store PDF documents for analysis
    yt_docs: List[Any]   # Store YouTube documents for analysis
    contradictions: Dict  # Store contradiction analysis results
    citations: Dict       # Store citation metadata
    gaps: Dict           # Store gap analysis results


# ===== CITATION HELPER FUNCTIONS =====
def parse_citations(text: str) -> List[str]:
    """Extract citations like [PDF-p.5] or [YOUTUBE-3:45] from text."""
    citation_pattern = r'\[(PDF-p\.\d+|YOUTUBE-\d+:\d+)\]'
    citations = re.findall(citation_pattern, text)
    return citations


def enrich_with_citation_links(text: str, pdf_docs: List, yt_docs: List) -> Dict[str, Dict]:
    """Create a mapping of citations to their actual document metadata."""
    citation_map = {}
    
    # Process PDF documents
    for doc in pdf_docs:
        page = doc.metadata.get('page', 0)
        citation_key = f'[PDF-p.{page}]'
        citation_map[citation_key] = {
            'type': 'pdf',
            'page': page,
            'snippet': doc.page_content[:200].replace('[PDF SOURCE]\n', '')
        }
    
    # Process YouTube documents
    for doc in yt_docs:
        citation_key = '[YOUTUBE-0:00]'
        if citation_key not in citation_map:
            citation_map[citation_key] = {
                'type': 'youtube',
                'url': doc.metadata.get('source', ''),
                'snippet': doc.page_content[:200].replace('[YOUTUBE SOURCE]\n', '')
            }
    
    return citation_map


# ===== BALANCED MULTI-SOURCE RETRIEVER =====
class BalancedMultiSourceRetriever:
    """
    Custom retriever that ensures BOTH sources are represented in results.
    
    Problem: With 85 PDF chunks vs 2 YouTube chunks, standard similarity search
    always returns only PDF chunks because they dominate the vector space.
    
    Solution: Retrieve more results, then balance by source type.
    """
    
    def __init__(self, vectorstore, k_per_source=3):
        self.vectorstore = vectorstore
        self.k_per_source = k_per_source
        logger.info(f"🔧 Initialized BalancedMultiSourceRetriever (k={k_per_source} per source)")
    
    def invoke(self, query: str) -> List[Any]:
        """
        Retrieve documents ensuring both PDF and YouTube sources are included.
        """
        # Use similarity_search directly with a larger k to get both source types
        all_docs = self.vectorstore.similarity_search(query, k=20)
        
        # Separate by source type
        pdf_docs = [d for d in all_docs if '[PDF SOURCE]' in d.page_content]
        yt_docs = [d for d in all_docs if '[YOUTUBE SOURCE]' in d.page_content]
        
        logger.info(f"🔍 BALANCED RETRIEVAL: Found {len(pdf_docs)} PDF, {len(yt_docs)} YouTube in pool")
        
        # Take top k from each source
        selected_pdf = pdf_docs[:self.k_per_source]
        selected_yt = yt_docs[:self.k_per_source]
        
        # Combine and return
        combined = selected_pdf + selected_yt
        
        logger.info(f"   ✅ Selected {len(selected_pdf)} PDF + {len(selected_yt)} YouTube chunks")
        
        return combined


# ===== MAIN GRAPH CREATION FUNCTION =====
def create_nexus_graph(retriever_or_vectorstore):
    """
    Creates the enhanced Nexus reasoning graph with balanced multi-source retrieval.
    
    Args:
        retriever_or_vectorstore: Either a retriever or vectorstore object.
                                 If retriever, we extract the vectorstore.
    """
    # Initialize LLM
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
    
    # Get the vectorstore (handle both retriever and vectorstore inputs)
    if hasattr(retriever_or_vectorstore, 'vectorstore'):
        # It's a retriever, extract vectorstore
        vectorstore = retriever_or_vectorstore.vectorstore
    else:
        # It's already a vectorstore
        vectorstore = retriever_or_vectorstore
    
    # Create balanced retriever with the vectorstore
    balanced_retriever = BalancedMultiSourceRetriever(vectorstore, k_per_source=3)

    # ===== NODE 1: RETRIEVE & SEPARATE SOURCES =====
    def retrieve_node(state: GraphState) -> Dict:
        """
        Retrieves relevant documents using balanced multi-source strategy.
        """
        logger.info(f"🧠 AGENT EYE: Searching for context for: '{state['question']}'")
        
        # Use balanced retriever
        docs = balanced_retriever.invoke(state["question"])
        
        # Separate PDF and YouTube chunks
        pdf_docs = [d for d in docs if '[PDF SOURCE]' in d.page_content]
        yt_docs = [d for d in docs if '[YOUTUBE SOURCE]' in d.page_content]
        
        # Log what sources were found
        sources_found = set([d.page_content.split('\n')[0] for d in docs])
        logger.info(f"📍 SOURCES RETRIEVED: {list(sources_found)}")
        logger.info(f"   - PDF chunks: {len(pdf_docs)}")
        logger.info(f"   - YouTube chunks: {len(yt_docs)}")
        
        # Combine all content for context
        context = "\n\n".join([d.page_content for d in docs])
        
        return {
            "context": context,
            "pdf_docs": pdf_docs,
            "yt_docs": yt_docs
        }

    # ===== NODE 2: CONTRADICTION DETECTION =====
    def contradiction_detection_node(state: GraphState) -> Dict:
        """
        Analyzes PDF and YouTube sources to detect contradictions.
        """
        logger.info("🔍 DETECTING CONTRADICTIONS between PDF and YouTube sources...")
        
        pdf_docs = state.get("pdf_docs", [])
        yt_docs = state.get("yt_docs", [])
        
        # Skip if only one source type exists
        if not pdf_docs or not yt_docs:
            logger.info("⚠️ Only one source type available - skipping contradiction check")
            return {
                "contradictions": {
                    "status": "single_source",
                    "has_contradictions": False,
                    "conflicts": [],
                    "alignment_score": 100
                }
            }
        
        # Prepare content samples from top chunks
        pdf_content = "\n\n".join([
            f"PDF Chunk {i+1}:\n{d.page_content[:500]}" 
            for i, d in enumerate(pdf_docs[:3])
        ])
        
        yt_content = "\n\n".join([
            f"YouTube Chunk {i+1}:\n{d.page_content[:500]}" 
            for i, d in enumerate(yt_docs[:3])
        ])
        
        # Construct contradiction detection prompt
        contradiction_prompt = f"""You are a critical analyst comparing two information sources. Your task is to identify any contradictions, conflicts, or significant differences between them.

PDF SOURCE CONTENT:
{pdf_content}

YOUTUBE VIDEO CONTENT:
{yt_content}

USER'S QUESTION CONTEXT: {state['question']}

Analyze these sources carefully and return a JSON object with this EXACT structure:
{{
    "has_contradictions": true or false,
    "conflicts": [
        {{
            "type": "factual_disagreement" or "temporal_conflict" or "emphasis_difference",
            "severity": "high" or "medium" or "low",
            "pdf_claim": "exact quote or paraphrase from PDF",
            "youtube_claim": "exact quote or paraphrase from YouTube",
            "explanation": "brief explanation of why this is a conflict"
        }}
    ],
    "alignment_score": 0-100
}}

IMPORTANT GUIDELINES:
- Only flag GENUINE contradictions (factual disagreements, outdated info, conflicting recommendations)
- DO NOT flag stylistic differences or different levels of detail as contradictions
- "factual_disagreement" = sources state opposite facts
- "temporal_conflict" = one source appears outdated compared to the other
- "emphasis_difference" = sources agree but emphasize different aspects
- alignment_score = 100 means perfect alignment, 0 means completely contradictory
- Be precise and only include real conflicts

Return ONLY the JSON object, no additional text.
"""
        
        try:
            response = llm.invoke([SystemMessage(content=contradiction_prompt)])
            
            # Parse JSON response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            contradiction_data = json.loads(content)
            
            # Log results
            alignment = contradiction_data.get('alignment_score', 0)
            num_conflicts = len(contradiction_data.get('conflicts', []))
            logger.info(f"✅ CONTRADICTION ANALYSIS COMPLETE:")
            logger.info(f"   - Alignment Score: {alignment}%")
            logger.info(f"   - Conflicts Found: {num_conflicts}")
            
            return {"contradictions": contradiction_data}
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from contradiction detection: {e}")
            logger.error(f"Raw response: {response.content[:200]}")
            return {
                "contradictions": {
                    "status": "error",
                    "has_contradictions": False,
                    "conflicts": [],
                    "error_message": "Failed to parse response"
                }
            }
        except Exception as e:
            logger.error(f"Error in contradiction detection: {e}")
            return {
                "contradictions": {
                    "status": "error",
                    "has_contradictions": False,
                    "conflicts": []
                }
            }

    # ===== NODE 3: GAP ANALYSIS =====
    def gap_analysis_node(state: GraphState) -> Dict:
        """
        Identifies what topics each source covers that the other doesn't.
        """
        logger.info("🔍 ANALYZING coverage gaps between sources...")
        
        pdf_docs = state.get("pdf_docs", [])
        yt_docs = state.get("yt_docs", [])
        
        # Skip if only one source type
        if not pdf_docs or not yt_docs:
            logger.info("⚠️ Only one source type - skipping gap analysis")
            return {
                "gaps": {
                    "status": "single_source",
                    "pdf_only_topics": [],
                    "youtube_only_topics": [],
                    "shared_topics": []
                }
            }
        
        # Prepare summaries of each source type
        pdf_summary = "\n\n".join([
            f"PDF Excerpt {i+1}:\n{d.page_content[:300]}" 
            for i, d in enumerate(pdf_docs[:5])
        ])
        
        yt_summary = "\n\n".join([
            f"YouTube Excerpt {i+1}:\n{d.page_content[:300]}" 
            for i, d in enumerate(yt_docs[:5])
        ])
        
        gap_prompt = f"""You are an educational content analyst. Compare these two sources and identify what each covers that the other doesn't.

PDF SOURCE CONTENT:
{pdf_summary}

YOUTUBE VIDEO CONTENT:
{yt_summary}

USER'S QUESTION CONTEXT: {state['question']}

Return a JSON object with this EXACT structure:
{{
    "pdf_only_topics": ["topic1", "topic2"],
    "youtube_only_topics": ["topic3", "topic4"],
    "shared_topics": ["topic5", "topic6"],
    "depth_differences": [
        {{
            "topic": "topic_name",
            "pdf_depth": "theoretical" or "practical" or "surface",
            "youtube_depth": "theoretical" or "practical" or "surface",
            "recommendation": "which source to prioritize for this topic and why"
        }}
    ],
    "practical_examples": {{
        "in_youtube_not_pdf": ["example1", "example2"],
        "in_pdf_not_youtube": ["example3"]
    }}
}}

GUIDELINES:
- Be specific about topics (e.g., "mitochondrial ATP production" not just "biology")
- "theoretical" = heavy on concepts/formulas, "practical" = step-by-step examples, "surface" = brief overview
- Focus on substantive differences, not just formatting
- Identify which source is better for learning different aspects

Return ONLY the JSON object, no additional text.
"""
        
        try:
            response = llm.invoke([SystemMessage(content=gap_prompt)])
            
            # Parse JSON response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            gap_data = json.loads(content)
            
            # Log results
            pdf_unique = len(gap_data.get('pdf_only_topics', []))
            yt_unique = len(gap_data.get('youtube_only_topics', []))
            shared = len(gap_data.get('shared_topics', []))
            logger.info(f"✅ GAP ANALYSIS COMPLETE:")
            logger.info(f"   - PDF-only topics: {pdf_unique}")
            logger.info(f"   - YouTube-only topics: {yt_unique}")
            logger.info(f"   - Shared topics: {shared}")
            
            return {"gaps": gap_data}
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from gap analysis: {e}")
            logger.error(f"Raw response: {response.content[:200]}")
            return {
                "gaps": {
                    "status": "error",
                    "pdf_only_topics": [],
                    "youtube_only_topics": [],
                    "shared_topics": []
                }
            }
        except Exception as e:
            logger.error(f"Error in gap analysis: {e}")
            return {
                "gaps": {
                    "status": "error"
                }
            }

    # ===== NODE 4: SYNTHESIS WITH CITATIONS =====
    def synthesize_node(state: GraphState) -> Dict:
        """
        Generates final answer with inline citations and awareness of contradictions/gaps.
        """
        logger.info("🧠 AGENT BRAIN: Synthesizing answer with citations and metadata awareness...")
        
        contradictions = state.get("contradictions", {})
        gaps = state.get("gaps", {})
        pdf_docs = state.get("pdf_docs", [])
        yt_docs = state.get("yt_docs", [])
        
        # Build base synthesis prompt
        synthesis_prompt = f"""You are the Nexus Agent - an expert at synthesizing information from multiple sources with precision and clarity.

YOUR CORE TASK:
Answer the user's question by synthesizing information from both PDF and YouTube sources provided.

MANDATORY CITATION RULES:
- Every factual claim MUST be cited
- Use format: [PDF-p.X] for PDF sources (where X is the page number)
- Use format: [YOUTUBE-M:SS] for video sources (use approximate timestamps like 0:00, 2:30, 5:45)
- Multiple sources for one claim: [PDF-p.5][YOUTUBE-3:45]
- Place citations immediately after the claim they support

CITATION EXAMPLE:
"Mitochondria are responsible for cellular energy production [PDF-p.12]. Recent studies show their efficiency varies by tissue type [YOUTUBE-8:23], which has implications for metabolic diseases [PDF-p.15]."

CONTEXT FROM SOURCES:
{state['context']}

USER'S QUESTION: {state['question']}
"""
        
        # Add contradiction awareness
        if contradictions.get("has_contradictions"):
            conflicts = contradictions.get("conflicts", [])
            conflict_text = "\n".join([
                f"• {c.get('severity', 'unknown').upper()} CONFLICT ({c.get('type', 'unknown')}):\n"
                f"  - PDF states: {c.get('pdf_claim', 'N/A')}\n"
                f"  - YouTube states: {c.get('youtube_claim', 'N/A')}\n"
                f"  - Issue: {c.get('explanation', 'N/A')}"
                for c in conflicts
            ])
            
            synthesis_prompt += f"""

⚠️ IMPORTANT - CONTRADICTIONS DETECTED BETWEEN SOURCES:
{conflict_text}

When addressing contradictions in your answer:
1. Acknowledge the disagreement explicitly
2. Present both perspectives fairly with proper citations
3. If possible, explain WHY the sources might disagree
4. If one source is more authoritative/recent, note that
5. Help the user understand which perspective might be more reliable
"""
        
        # Add gap analysis awareness
        if gaps.get("status") != "single_source" and gaps.get("status") != "error":
            pdf_only = gaps.get("pdf_only_topics", [])
            yt_only = gaps.get("youtube_only_topics", [])
            
            if pdf_only or yt_only:
                gap_text = ""
                if pdf_only:
                    gap_text += f"\n- Topics ONLY in PDF: {', '.join(pdf_only[:3])}"
                if yt_only:
                    gap_text += f"\n- Topics ONLY in YouTube: {', '.join(yt_only[:3])}"
                
                synthesis_prompt += f"""

📊 COVERAGE ANALYSIS:
The sources have complementary coverage:{gap_text}

Consider mentioning if the user would benefit from consulting a specific source for certain aspects.
"""
        
        synthesis_prompt += """

NOW GENERATE YOUR ANSWER:
- Be clear, accurate, and well-structured
- Use proper citations for every claim
- Address any contradictions appropriately
- Provide practical value to the user
- If sources are incomplete, acknowledge what's missing
"""
        
        try:
            response = llm.invoke([
                SystemMessage(content=synthesis_prompt),
                HumanMessage(content=state["question"])
            ])
            
            raw_answer = response.content
            
            # Extract and enrich citations
            citations_found = parse_citations(raw_answer)
            citation_metadata = enrich_with_citation_links(raw_answer, pdf_docs, yt_docs)
            
            logger.info(f"✅ SYNTHESIS COMPLETE:")
            logger.info(f"   - Answer length: {len(raw_answer)} characters")
            logger.info(f"   - Citations used: {len(citations_found)}")
            
            return {
                "answer": raw_answer,
                "citations": citation_metadata
            }
            
        except Exception as e:
            logger.error(f"Error in synthesis: {e}")
            return {
                "answer": "I encountered an error while synthesizing the answer. Please try rephrasing your question.",
                "citations": {}
            }

    # ===== BUILD THE GRAPH WORKFLOW =====
    logger.info("🔧 Building Nexus reasoning graph...")
    
    workflow = StateGraph(GraphState)
    
    # Add all nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("detect_contradictions", contradiction_detection_node)
    workflow.add_node("gap_analysis", gap_analysis_node)
    workflow.add_node("generate", synthesize_node)

    # Define the flow
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "detect_contradictions")
    workflow.add_edge("detect_contradictions", "gap_analysis")
    workflow.add_edge("gap_analysis", "generate")
    workflow.add_edge("generate", END)

    logger.info("🚀 Nexus Reasoning Graph compiled with:")
    logger.info("   ✅ Balanced Multi-Source Retrieval")
    logger.info("   ✅ Contradiction Detection")
    logger.info("   ✅ Gap Analysis")
    logger.info("   ✅ Citation Traceability")
    
    return workflow.compile()