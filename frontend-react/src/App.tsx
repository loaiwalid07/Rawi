import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Send, RotateCcw, AlertCircle, MessageCircle } from 'lucide-react';
import axios from 'axios';
import VideoPlayer from './components/VideoPlayer';
import TranscriptPanel from './components/TranscriptPanel';
import ChatPanel from './components/ChatPanel';

const API_BASE = 'http://localhost:8000';

type TaskStatus = 'pending' | 'planning' | 'storyboarding' | 'generating' | 'merging' | 'completed' | 'failed';

interface ProgressUpdate {
  task_id: string;
  status: TaskStatus;
  progress: number;
  message: string;
  result?: {
    video_url: string;
    narration_text: string;
    interleaved_stream: any[];
    story_id: string;
  };
}

interface Segment {
  type: string;
  content: string;
  timestamp: number;
  duration: number;
}

const App: React.FC = () => {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<ProgressUpdate | null>(null);
  const [videoResult, setVideoResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const subscribeToTask = (taskId: string) => {
    const eventSource = new EventSource(`${API_BASE}/stream-progress/${taskId}`);
    
    eventSource.onmessage = (event) => {
      const data: ProgressUpdate = JSON.parse(event.data);
      setStatus(data);
      
      if (data.status === 'completed') {
        setVideoResult({
          ...data.result,
          story_id: taskId
        });
        setIsGenerating(false);
        eventSource.close();
      } else if (data.status === 'failed') {
        setError(data.message);
        setIsGenerating(false);
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      setError("Lost connection to generation server.");
      setIsGenerating(false);
      eventSource.close();
    };
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setIsGenerating(true);
    setVideoResult(null);
    setStatus(null);
    setError(null);

    try {
      const resp = await axios.post(`${API_BASE}/tell-story`, { topic });
      subscribeToTask(resp.data.task_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to initiate story generation.");
      setIsGenerating(false);
    }
  };

  const handleSegmentClick = (time: number) => {
    setCurrentTime(time);
    // Find and update video time if needed
    const video = document.querySelector('video');
    if (video) {
      video.currentTime = time;
    }
  };

  const resetApp = () => {
    setVideoResult(null);
    setTopic('');
    setStatus(null);
    setChatOpen(false);
    setCurrentTime(0);
  };

  // Parse segments from result
  const segments: Segment[] = videoResult?.interleaved_stream || [];

  return (
    <div className="min-h-screen bg-[#050510] text-white flex flex-col">
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-600/20 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600/20 blur-[120px] rounded-full animate-pulse [animation-delay:2s]" />
      </div>

      <div className="relative z-10 flex-1 flex flex-col">
        {/* Header */}
        <header className="p-6 flex justify-between items-center">
          <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-indigo-400">
            RAWI <span className="text-indigo-500">Storyteller</span>
          </h1>
          
          {videoResult && (
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-xl transition-all"
            >
              <MessageCircle size={18} className="text-indigo-400" />
              <span className="text-sm">Ask about this story</span>
            </button>
          )}
        </header>

        {/* Main Content */}
        <main className="flex-1 flex items-center justify-center p-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-6xl"
          >
            {/* Input View */}
            {!isGenerating && !videoResult && (
              <div className="max-w-2xl mx-auto text-center space-y-8">
                <header className="space-y-2">
                  <h2 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-indigo-400">
                    Transform Any Topic Into a Story
                  </h2>
                  <p className="text-indigo-300/60">Enter a topic and watch it become an engaging educational video</p>
                </header>

                <form onSubmit={handleGenerate} className="relative group">
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="What should we learn about today?"
                    className="w-full bg-white/5 border border-white/10 p-6 rounded-2xl text-xl outline-none focus:border-indigo-500/50 backdrop-blur-xl transition-all placeholder:text-white/20 group-hover:bg-white/10 pr-16"
                  />
                  <button 
                    type="submit"
                    disabled={!topic.trim()}
                    className="absolute right-3 top-3 bottom-3 aspect-square rounded-xl bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-500 disabled:opacity-50 transition-colors"
                  >
                    <Send size={24} />
                  </button>
                </form>
              </div>
            )}

            {/* Generating View */}
            {isGenerating && status && (
              <div className="flex flex-col items-center space-y-12">
                <div className="relative w-48 h-48 flex items-center justify-center">
                  <motion.div 
                    animate={{ rotate: 360 }}
                    transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                    className="absolute inset-0 border-t-2 border-indigo-500/50 rounded-full"
                  />
                  <motion.div 
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 4, repeat: Infinity }}
                    className="w-32 h-32 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full blur-[20px] opacity-40"
                  />
                  <div className="text-4xl font-bold">{status.progress}%</div>
                </div>
                
                <div className="text-center space-y-2">
                  <div className="text-indigo-400 font-mono text-sm tracking-widest uppercase">
                    {status.status.replace('_', ' ')}
                  </div>
                  <h2 className="text-2xl font-light text-white/90 italic">"{status.message}"</h2>
                </div>

                <div className="w-full max-w-md bg-white/5 h-1 rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${status.progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Output View */}
            {videoResult && (
              <motion.div 
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="grid grid-cols-1 lg:grid-cols-2 gap-6"
              >
                {/* Video Section */}
                <div className="space-y-4">
                  <VideoPlayer 
                    videoUrl={`${API_BASE}${videoResult.video_url}`}
                    segments={segments}
                  />
                  
                  <div className="flex justify-between items-center">
                    <button 
                      onClick={resetApp}
                      className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors"
                    >
                      <RotateCcw size={18} /> Create another story
                    </button>
                  </div>
                </div>

                {/* Transcript Section */}
                <div className="h-[500px] lg:h-auto p-6 rounded-3xl bg-white/5 backdrop-blur-3xl border border-white/10">
                  <TranscriptPanel 
                    segments={segments}
                    currentTime={currentTime}
                    onSegmentClick={handleSegmentClick}
                  />
                </div>
              </motion.div>
            )}

            {/* Error View */}
            {error && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-8 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center gap-3"
              >
                <AlertCircle size={20} />
                {error}
              </motion.div>
            )}
          </motion.div>
        </main>

        {/* Chat Panel */}
        {videoResult && (
          <ChatPanel 
            storyId={videoResult.story_id}
            isOpen={chatOpen}
            onToggle={() => setChatOpen(!chatOpen)}
          />
        )}

        {/* Footer */}
        <footer className="p-6 text-center text-white/10 font-mono text-xs tracking-widest uppercase">
          Rawi Multimodal Engine v1.2
        </footer>
      </div>
    </div>
  );
};

export default App;
