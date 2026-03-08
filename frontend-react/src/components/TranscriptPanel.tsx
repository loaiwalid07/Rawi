// frontend-react/src/components/TranscriptPanel.tsx
import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

interface TranscriptPanelProps {
  segments: Segment[];
  currentTime: number;
  onSegmentClick?: (time: number) => void;
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  segments,
  currentTime,
  onSegmentClick
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Filter to only narration segments
  const narrationSegments = segments.filter(seg => 
    seg.type === 'NARRATION' || seg.type === 'NARRATION_BLOB'
  );

  // Find active segment based on current time
  const activeIndex = narrationSegments.findIndex((seg, i) => {
    const nextSeg = narrationSegments[i + 1];
    return currentTime >= seg.timestamp && (!nextSeg || currentTime < nextSeg.timestamp);
  });

  // Auto-scroll to active segment
  useEffect(() => {
    if (activeIndex >= 0 && containerRef.current) {
      const activeElement = containerRef.current.children[activeIndex] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeIndex]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
        <h3 className="text-indigo-400 font-semibold">Transcript</h3>
      </div>
      
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent"
      >
        <AnimatePresence>
          {narrationSegments.map((seg, i) => {
            const isActive = i === activeIndex;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`
                  p-4 rounded-xl cursor-pointer transition-all duration-300
                  ${isActive 
                    ? 'bg-indigo-500/20 border border-indigo-500/50 shadow-lg shadow-indigo-500/10' 
                    : 'bg-white/5 hover:bg-white/10 border border-transparent'
                  }
                `}
                onClick={() => onSegmentClick?.(seg.timestamp)}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono text-white/40">
                    {formatTime(seg.timestamp)}
                  </span>
                  {isActive && (
                    <span className="text-xs bg-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded-full">
                      Now Playing
                    </span>
                  )}
                </div>
                <p className={`text-white/80 leading-relaxed ${isActive ? 'text-base' : 'text-sm'}`}>
                  {seg.content}
                </p>
              </motion.div>
            );
          })}
        </AnimatePresence>
        
        {narrationSegments.length === 0 && (
          <div className="text-white/40 text-center py-8">
            <p>No transcript available</p>
          </div>
        )}
      </div>
    </div>
  );
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default TranscriptPanel;
