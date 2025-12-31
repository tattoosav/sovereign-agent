// Sovereign Agent Web Client

class SovereignAgent {
    constructor() {
        this.sessionId = null;
        this.ws = null;
        this.isConnected = false;

        // DOM elements
        this.messagesEl = document.getElementById('messages');
        this.inputEl = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.statusEl = document.getElementById('connection-status');
        this.sessionInfoEl = document.getElementById('session-info');
        this.toolsListEl = document.getElementById('tools-list');
        this.newSessionBtn = document.getElementById('new-session-btn');
        this.metricsBtn = document.getElementById('metrics-btn');
        this.modal = document.getElementById('modal');
        this.modalTitle = document.getElementById('modal-title');
        this.modalBody = document.getElementById('modal-body');
        this.modalClose = document.querySelector('.modal .close');

        // File upload elements
        this.uploadZone = document.getElementById('upload-zone');
        this.fileInput = document.getElementById('file-input');
        this.browseBtn = document.getElementById('browse-btn');
        this.analyzeBtn = document.getElementById('analyze-btn');
        this.uploadStatus = document.getElementById('upload-status');
        this.uploadDir = null;

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.checkHealth();
        await this.createSession();
        await this.loadTools();
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.clearBtn.addEventListener('click', () => this.clearChat());
        this.newSessionBtn.addEventListener('click', () => this.createSession());
        this.metricsBtn.addEventListener('click', () => this.showMetrics());
        this.modalClose.addEventListener('click', () => this.hideModal());
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.hideModal();
        });

        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // File upload events
        this.browseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.fileInput.click();
        });

        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadFiles(e.target.files);
            }
        });

        this.analyzeBtn.addEventListener('click', () => this.analyzeProject());

        // Drag and drop
        this.uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadZone.classList.add('dragover');
        });

        this.uploadZone.addEventListener('dragleave', () => {
            this.uploadZone.classList.remove('dragover');
        });

        this.uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                this.uploadFiles(e.dataTransfer.files);
            }
        });
    }

    async checkHealth() {
        try {
            const response = await fetch('/health');
            const data = await response.json();

            if (data.ollama_connected) {
                this.setStatus('connected', 'Connected');
                this.isConnected = true;
            } else {
                this.setStatus('disconnected', 'Ollama not connected');
            }
        } catch (error) {
            this.setStatus('disconnected', 'API unreachable');
            console.error('Health check failed:', error);
        }
    }

    async createSession() {
        try {
            const response = await fetch('/session/new', { method: 'POST' });
            const data = await response.json();
            this.sessionId = data.session_id;
            this.sessionInfoEl.textContent = `Session: ${this.sessionId.slice(0, 8)}...`;
            this.addSystemMessage('New session created');
            this.messagesEl.innerHTML = '';
        } catch (error) {
            console.error('Failed to create session:', error);
            this.addSystemMessage('Failed to create session');
        }
    }

    async loadTools() {
        try {
            const response = await fetch('/tools');
            const data = await response.json();

            this.toolsListEl.innerHTML = data.tools.map(tool => `
                <div class="tool-item">
                    <div class="tool-item-name">${tool.name}</div>
                    <div class="tool-item-desc">${tool.description.slice(0, 60)}...</div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to load tools:', error);
        }
    }

    async sendMessage() {
        const message = this.inputEl.value.trim();
        if (!message || !this.sessionId) return;

        // Add user message to UI
        this.addMessage('user', message);
        this.inputEl.value = '';

        // Disable input while processing
        this.sendBtn.disabled = true;
        this.setStatus('thinking', 'Thinking...');

        // Use streaming for better UX
        await this.sendMessageStreaming(message);
    }

    async sendMessageStreaming(message) {
        // Create placeholder for streaming response
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant';
        messageEl.innerHTML = `
            <div class="message-header">Sovereign Agent</div>
            <div class="message-content"><span class="loading"></span> Generating...</div>
        `;
        this.messagesEl.appendChild(messageEl);
        this.scrollToBottom();

        const contentEl = messageEl.querySelector('.message-content');
        let fullContent = '';

        try {
            const response = await fetch('/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId
                })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'chunk') {
                                fullContent += data.content;
                                contentEl.innerHTML = this.formatContent(fullContent);
                                this.scrollToBottom();
                            } else if (data.type === 'status') {
                                this.setStatus('thinking', `Task: ${data.task_type}`);
                            } else if (data.type === 'done') {
                                this.setStatus('connected', 'Connected');
                            } else if (data.type === 'error') {
                                contentEl.innerHTML = `<span class="error">Error: ${data.error}</span>`;
                                this.setStatus('disconnected', 'Error');
                            }
                        } catch (e) {
                            // Ignore parse errors for incomplete chunks
                        }
                    }
                }
            }

            // Final format
            if (fullContent) {
                contentEl.innerHTML = this.formatContent(fullContent);
            }
            this.setStatus('connected', 'Connected');

        } catch (error) {
            console.error('Streaming error:', error);
            contentEl.innerHTML = 'Error: Failed to get response';
            this.setStatus('disconnected', 'Error');

            // Fall back to non-streaming
            await this.sendMessageNonStreaming(message, messageEl);
        } finally {
            this.sendBtn.disabled = false;
        }
    }

    async sendMessageNonStreaming(message, existingEl = null) {
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId
                })
            });

            const data = await response.json();

            if (existingEl) {
                // Update existing message element
                const contentEl = existingEl.querySelector('.message-content');
                if (data.status === 'success') {
                    contentEl.innerHTML = this.formatContent(data.response);
                } else {
                    contentEl.innerHTML = `Error: ${data.error}`;
                }
            } else {
                // Add new message
                if (data.status === 'success') {
                    this.addMessage('assistant', data.response, data.tool_calls);
                } else {
                    this.addMessage('assistant', `Error: ${data.error}`);
                }
            }

            this.setStatus('connected', 'Connected');
        } catch (error) {
            console.error('Chat error:', error);
            if (existingEl) {
                existingEl.querySelector('.message-content').innerHTML = 'Error: Failed to get response';
            } else {
                this.addMessage('assistant', 'Error: Failed to get response');
            }
            this.setStatus('disconnected', 'Error');
        } finally {
            this.sendBtn.disabled = false;
        }
    }

    async clearChat() {
        if (!this.sessionId) return;

        try {
            await fetch(`/session/${this.sessionId}/reset`, { method: 'POST' });
            this.messagesEl.innerHTML = '';
            this.addSystemMessage('Conversation cleared');
        } catch (error) {
            console.error('Failed to clear chat:', error);
        }
    }

    async showMetrics() {
        if (!this.sessionId) return;

        try {
            const response = await fetch(`/session/${this.sessionId}/metrics`);
            const data = await response.json();

            this.modalTitle.textContent = 'Session Metrics';
            this.modalBody.innerHTML = `<pre>${JSON.stringify(data.metrics, null, 2)}</pre>`;
            this.showModal();
        } catch (error) {
            console.error('Failed to load metrics:', error);
        }
    }

    async uploadFiles(files) {
        if (!this.sessionId) {
            this.addSystemMessage('Please wait for session to be created');
            return;
        }

        this.uploadStatus.classList.remove('hidden');
        this.uploadStatus.textContent = `Uploading ${files.length} file(s)...`;

        const formData = new FormData();
        formData.append('session_id', this.sessionId);

        for (const file of files) {
            formData.append('files', file);
        }

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.uploadDir = data.upload_dir;
                this.analyzeBtn.disabled = false;

                const fileList = data.uploaded.map(f =>
                    f.type === 'zip' ? `${f.name} (${f.files_extracted} files extracted)` : f.name
                ).join(', ');

                this.uploadStatus.innerHTML = `<span class="success">Uploaded: ${fileList}</span>`;
                this.addSystemMessage(`Files uploaded to ${data.upload_dir}. Click "Analyze Project" to understand the codebase.`);
            } else {
                this.uploadStatus.innerHTML = `<span class="error">Upload failed</span>`;
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.uploadStatus.innerHTML = `<span class="error">Upload failed: ${error.message}</span>`;
        }
    }

    async analyzeProject() {
        if (!this.sessionId || !this.uploadDir) return;

        this.analyzeBtn.disabled = true;
        this.setStatus('thinking', 'Analyzing project...');

        try {
            const formData = new FormData();
            formData.append('session_id', this.sessionId);

            const response = await fetch('/upload/analyze', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.status === 'success') {
                const analysis = data.analysis;

                // Format analysis results
                let analysisText = `**Project Analysis**\n\n`;
                analysisText += `**Languages:** ${analysis.languages.join(', ') || 'Unknown'}\n`;
                analysisText += `**Frameworks:** ${analysis.frameworks.join(', ') || 'None detected'}\n`;
                analysisText += `**Package Managers:** ${analysis.package_managers.join(', ') || 'None detected'}\n`;
                analysisText += `**Files:** ${analysis.file_count}\n`;

                if (analysis.entry_points.length > 0) {
                    analysisText += `**Entry Points:** ${analysis.entry_points.join(', ')}\n`;
                }

                if (analysis.config_files.length > 0) {
                    analysisText += `**Config Files:** ${analysis.config_files.join(', ')}\n`;
                }

                if (Object.keys(analysis.structure).length > 0) {
                    analysisText += `\n**Structure:**\n`;
                    for (const [dir, count] of Object.entries(analysis.structure)) {
                        analysisText += `  - ${dir}/: ${count} files\n`;
                    }
                }

                if (analysis.recommendations.length > 0) {
                    analysisText += `\n**Recommendations:**\n`;
                    for (const rec of analysis.recommendations) {
                        analysisText += `  - ${rec}\n`;
                    }
                }

                this.addMessage('assistant', analysisText);

                // Auto-send a message to the agent to understand the project
                const contextMessage = `I've uploaded a project. Here's the analysis:\n${analysisText}\n\nThe project files are at: ${this.uploadDir}\n\nPlease explore the codebase and let me know what you find. What is this project about?`;
                this.inputEl.value = contextMessage;
            }

            this.setStatus('connected', 'Connected');
        } catch (error) {
            console.error('Analysis error:', error);
            this.addSystemMessage(`Analysis failed: ${error.message}`);
            this.setStatus('disconnected', 'Error');
        } finally {
            this.analyzeBtn.disabled = false;
        }
    }

    addMessage(role, content, toolCalls = []) {
        const messageEl = document.createElement('div');
        messageEl.className = `message ${role}`;

        const header = role === 'user' ? 'You' : 'Sovereign Agent';

        // Format content (simple markdown-like formatting)
        const formattedContent = this.formatContent(content);

        let toolCallsHtml = '';
        if (toolCalls && toolCalls.length > 0) {
            toolCallsHtml = `
                <div class="tool-calls">
                    <strong>Tool Calls:</strong>
                    ${toolCalls.map(tc => `
                        <div class="tool-call ${tc.success ? 'success' : 'failure'}">
                            <div class="tool-call-header">
                                <span class="tool-call-name">${tc.name}</span>
                                <span class="tool-call-status">${tc.success ? '✓' : '✗'}</span>
                            </div>
                            ${tc.result ? `<div class="tool-call-result">${this.escapeHtml(tc.result)}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }

        messageEl.innerHTML = `
            <div class="message-header">${header}</div>
            <div class="message-content">${formattedContent}</div>
            ${toolCallsHtml}
        `;

        this.messagesEl.appendChild(messageEl);
        this.scrollToBottom();
    }

    addSystemMessage(content) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message system';
        messageEl.textContent = content;
        this.messagesEl.appendChild(messageEl);
        this.scrollToBottom();
    }

    formatContent(content) {
        if (!content) return '';

        // Escape HTML first
        let formatted = this.escapeHtml(content);

        // Code blocks
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        return formatted;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    setStatus(className, text) {
        this.statusEl.className = `status ${className}`;
        this.statusEl.textContent = text;
    }

    scrollToBottom() {
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    showModal() {
        this.modal.classList.remove('hidden');
    }

    hideModal() {
        this.modal.classList.add('hidden');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.agent = new SovereignAgent();
});
