/**
 * Story Player Component
 * Handles video playback and synchronized text bubble display
 */

class StoryPlayer {
    constructor(videoElement, textBubblesElement, options = {}) {
        this.video = videoElement;
        this.textBubblesContainer = textBubblesElement;
        this.currentBubble = null;
        this.segments = [];
        this.isInitialized = false;
        
        this.options = {
            bubbleClass: 'text-bubble',
            transitionDuration: 500,
            ...options
        };

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.video.addEventListener('seeked', () => this.onSeeked());
        this.video.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.addEventListener('play', () => this.onPlay());
        this.video.addEventListener('pause', () => this.onPause());
        this.video.addEventListener('ended', () => this.onEnded());
    }

    loadStory(storyData) {
        this.segments = storyData.interleaved_stream.filter(seg => seg.type === 'NARRATION');
        this.textBubblesContainer.innerHTML = '';
        
        // Create bubbles for each narration segment
        this.segments.forEach((segment, index) => {
            const bubble = this.createBubble(segment, index);
            this.textBubblesContainer.appendChild(bubble);
        });

        this.isInitialized = true;
    }

    createBubble(segment, index) {
        const bubble = document.createElement('p');
        bubble.className = this.options.bubbleClass;
        bubble.id = `bubble-${index}`;
        bubble.textContent = segment.content;
        bubble.dataset.timestamp = segment.timestamp;
        bubble.dataset.duration = segment.duration;
        bubble.style.display = 'none';
        return bubble;
    }

    onTimeUpdate() {
        if (!this.isInitialized) return;

        const currentTime = this.video.currentTime;
        const activeBubble = this.findActiveBubble(currentTime);

        if (activeBubble !== this.currentBubble) {
            this.showBubble(activeBubble);
            this.currentBubble = activeBubble;
        }

        this.updateBubbleTransition(currentTime);
    }

    findActiveBubble(currentTime) {
        // Find the bubble that should be displayed at current time
        for (let i = this.segments.length - 1; i >= 0; i--) {
            if (currentTime >= this.segments[i].timestamp) {
                return i;
            }
        }
        return -1;
    }

    showBubble(bubbleIndex) {
        // Hide all bubbles
        const allBubbles = this.textBubblesContainer.querySelectorAll(`.${this.options.bubbleClass}`);
        allBubbles.forEach(bubble => {
            bubble.style.display = 'none';
            bubble.style.opacity = '0';
        });

        // Show active bubble
        if (bubbleIndex >= 0 && bubbleIndex < this.segments.length) {
            const bubble = document.getElementById(`bubble-${bubbleIndex}`);
            if (bubble) {
                bubble.style.display = 'block';
                
                // Trigger reflow
                bubble.offsetHeight;
                
                // Fade in
                bubble.style.transition = `opacity ${this.options.transitionDuration}ms ease-in`;
                bubble.style.opacity = '1';
            }
        }
    }

    updateBubbleTransition(currentTime) {
        if (this.currentBubble >= 0 && this.currentBubble < this.segments.length) {
            const segment = this.segments[this.currentBubble];
            const bubble = document.getElementById(`bubble-${this.currentBubble}`);
            
            if (bubble && segment) {
                const timeInSegment = currentTime - segment.timestamp;
                const progress = Math.min(timeInSegment / segment.duration, 1);
                
                // Update bubble opacity based on progress
                if (progress > 0.8) {
                    bubble.style.opacity = 1 - ((progress - 0.8) * 5); // Fade out in last 20%
                } else {
                    bubble.style.opacity = '1';
                }
            }
        }
    }

    onSeeked() {
        // Update bubble immediately after seek
        const currentTime = this.video.currentTime;
        this.currentBubble = this.findActiveBubble(currentTime);
        this.showBubble(this.currentBubble);
    }

    onLoadedMetadata() {
        // Video metadata loaded, ready to play
        console.log('Video loaded:', this.video.duration);
    }

    onPlay() {
        console.log('Video playing');
    }

    onPause() {
        console.log('Video paused');
    }

    onEnded() {
        console.log('Video ended');
    }

    // Public methods
    play() {
        return this.video.play();
    }

    pause() {
        this.video.pause();
    }

    seekTo(time) {
        this.video.currentTime = time;
    }

    getCurrentTime() {
        return this.video.currentTime;
    }

    getDuration() {
        return this.video.duration;
    }

    destroy() {
        // Clean up event listeners
        this.video.removeEventListener('timeupdate', () => this.onTimeUpdate());
        this.video.removeEventListener('seeked', () => this.onSeeked());
        this.video.removeEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.removeEventListener('play', () => this.onPlay());
        this.video.removeEventListener('pause', () => this.onPause());
        this.video.removeEventListener('ended', () => this.onEnded());
        
        this.textBubblesContainer.innerHTML = '';
        this.isInitialized = false;
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StoryPlayer;
}
