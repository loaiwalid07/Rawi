/**
 * Progress Bar Component
 * Displays and controls video playback progress
 */

class ProgressBar {
    constructor(containerElement, videoElement, options = {}) {
        this.container = containerElement;
        this.video = videoElement;
        this.isDragging = false;
        
        this.options = {
            barClass: 'progress-bar',
            fillClass: 'progress-fill',
            timeClass: 'progress-time',
            currentTimeClass: 'current-time',
            totalTimeClass: 'total-time',
            showTime: true,
            clickToSeek: true,
            ...options
        };

        this.render();
        this.setupEventListeners();
    }

    render() {
        this.container.innerHTML = '';

        // Create progress bar
        const progressBar = document.createElement('div');
        progressBar.className = this.options.barClass;

        const progressFill = document.createElement('div');
        progressFill.className = this.options.fillClass;
        progressFill.style.width = '0%';

        progressBar.appendChild(progressFill);
        this.container.appendChild(progressBar);

        this.progressBar = progressBar;
        this.progressFill = progressFill;

        // Create time display if enabled
        if (this.options.showTime) {
            const timeDisplay = document.createElement('div');
            timeDisplay.className = this.options.timeClass;

            const currentTime = document.createElement('span');
            currentTime.className = this.options.currentTimeClass;
            currentTime.textContent = '0:00';

            const totalTime = document.createElement('span');
            totalTime.className = this.options.totalTimeClass;
            totalTime.textContent = '0:00';

            timeDisplay.appendChild(currentTime);
            timeDisplay.appendChild(totalTime);
            this.container.appendChild(timeDisplay);

            this.currentTimeElement = currentTime;
            this.totalTimeElement = totalTime;
        }

        this.updateProgress();
    }

    setupEventListeners() {
        // Video events
        this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.video.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.addEventListener('durationchange', () => this.onDurationChange());

        // Progress bar click
        if (this.options.clickToSeek) {
            this.progressBar.addEventListener('click', (e) => this.onProgressBarClick(e));
            this.progressBar.addEventListener('mousedown', (e) => this.onDragStart(e));
            this.progressBar.addEventListener('touchstart', (e) => this.onDragStart(e));
        }

        // Document events for dragging
        document.addEventListener('mousemove', (e) => this.onDragMove(e));
        document.addEventListener('mouseup', () => this.onDragEnd());
        document.addEventListener('touchmove', (e) => this.onDragMove(e));
        document.addEventListener('touchend', () => this.onDragEnd());
    }

    onTimeUpdate() {
        this.updateProgress();
    }

    onLoadedMetadata() {
        this.updateTotalTime();
        this.updateProgress();
    }

    onDurationChange() {
        this.updateTotalTime();
        this.updateProgress();
    }

    onProgressBarClick(e) {
        if (this.isDragging) return;
        
        const rect = this.progressBar.getBoundingClientRect();
        const x = this.getXFromEvent(e);
        const percentage = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
        
        this.seekToPercentage(percentage);
    }

    onDragStart(e) {
        e.preventDefault();
        this.isDragging = true;
        this.progressBar.style.cursor = 'grabbing';
    }

    onDragMove(e) {
        if (!this.isDragging) return;

        const rect = this.progressBar.getBoundingClientRect();
        const x = this.getXFromEvent(e);
        const percentage = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
        
        this.progressFill.style.width = `${percentage * 100}%`;
        
        // Optional: Seek while dragging
        if (this.options.seekWhileDragging) {
            this.seekToPercentage(percentage);
        }
    }

    onDragEnd() {
        if (!this.isDragging) return;

        const rect = this.progressBar.getBoundingClientRect();
        const currentPercentage = parseFloat(this.progressFill.style.width) / 100;
        
        this.seekToPercentage(currentPercentage);
        
        this.isDragging = false;
        this.progressBar.style.cursor = '';
    }

    getXFromEvent(e) {
        if (e.touches && e.touches.length > 0) {
            return e.touches[0].clientX;
        }
        return e.clientX;
    }

    seekToPercentage(percentage) {
        const time = percentage * this.video.duration;
        this.video.currentTime = time;
    }

    updateProgress() {
        const currentTime = this.video.currentTime;
        const duration = this.video.duration;

        if (duration > 0) {
            const percentage = (currentTime / duration) * 100;
            this.progressFill.style.width = `${percentage}%`;
        }

        if (this.options.showTime && this.currentTimeElement) {
            this.currentTimeElement.textContent = this.formatTime(currentTime);
        }
    }

    updateTotalTime() {
        if (this.options.showTime && this.totalTimeElement) {
            this.totalTimeElement.textContent = this.formatTime(this.video.duration);
        }
    }

    formatTime(seconds) {
        if (!isFinite(seconds) || isNaN(seconds)) {
            return '0:00';
        }

        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // Public methods
    getCurrentProgress() {
        return parseFloat(this.progressFill.style.width) / 100;
    }

    getCurrentTime() {
        return this.video.currentTime;
    }

    getDuration() {
        return this.video.duration;
    }

    destroy() {
        // Remove event listeners
        this.video.removeEventListener('timeupdate', () => this.onTimeUpdate());
        this.video.removeEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.removeEventListener('durationchange', () => this.onDurationChange());
        this.progressBar.removeEventListener('click', (e) => this.onProgressBarClick(e));
        this.progressBar.removeEventListener('mousedown', (e) => this.onDragStart(e));
        this.progressBar.removeEventListener('touchstart', (e) => this.onDragStart(e));
        document.removeEventListener('mousemove', (e) => this.onDragMove(e));
        document.removeEventListener('mouseup', () => this.onDragEnd());
        document.removeEventListener('touchmove', (e) => this.onDragMove(e));
        document.removeEventListener('touchend', () => this.onDragEnd());

        // Clear DOM
        this.container.innerHTML = '';
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProgressBar;
}
