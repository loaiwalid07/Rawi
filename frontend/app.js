// RAWI - The Storyteller Frontend Application

class RawiApp {
    constructor() {
        this.apiUrl = this.getApiUrl();
        this.currentStory = null;
        this.videoPlayer = null;
        this.audioPlayer = null;
        this.isPlaying = false;
        this.currentSegment = 0;
        
        this.initializeEventListeners();
    }

    getApiUrl() {
        // Use the same origin as the frontend (works for both local and deployed)
        return window.location.origin;
    }

    initializeEventListeners() {
        // Story form submission
        document.getElementById('storyForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.generateStory();
        });

        // Player controls
        document.getElementById('closeBtn').addEventListener('click', () => {
            this.closePlayer();
        });

        document.getElementById('playPauseBtn').addEventListener('click', () => {
            this.togglePlayPause();
        });

        document.getElementById('rewindBtn').addEventListener('click', () => {
            this.seek(-10);
        });

        document.getElementById('forwardBtn').addEventListener('click', () => {
            this.seek(10);
        });

        document.getElementById('muteBtn').addEventListener('click', () => {
            this.toggleMute();
        });

        // Video player events
        const video = document.getElementById('storyVideo');
        video.addEventListener('timeupdate', () => this.onTimeUpdate());
        video.addEventListener('loadedmetadata', () => this.onVideoLoaded());
        video.addEventListener('ended', () => this.onVideoEnded());

        // Retry button
        document.getElementById('retryBtn').addEventListener('click', () => {
            this.hideError();
        });
    }

    async generateStory() {
        const form = document.getElementById('storyForm');
        const formData = new FormData(form);

        const storyRequest = {
            topic: formData.get('topic'),
            audience: formData.get('audience'),
            metaphor: formData.get('metaphor') || null,
            duration_minutes: parseInt(formData.get('duration')),
            language: 'en'
        };

        // Show loading state
        this.showLoading();
        this.updateLoadingStep(1, 'Planning story');

        try {
            const response = await fetch(`${this.apiUrl}/tell-story`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(storyRequest)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Simulate progress updates (in real app, use WebSocket or polling)
            this.updateLoadingStep(2, 'Creating storyboard');
            await this.delay(1000);
            
            this.updateLoadingStep(3, 'Generating visuals');
            await this.delay(1000);
            
            this.updateLoadingStep(4, 'Creating voiceover');
            await this.delay(1000);
            
            this.updateLoadingStep(5, 'Merging video');
            await this.delay(1000);

            const storyData = await response.json();
            this.currentStory = storyData;

            this.hideLoading();
            this.showPlayer(storyData);

        } catch (error) {
            console.error('Error generating story:', error);
            this.hideLoading();
            this.showError(error.message);
        }
    }

    showPlayer(storyData) {
        const player = document.getElementById('storyPlayer');
        const form = document.querySelector('.story-form');

        // Hide form, show player
        form.style.display = 'none';
        player.style.display = 'block';

        // Set story title
        document.getElementById('storyTitle').textContent = 
            `Story: ${storyData.segments[0]?.narration?.substring(0, 50) || 'Untitled Story'}...`;

        // Set video source
        const video = document.getElementById('storyVideo');
        const videoUrl = storyData.video_url;
        
        console.log('Video URL:', videoUrl);
        console.log('Video URL type:', typeof videoUrl);
        console.log('Video URL starts with http:', videoUrl?.startsWith('http'));
        
        // Check if video URL is valid (accept absolute or relative URLs)
        if (videoUrl && (videoUrl.startsWith('http') || videoUrl.startsWith('https') || videoUrl.startsWith('file://') || videoUrl.startsWith('/'))) {
            video.src = videoUrl;
            console.log('Setting video src:', video.src);
        } else {
            console.error('Invalid video URL:', videoUrl);
            // Show error in player
            const videoContainer = document.querySelector('.video-container');
            videoContainer.innerHTML = `
                <div class="video-error" style="padding: 40px; text-align: center; background: #1a1a2e; border-radius: 10px;">
                    <h3 style="color: #ff6b6b;">⚠️ Video Not Available</h3>
                    <p style="color: #ccc;">The video is still being processed or an error occurred.</p>
                    <p style="color: #888; font-size: 12px; word-break: break-all;">URL: ${videoUrl || 'No URL'}</p>
                    <a href="${videoUrl}" target="_blank" class="btn btn-primary" style="margin-top: 15px; display: inline-block;">
                        Open Video Directly
                    </a>
                </div>
            `;
        }

        // Set details
        document.getElementById('detailTopic').textContent = storyData.segments[0]?.narration?.split(' ').slice(0, 3).join(' ') || '-';
        document.getElementById('detailAudience').textContent = storyData.segments[0]?.emotion || 'General';
        document.getElementById('detailDuration').textContent = `${storyData.segments.length * 15}s`;

        // Set narration summary
        document.getElementById('storyNarration').textContent = storyData.narration_text;

        // Set resource links
        document.getElementById('downloadVideo').href = storyData.video_url || '#';
        document.getElementById('downloadAudio').href = storyData.voiceover_url || '#';

        // Initialize text bubbles
        this.initializeTextBubbles(storyData.interleaved_stream);

        // Load video
        if (video.src) {
            video.load();
            
            // Add error handler
            video.onerror = (e) => {
                console.error('Video error:', e);
                const videoContainer = document.querySelector('.video-container');
                videoContainer.innerHTML = `
                    <div class="video-error" style="padding: 40px; text-align: center; background: #1a1a2e; border-radius: 10px;">
                        <h3 style="color: #ff6b6b;">⚠️ Video Error</h3>
                        <p style="color: #ccc;">The video could not be loaded.</p>
                        <a href="${videoUrl}" target="_blank" class="btn btn-primary" style="margin-top: 15px; display: inline-block;">
                            Open Video Directly
                        </a>
                    </div>
                `;
            };
        }
    }

    initializeTextBubbles(stream) {
        const textBubbles = document.getElementById('textBubbles');
        textBubbles.innerHTML = '';

        // Filter for narration segments
        const narrationSegments = stream.filter(seg => seg.type === 'NARRATION');

        if (narrationSegments.length === 0) {
            textBubbles.innerHTML = '<p class="text-bubble">Loading narration...</p>';
            return;
        }

        // Create a text bubble for each narration
        narrationSegments.forEach((segment, index) => {
            const bubble = document.createElement('p');
            bubble.className = 'text-bubble';
            bubble.id = `text-bubble-${index}`;
            bubble.textContent = segment.content;
            bubble.style.display = 'none'; // Hide initially
            textBubbles.appendChild(bubble);
        });
    }

    onVideoLoaded() {
        const video = document.getElementById('storyVideo');
        const totalTime = document.getElementById('totalTime');
        
        // Update total time display
        totalTime.textContent = this.formatTime(video.duration);
    }

    onTimeUpdate() {
        const video = document.getElementById('storyVideo');
        const progressBar = document.getElementById('progressBar');
        const currentTime = document.getElementById('currentTime');

        if (!video || !video.duration || isNaN(video.duration)) return;

        // Update progress bar
        const progress = (video.currentTime / video.duration) * 100;
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }

        // Update time display
        if (currentTime) {
            currentTime.textContent = this.formatTime(video.currentTime);
        }

        // Update text bubbles based on current time
        this.updateTextBubbles(video.currentTime);
    }

    updateTextBubbles(currentTime) {
        if (!this.currentStory) return;

        const stream = this.currentStory.interleaved_stream;
        const narrationSegments = stream.filter(seg => seg.type === 'NARRATION');

        // Find which segment should be displayed
        let activeIndex = -1;
        for (let i = narrationSegments.length - 1; i >= 0; i--) {
            if (currentTime >= narrationSegments[i].timestamp) {
                activeIndex = i;
                break;
            }
        }

        // Show active bubble, hide others
        narrationSegments.forEach((segment, index) => {
            const bubble = document.getElementById(`text-bubble-${index}`);
            if (bubble) {
                if (index === activeIndex) {
                    bubble.style.display = 'block';
                    bubble.style.animation = 'none';
                    setTimeout(() => bubble.style.animation = 'fadeIn 0.5s ease-in', 10);
                } else {
                    bubble.style.display = 'none';
                }
            }
        });
    }

    onVideoEnded() {
        this.isPlaying = false;
        this.updatePlayPauseButton();
    }

    togglePlayPause() {
        const video = document.getElementById('storyVideo');
        
        if (this.isPlaying) {
            video.pause();
        } else {
            video.play();
        }
        
        this.isPlaying = !this.isPlaying;
        this.updatePlayPauseButton();
    }

    updatePlayPauseButton() {
        const btn = document.getElementById('playPauseBtn');
        btn.textContent = this.isPlaying ? '⏸️ Pause' : '▶️ Play';
    }

    seek(seconds) {
        const video = document.getElementById('storyVideo');
        if (!video || !video.duration || isNaN(video.duration)) return;
        video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
    }

    toggleMute() {
        const video = document.getElementById('storyVideo');
        const btn = document.getElementById('muteBtn');
        
        video.muted = !video.muted;
        btn.textContent = video.muted ? '🔇' : '🔊';
    }

    closePlayer() {
        const player = document.getElementById('storyPlayer');
        const form = document.querySelector('.story-form');

        // Stop video
        const video = document.getElementById('storyVideo');
        video.pause();
        video.src = '';

        // Show form, hide player
        form.style.display = 'block';
        player.style.display = 'none';

        this.currentStory = null;
        this.isPlaying = false;
    }

    showLoading() {
        const overlay = document.getElementById('loadingOverlay');
        overlay.style.display = 'flex';
        
        // Reset steps
        for (let i = 1; i <= 5; i++) {
            const step = document.getElementById(`step${i}`);
            step.classList.remove('active', 'completed');
        }
    }

    updateLoadingStep(step, message) {
        document.getElementById('loadingMessage').textContent = message;
        
        // Mark previous steps as completed
        for (let i = 1; i < step; i++) {
            const stepEl = document.getElementById(`step${i}`);
            stepEl.classList.add('completed');
            stepEl.classList.remove('active');
        }

        // Mark current step as active
        const currentStep = document.getElementById(`step${step}`);
        currentStep.classList.add('active');
    }

    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        overlay.style.display = 'none';
    }

    showError(message) {
        const errorEl = document.getElementById('errorMessage');
        document.getElementById('errorText').textContent = message || 'Something went wrong. Please try again.';
        errorEl.style.display = 'block';
    }

    hideError() {
        document.getElementById('errorMessage').style.display = 'none';
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new RawiApp();
});

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RawiApp;
}
