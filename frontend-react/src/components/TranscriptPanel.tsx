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

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ segments, currentTime, onSegmentClick }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Find active segment based on current time
  const activeIndex = segments.findIndex(
    (seg) => currentTime >= seg.timestamp && currentTime < seg.timestamp + seg.duration
  );

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
      {/* Header */}
      <div className="flex items-center gap-2 mb-4 pb-2 border-b border-slate-700/50">
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
        <h3 className="text-sm font-medium text-slate-300">Transcript</h3>
      </div>
      
      {/* Content */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-2 pr-2 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-transparent scrollbar-rounded"
      >
        {segments.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-sm">
            No transcript available
          </div>
        ) : (
          <AnimatePresence>
            {segments.map((seg, i) => {
              const isActive = i === activeIndex;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  onClick={() => onSegmentClick?.(seg.timestamp)}
                  className={`
                    p-3 rounded-lg cursor-pointer transition-all duration-200
                    ${isActive 
                      ? 'bg-blue-500/10 border border-blue-500/50' 
                      : 'hover:bg-slate-800/50 border border-transparent'
                    }
                  `}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-xs text-slate-500 font-mono mt-1">
                      {Math.floor(seg.timestamp / 60)}:{Math.floor(seg.timestamp % 60).toString().padStart(2, '0')}
                    </span>
                    <p className="text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
                      {seg.content}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
};

export default TranscriptPanel;
