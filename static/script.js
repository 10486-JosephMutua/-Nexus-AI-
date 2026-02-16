document.addEventListener('DOMContentLoaded', () => {
    
    // ===== DOM ELEMENT REFERENCES =====
    
    // Ingestion Elements
    const ingestForm = document.getElementById('ingestForm');
    const ingestBtn = document.getElementById('ingestBtn');
    const ingestionSection = document.getElementById('ingestion-section');
    
    // Chat Elements
    const chatSection = document.getElementById('chat-section');
    const askBtn = document.getElementById('askBtn');
    const questionInput = document.getElementById('question');
    const answerDiv = document.getElementById('answer');
    
    // Metadata Panel Elements
    const metadataPanel = document.getElementById('metadata-panel');
    const contradictionAlert = document.getElementById('contradiction-alert');
    const contradictionList = document.getElementById('contradiction-list');
    const contradictionCount = document.getElementById('contradiction-count');
    const alignmentBadge = document.getElementById('alignment-badge');
    const alignmentScore = document.getElementById('alignment-score');
    const gapPanel = document.getElementById('gap-panel');
    const gapContent = document.getElementById('gap-content');
    const citationPanel = document.getElementById('citation-panel');
    const citationCount = document.getElementById('citation-count');
    const pdfCitationCount = document.getElementById('pdf-citation-count');
    const ytCitationCount = document.getElementById('yt-citation-count');
    
    // Quick Question Buttons
    const quickQuestionBtns = document.querySelectorAll('.quick-question-btn');

    // ===== UTILITY FUNCTIONS =====
    
    /**
     * Shows a temporary toast notification
     */
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';
        toast.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in-up`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    /**
     * Formats the severity level with appropriate styling
     */
    function getSeverityBadge(severity) {
        const severityMap = {
            'high': { color: 'bg-red-500/20 text-red-300', icon: 'fa-exclamation-circle' },
            'medium': { color: 'bg-yellow-500/20 text-yellow-300', icon: 'fa-exclamation-triangle' },
            'low': { color: 'bg-gray-500/20 text-gray-300', icon: 'fa-info-circle' }
        };
        const config = severityMap[severity] || severityMap['low'];
        return `<span class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-bold ${config.color}">
            <i class="fas ${config.icon}"></i> ${severity.toUpperCase()}
        </span>`;
    }
    
    /**
     * Gets the alignment score color based on score value
     */
    function getAlignmentColor(score) {
        if (score >= 80) return 'text-green-400';
        if (score >= 50) return 'text-yellow-400';
        return 'text-red-400';
    }

    // ===== HANDLER: BUILD KNOWLEDGE BRIDGE =====
    ingestForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const pdfFile = document.getElementById('pdfFile').files[0];
        const ytUrl = document.getElementById('ytUrl').value.trim();

        if (!pdfFile && !ytUrl) {
            showToast("Please provide at least one source (PDF or YouTube URL).", 'error');
            return;
        }

        const formData = new FormData();
        if (pdfFile) formData.append('pdf_file', pdfFile);
        if (ytUrl) formData.append('youtube_url', ytUrl);

        // UI State: Loading Ingestion
        ingestBtn.disabled = true;
        ingestBtn.innerHTML = `<div class="loader rounded-full border-2 border-t-2 border-white/20 h-5 w-5 mr-3"></div> Processing Sources...`;

        try {
            const response = await fetch('/ingest', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.message) {
                // Success Transition
                ingestionSection.classList.add('opacity-50', 'pointer-events-none');
                ingestBtn.innerHTML = `<i class="fas fa-check-circle mr-2"></i> Bridge Built Successfully`;
                ingestBtn.className = "w-full bg-emerald-600 py-4 rounded-2xl font-bold text-lg flex justify-center items-center gap-3";
                
                // Show Chat Section with animation
                chatSection.classList.remove('hidden');
                setTimeout(() => {
                    chatSection.classList.remove('opacity-0', 'translate-y-4');
                }, 100);
                
                showToast("Knowledge Bridge constructed successfully!", 'success');
            } else {
                throw new Error(data.error || "Ingestion failed");
            }
        } catch (error) {
            showToast(error.message, 'error');
            ingestBtn.disabled = false;
            ingestBtn.innerHTML = `<span>Try Again</span> <i class="fas fa-redo text-sm"></i>`;
        }
    });

    // ===== HANDLER: DISPLAY CONTRADICTIONS =====
    function displayContradictions(contradictions) {
        if (!contradictions || contradictions.status === 'single_source' || contradictions.status === 'error') {
            contradictionAlert.classList.add('hidden');
            alignmentBadge.classList.add('hidden');
            return;
        }

        // Display alignment score
        const score = contradictions.alignment_score || 0;
        alignmentScore.textContent = score;
        alignmentScore.className = `text-3xl font-black ${getAlignmentColor(score)}`;
        alignmentBadge.classList.remove('hidden');

        // Display contradictions if any exist
        if (contradictions.has_contradictions && contradictions.conflicts && contradictions.conflicts.length > 0) {
            contradictionAlert.classList.remove('hidden');
            contradictionCount.textContent = contradictions.conflicts.length;
            
            contradictionList.innerHTML = contradictions.conflicts.map((conflict, index) => `
                <div class="bg-slate-900/50 p-3 rounded-lg border-l-4 ${
                    conflict.severity === 'high' ? 'border-red-500' :
                    conflict.severity === 'medium' ? 'border-yellow-500' : 'border-gray-500'
                }">
                    <div class="flex items-start justify-between mb-2">
                        <span class="font-semibold text-slate-300 text-xs">Conflict #${index + 1}</span>
                        ${getSeverityBadge(conflict.severity)}
                    </div>
                    <div class="space-y-2">
                        <div class="flex items-start gap-2">
                            <i class="fas fa-file-pdf text-blue-400 mt-1 text-xs"></i>
                            <p class="text-slate-400 text-xs flex-1">
                                <strong class="text-blue-300">PDF:</strong> ${conflict.pdf_claim}
                            </p>
                        </div>
                        <div class="flex items-start gap-2">
                            <i class="fas fa-video text-red-400 mt-1 text-xs"></i>
                            <p class="text-slate-400 text-xs flex-1">
                                <strong class="text-red-300">Video:</strong> ${conflict.youtube_claim}
                            </p>
                        </div>
                        <div class="bg-slate-800/50 p-2 rounded mt-2">
                            <p class="text-slate-500 text-xs italic">
                                <i class="fas fa-lightbulb text-yellow-400 mr-1"></i>
                                ${conflict.explanation}
                            </p>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            contradictionAlert.classList.add('hidden');
        }
    }

    // ===== HANDLER: DISPLAY GAP ANALYSIS =====
    function displayGapAnalysis(gaps) {
        if (!gaps || gaps.status === 'single_source' || gaps.status === 'error') {
            gapPanel.classList.add('hidden');
            return;
        }

        gapPanel.classList.remove('hidden');
        
        // Display main coverage gaps
        const pdfOnly = gaps.pdf_only_topics || [];
        const ytOnly = gaps.youtube_only_topics || [];
        const shared = gaps.shared_topics || [];

        gapContent.innerHTML = `
            <div class="bg-slate-900/50 p-3 rounded-lg">
                <h4 class="font-semibold text-blue-300 mb-2 text-xs flex items-center gap-2">
                    <i class="fas fa-file-pdf"></i> PDF Only
                    <span class="bg-blue-500/20 px-2 py-0.5 rounded-full text-xs">${pdfOnly.length}</span>
                </h4>
                ${pdfOnly.length > 0 ? `
                    <ul class="text-xs text-slate-400 space-y-1">
                        ${pdfOnly.map(t => `<li class="flex items-start gap-2">
                            <i class="fas fa-chevron-right text-blue-400 mt-1 text-xs"></i>
                            <span>${t}</span>
                        </li>`).join('')}
                    </ul>
                ` : '<p class="text-xs text-slate-500 italic">No unique topics</p>'}
            </div>
            
            <div class="bg-slate-900/50 p-3 rounded-lg">
                <h4 class="font-semibold text-red-300 mb-2 text-xs flex items-center gap-2">
                    <i class="fas fa-video"></i> Video Only
                    <span class="bg-red-500/20 px-2 py-0.5 rounded-full text-xs">${ytOnly.length}</span>
                </h4>
                ${ytOnly.length > 0 ? `
                    <ul class="text-xs text-slate-400 space-y-1">
                        ${ytOnly.map(t => `<li class="flex items-start gap-2">
                            <i class="fas fa-chevron-right text-red-400 mt-1 text-xs"></i>
                            <span>${t}</span>
                        </li>`).join('')}
                    </ul>
                ` : '<p class="text-xs text-slate-500 italic">No unique topics</p>'}
            </div>
        `;

        // Add shared topics if any
        if (shared.length > 0) {
            gapContent.innerHTML += `
                <div class="bg-slate-900/50 p-3 rounded-lg md:col-span-2">
                    <h4 class="font-semibold text-purple-300 mb-2 text-xs flex items-center gap-2">
                        <i class="fas fa-layer-group"></i> Shared Topics
                        <span class="bg-purple-500/20 px-2 py-0.5 rounded-full text-xs">${shared.length}</span>
                    </h4>
                    <div class="flex flex-wrap gap-2">
                        ${shared.map(t => `<span class="text-xs bg-purple-500/10 text-purple-300 px-2 py-1 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        // Display practical examples if available
        const practicalExamples = gaps.practical_examples;
        if (practicalExamples && (practicalExamples.in_youtube_not_pdf?.length > 0 || practicalExamples.in_pdf_not_youtube?.length > 0)) {
            document.getElementById('practical-examples').classList.remove('hidden');
            document.getElementById('practical-content').innerHTML = `
                ${practicalExamples.in_youtube_not_pdf?.length > 0 ? `
                    <div class="bg-red-900/20 p-2 rounded">
                        <p class="text-red-300 font-semibold mb-1">🎥 Video Examples:</p>
                        <ul class="text-slate-400 space-y-1">
                            ${practicalExamples.in_youtube_not_pdf.map(ex => `<li>• ${ex}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${practicalExamples.in_pdf_not_youtube?.length > 0 ? `
                    <div class="bg-blue-900/20 p-2 rounded">
                        <p class="text-blue-300 font-semibold mb-1">📄 PDF Examples:</p>
                        <ul class="text-slate-400 space-y-1">
                            ${practicalExamples.in_pdf_not_youtube.map(ex => `<li>• ${ex}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
        } else {
            document.getElementById('practical-examples').classList.add('hidden');
        }

        // Display depth differences if available
        const depthDifferences = gaps.depth_differences;
        if (depthDifferences && depthDifferences.length > 0) {
            document.getElementById('depth-differences').classList.remove('hidden');
            document.getElementById('depth-content').innerHTML = depthDifferences.map(diff => `
                <div class="bg-slate-900/50 p-2 rounded">
                    <p class="font-semibold text-slate-300 mb-1">${diff.topic}</p>
                    <div class="grid grid-cols-2 gap-2 text-xs mb-1">
                        <span class="text-blue-400">📄 PDF: ${diff.pdf_depth}</span>
                        <span class="text-red-400">🎥 Video: ${diff.youtube_depth}</span>
                    </div>
                    <p class="text-slate-500 text-xs italic">💡 ${diff.recommendation}</p>
                </div>
            `).join('');
        } else {
            document.getElementById('depth-differences').classList.add('hidden');
        }
    }

    // ===== HANDLER: DISPLAY CITATIONS =====
    function displayCitations(citations, answerText) {
        if (!citations || Object.keys(citations).length === 0) {
            citationPanel.classList.add('hidden');
            return;
        }

        citationPanel.classList.remove('hidden');
        
        // Count citations by type
        let pdfCount = 0;
        let ytCount = 0;
        
        Object.values(citations).forEach(citation => {
            if (citation.type === 'pdf') pdfCount++;
            if (citation.type === 'youtube') ytCount++;
        });

        citationCount.textContent = Object.keys(citations).length;
        pdfCitationCount.textContent = `${pdfCount} PDF`;
        ytCitationCount.textContent = `${ytCount} Video`;

        // Make citations hoverable in the answer text
        let enrichedHTML = answerDiv.innerHTML;
        
        Object.keys(citations).forEach(citationKey => {
            const citationData = citations[citationKey];
            const snippet = citationData.snippet.replace(/"/g, '&quot;');
            
            // Create regex pattern that escapes special characters
            const escapedKey = citationKey.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedKey, 'g');
            
            // Replace with styled citation link
            enrichedHTML = enrichedHTML.replace(
                regex,
                `<span class="citation-link text-blue-400 cursor-help border-b border-blue-400 border-dotted" 
                       data-snippet="${snippet}" 
                       title="${snippet}">
                    ${citationKey}
                </span>`
            );
        });
        
        answerDiv.innerHTML = enrichedHTML;
    }

    // ===== HANDLER: SYNTHESIZE QUERY =====
    const handleQuery = async () => {
        const query = questionInput.value.trim();
        if (!query) {
            showToast("Please enter a question", 'error');
            return;
        }

        // UI State: Loading Query
        askBtn.disabled = true;
        askBtn.innerHTML = `<div class="loader rounded-full border-2 border-t-2 border-white/20 h-5 w-5"></div>`;
        answerDiv.innerHTML = `
            <div class="flex flex-col gap-4 animate-pulse">
                <div class="h-4 bg-slate-800 rounded w-3/4"></div>
                <div class="h-4 bg-slate-800 rounded w-1/2"></div>
                <div class="h-4 bg-slate-800 rounded w-5/6"></div>
                <p class="text-xs text-slate-500 uppercase tracking-widest mt-2 flex items-center gap-2">
                    <i class="fas fa-brain"></i>
                    Nexus is reasoning across sources...
                </p>
            </div>
        `;

        // Hide metadata panels during loading
        metadataPanel.classList.add('hidden');

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: query })
            });
            
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            
            const data = await response.json();

            if (data.answer) {
                // Render main answer with Markdown
                answerDiv.innerHTML = marked.parse(data.answer);
                
                // Show metadata panel
                metadataPanel.classList.remove('hidden');
                
                // Display all metadata
                displayContradictions(data.contradictions);
                displayGapAnalysis(data.gaps);
                displayCitations(data.citations, data.answer);
                
                // Success feedback
                showToast("Analysis complete!", 'success');
                
            } else {
                throw new Error(data.error || "No answer received");
            }

        } catch (error) {
            console.error('Query error:', error);
            answerDiv.innerHTML = `
                <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                    <p class="text-red-400 flex items-center gap-2">
                        <i class="fas fa-exclamation-circle"></i>
                        Error: ${error.message}
                    </p>
                    <p class="text-slate-500 text-sm mt-2">Please try again or rephrase your question.</p>
                </div>
            `;
            showToast(error.message, 'error');
        } finally {
            askBtn.disabled = false;
            askBtn.innerHTML = `<i class="fas fa-paper-plane px-2"></i>`;
            questionInput.value = '';
        }
    };

    // ===== EVENT LISTENERS =====
    
    // Ask button click
    askBtn.addEventListener('click', handleQuery);
    
    // Enter key in question input
    questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleQuery();
        }
    });
    
    // Quick question buttons
    quickQuestionBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const question = btn.getAttribute('data-question');
            questionInput.value = question;
            handleQuery();
        });
    });

    // ===== INITIALIZATION =====
    console.log('🚀 Nexus AI Enhanced Edition Loaded');
    console.log('✅ Contradiction Detection Active');
    console.log('✅ Citation Traceability Active');
    console.log('✅ Gap Analysis Active');
});