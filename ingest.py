import os
import json
import hashlib
import logging
import yt_dlp
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# --- 1. THE "EYES": LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - 👁️  %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NEXUS_INGEST")

# --- 2. THE CONSTANTS ---
REGISTRY_FILE = "processed_registry.json"
DB_DIR = "./nexus_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

# --- 3. THE "MEMORY" (CACHING LOGIC) ---

def get_file_hash(file_path):
    """Creates a unique SHA-256 fingerprint for a PDF file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_yt_id(url):
    """Extracts the unique 11-char YouTube ID to use as a fingerprint."""
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1].split("?")[0]
    return hashlib.md5(url.encode()).hexdigest()

def check_registry(source_ids):
    """Checks if these specific fingerprints have been processed before."""
    if not os.path.exists(REGISTRY_FILE):
        return False
    with open(REGISTRY_FILE, "r") as f:
        registry = json.load(f)
    return all(sid in registry for sid in source_ids)

def update_registry(source_ids):
    """Adds new fingerprints to our memory so we don't repeat work."""
    registry = {}
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            registry = json.load(f)
    for sid in source_ids:
        registry[sid] = True
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=4)


# --- 4. THE DATA EXTRACTORS ---

def get_youtube_content(url):
    """Robust YouTube extraction using yt-dlp."""
    logger.info(f"Connecting to YouTube Archive: {url}")
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Video')
            desc = info.get('description', 'No description available')
            logger.info(f"Successfully retrieved metadata for: {title}")
            
            content = f"VIDEO TITLE: {title}\nDESCRIPTION: {desc}"
            # FIX: Ensure metadata has 'type' field set correctly
            return [Document(
                page_content=content, 
                metadata={
                    "source": url, 
                    "type": "youtube",  # CRITICAL: This must be set
                    "title": title
                }
            )]
    except Exception as e:
        logger.error(f"Failed to extract YouTube context: {e}")
        return []


# --- 5. THE MAIN ENGINE: PROCESS SOURCES ---

def process_sources(pdf_path=None, youtube_url=None):
    """
    The core engine that builds the Knowledge Bridge.
    
    FIX APPLIED: Proper source tagging after chunking to ensure
    YouTube and PDF chunks are distinguishable.
    """
    documents = []
    current_source_ids = []

    # Step 1: Identify and Fingerprint
    if pdf_path:
        current_source_ids.append(get_file_hash(pdf_path))
    if youtube_url and youtube_url.strip():
        current_source_ids.append(extract_yt_id(youtube_url))

    # Step 2: Semantic Cache Check
    if check_registry(current_source_ids) and os.path.exists(DB_DIR):
        logger.info("✨ CACHE HIT: These sources are already in the Bridge. Skipping ingestion.")
        vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
        return vectorstore  # Return vectorstore, not retriever

    logger.info("🚀 CACHE MISS: New knowledge detected. Building Bridge...")

    # Step 3: Load Raw Content
    if pdf_path:
        logger.info(f"Shredding PDF: {os.path.basename(pdf_path)}")
        loader = PyPDFLoader(pdf_path)
        pdf_docs = loader.load()
        # IMPORTANT: Set type metadata for PDF docs
        for doc in pdf_docs:
            doc.metadata["type"] = "pdf"
        documents.extend(pdf_docs)
        logger.info(f"   - Loaded {len(pdf_docs)} PDF pages")

    if youtube_url and youtube_url.strip():
        yt_docs = get_youtube_content(youtube_url)
        # YouTube docs already have metadata["type"] = "youtube" from get_youtube_content()
        documents.extend(yt_docs)
        logger.info(f"   - Loaded {len(yt_docs)} YouTube documents")

    if not documents:
        logger.error("❌ No documents loaded. Cannot build bridge.")
        return None

    # Step 4: Recursive Shredding (Chunking)
    logger.info("Shredding content into semantic chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    
    # CRITICAL FIX: Split documents while preserving metadata
    final_chunks = []
    
    # Process PDF documents separately
    pdf_documents = [doc for doc in documents if doc.metadata.get("type") == "pdf"]
    if pdf_documents:
        pdf_chunks = text_splitter.split_documents(pdf_documents)
        logger.info(f"   - Created {len(pdf_chunks)} PDF chunks")
        final_chunks.extend(pdf_chunks)
    
    # Process YouTube documents separately
    yt_documents = [doc for doc in documents if doc.metadata.get("type") == "youtube"]
    if yt_documents:
        yt_chunks = text_splitter.split_documents(yt_documents)
        logger.info(f"   - Created {len(yt_chunks)} YouTube chunks")
        final_chunks.extend(yt_chunks)

    # Step 5: Source Tagging (Enhanced)
    # We explicitly inject the source type into the text so the LLM sees it
    logger.info("Tagging chunks with source identifiers...")
    for chunk in final_chunks:
        src_type = chunk.metadata.get("type", "unknown")
        
        # Add source tag to the beginning of content
        chunk.page_content = f"[{src_type.upper()} SOURCE]\n{chunk.page_content}"
        
        # Log for debugging
        if src_type == "youtube":
            logger.debug(f"Tagged YouTube chunk: {chunk.page_content[:50]}...")

    # Verify tagging worked
    pdf_tagged = len([c for c in final_chunks if '[PDF SOURCE]' in c.page_content])
    yt_tagged = len([c for c in final_chunks if '[YOUTUBE SOURCE]' in c.page_content])
    logger.info(f"   - Tagged {pdf_tagged} PDF chunks")
    logger.info(f"   - Tagged {yt_tagged} YouTube chunks")
    
    if yt_tagged == 0 and youtube_url:
        logger.warning("⚠️ WARNING: YouTube URL provided but no YouTube chunks tagged!")
        logger.warning("   - This may indicate an issue with YouTube content extraction")

    # Step 6: Embedding & Storage
    logger.info(f"Embedding {len(final_chunks)} total chunks into ChromaDB...")
    vectorstore = Chroma.from_documents(
        documents=final_chunks, 
        embedding=embeddings,
        persist_directory=DB_DIR
    )

    # Step 7: Update Memory
    update_registry(current_source_ids)
    
    logger.info("✅ KNOWLEDGE BRIDGE BUILT AND CACHED.")
    
    # Return the vectorstore itself (not just retriever)
    # This allows graph.py to create custom retrievers
    return vectorstore