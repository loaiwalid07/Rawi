import React, { useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

interface VideoPlayerProps {
  videoUrl: string;
  segments: Segment[];
  onTimeUpdate?: (time: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, segments, onTimeUpdate }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, Math.min(time, duration));
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Calculate progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="relative">
      <div className="aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-slate-900">
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
        />
        
        {/* Custom Controls Overlay */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-slate-900/90 via-slate-900/50 to-transparent pt-12 px-4">
 pb-4          {/* Progress Bar */}
          <div className="relative h-1.5 bg-white/20 rounded-full mb-3 cursor-pointer group">
            <motion.div 
              className="absolute left-0 top-0 h-full bg-blue-500 rounded-full"
              style={{ width: `${progress}%` }}
            />
            {/* Segment markers */}
            {segments.map((seg, i) => {
              const pos = duration > 0 ? (seg.timestamp / duration) * 100 : 0;
              return (
                <div
                  key={i}
                  className="absolute top-0 w-0.5 h-full bg-white/40 cursor-pointer hover:bg-blue-400"
                  style={{ left: `${pos}%` }}
                  onClick={() => handleSeek(seg.timestamp)}
                  title={`Segment ${i + 1}`}
                />
              );
            })}
          </div>

          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* Play/Pause */}
              <button 
                onClick={togglePlay}
                className="w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-500 flex items-center justify-center text-white transition-colors"
              >
                {isPlaying ? (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                  </svg>
                ) : (
                  <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                )}
              </button>

              {/* Skip Back */}
              <button 
                onClick={() => handleSeek(currentTime - 10)}
                className="text-white/70 hover:text-white transition-colors p-2 text-sm font-medium"
              >
                -10s
              </button>

              {/* Skip Forward */}
              <button 
                onClick={() => handleSeek(currentTime + 10)}
                className="text-white/70 hover:text-white transition-colors p-2 text-sm font-medium"
              >
                +10s
              </button>

              {/* Time Display */}
              <span className="text-white/70 text-sm font-mono ml-2">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
