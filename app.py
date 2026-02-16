import os
import logging
from flask import Flask, render_template, request, jsonify
from ingest import process_sources
from graph import create_nexus_graph
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("NEXUS_WEB")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads folder if doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

nexus_retriever = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ingest', methods=['POST'])
def ingest():
    global nexus_retriever
    logger.info("--- NEW INGESTION REQUEST RECEIVED ---")
    
    yt_url = request.form.get('youtube_url')
    pdf_file = request.files.get('pdf_file')

    pdf_path = None
    if pdf_file:
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
        pdf_file.save(pdf_path)

    nexus_retriever = process_sources(pdf_path, yt_url)
    return jsonify({"message": "Bridge Built!"})

@app.route('/ask', methods=['POST'])
def ask():
    logger.info("--- NEW QUERY RECEIVED ---")
    if not nexus_retriever:
        return jsonify({"error": "No Knowledge Base"}), 400
    
    q = request.json.get('question')
    graph = create_nexus_graph(nexus_retriever)
    result = graph.invoke({"question": q})
    
    logger.info("--- REQUEST FINISHED ---")
    
    # Return enhanced response with all metadata
    return jsonify({
        "answer": result.get("answer"),
        "contradictions": result.get("contradictions", {}),
        "citations": result.get("citations", {}),
        "gaps": result.get("gaps", {})
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)