// frontend-react/src/components/VideoPlayer.tsx
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
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, segments }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const seekTo = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play();
    }
  };

  // Calculate progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="relative">
      <div className="aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-black">
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="w-full h-full object-contain"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
        />
      </div>
      
      {/* Custom timeline below video */}
      <div className="mt-4 space-y-2">
        <div className="flex justify-between text-xs text-white/40 font-mono">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
        <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div 
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-indigo-500 to-purple-500"
            style={{ width: `${progress}%` }}
          />
          {/* Segment markers */}
          {segments.map((seg, i) => {
            const pos = duration > 0 ? (seg.timestamp / duration) * 100 : 0;
            return (
              <div
                key={i}
                className="absolute top-0 w-0.5 h-full bg-white/30 cursor-pointer hover:bg-indigo-400"
                style={{ left: `${pos}%` }}
                onClick={() => seekTo(seg.timestamp)}
                title={`Segment ${i + 1}: ${seg.content?.substring(0, 30)}...`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default VideoPlayer;
