import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, RotateCcw, AlertCircle, MessageCircle, FileText, Sparkles } from 'lucide-react';
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

type TabType = 'transcript' | 'chat';

const App: React.FC = () => {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<ProgressUpdate | null>(null);
  const [videoResult, setVideoResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('transcript');
  const [currentTime, setCurrentTime] = useState(0);
  const [panelCollapsed, setPanelCollapsed] = useState(false);

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
    const video = document.querySelector('video');
    if (video) {
      video.currentTime = time;
    }
  };

  const resetApp = () => {
    setVideoResult(null);
    setTopic('');
    setStatus(null);
    setCurrentTime(0);
    setActiveTab('transcript');
  };

  const segments: Segment[] = (videoResult?.interleaved_stream || []).filter((seg: Segment) => seg.type === 'NARRATION');

  const getStatusColor = (s: TaskStatus) => {
    switch (s) {
      case 'completed': return 'bg-emerald-500';
      case 'failed': return 'bg-red-500';
      case 'generating': return 'bg-blue-500';
      case 'storyboarding': return 'bg-violet-500';
      case 'planning': return 'bg-amber-500';
      default: return 'bg-slate-500';
    }
  };

  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex overflow-hidden">
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="text-lg font-semibold text-white shrink-0">
              RAWI <span className="text-blue-400 font-normal">Studio</span>
            </h1>
            {videoResult && (
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded truncate max-w-xs">
                {topic}
              </span>
            )}
          </div>
          
          {videoResult && (
            <button
              onClick={resetApp}
              className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors shrink-0"
            >
              <RotateCcw size={16} />
              <span>New Video</span>
            </button>
          )}
        </header>

        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left: Video Section */}
          <div className="flex-1 flex flex-col p-6 overflow-hidden min-w-0">
            <AnimatePresence mode="wait">
              {/* Input State */}
              {!isGenerating && !videoResult && (
                <motion.div
                  key="input"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="flex-1 flex flex-col items-center justify-center"
                >
                  <div className="text-center mb-8">
                    <h2 className="text-3xl font-bold text-white mb-2">
                      Transform Any Topic Into a Video
                    </h2>
                    <p className="text-slate-400">
                      Enter a topic and watch it become an engaging educational video
                    </p>
                  </div>

                  <form onSubmit={handleGenerate} className="w-full max-w-xl">
                    <div className="relative">
                      <input
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder="What should we learn about today?"
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-5 py-4 text-lg text-white placeholder:text-slate-500 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all pr-14"
                      />
                      <button 
                        type="submit"
                        disabled={!topic.trim()}
                        className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-lg bg-blue-500 text-white flex items-center justify-center hover:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                      >
                        <Send size={20} />
                      </button>
                    </div>
                  </form>
                </motion.div>
              )}

              {/* Generating State */}
              {isGenerating && status && (
                <motion.div
                  key="generating"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center"
                >
                  <div className="w-32 h-32 relative mb-8">
                    <motion.div 
                      animate={{ rotate: 360 }}
                      transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                      className="absolute inset-0 border-2 border-t-blue-500 border-slate-700 rounded-full"
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-3xl font-bold text-white">{status.progress}%</span>
                    </div>
                  </div>
                  
                  <div className="text-center max-w-md">
                    <div className="flex items-center justify-center gap-2 mb-2">
                      <span className={`w-2 h-2 rounded-full ${getStatusColor(status.status)} animate-pulse`} />
                      <span className="text-sm font-medium text-slate-400 uppercase tracking-wider">
                        {status.status.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-lg text-slate-300">{status.message}</p>
                  </div>

                  <div className="w-full max-w-sm mt-8">
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <motion.div 
                        className="h-full bg-blue-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${status.progress}%` }}
                        transition={{ duration: 0.3 }}
                      />
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Video Result State */}
              {videoResult && (
                <motion.div
                  key="video"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex-1 flex flex-col min-h-0"
                >
                  {/* Video Player */}
                  <div className="flex-1 min-h-0 mb-4">
                    <VideoPlayer 
                      videoUrl={`${API_BASE}${videoResult.video_url}`}
                      segments={segments}
                      onTimeUpdate={setCurrentTime}
                    />
                  </div>
                  
                  {/* Video Info Bar */}
                  <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shrink-0">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium text-white mb-1 truncate">{topic}</h3>
                        <p className="text-sm text-slate-400">
                          Educational video generated with AI narration
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 ml-4">
                        <button
                          onClick={() => { setActiveTab('chat'); setPanelCollapsed(false); }}
                          className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-all"
                        >
                          <Sparkles size={18} />
                          <span className="text-sm font-medium">Ask AI</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error State */}
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center gap-3 shrink-0"
              >
                <AlertCircle size={20} className="shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}
          </div>

          {/* Right: Transcript & AI Assistant Panel */}
          {videoResult && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: panelCollapsed ? 48 : 400, opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="border-l border-slate-800 bg-slate-900/30 flex flex-col overflow-hidden shrink-0 relative"
            >
              {/* Collapse Toggle */}
              <button
                onClick={() => setPanelCollapsed(!panelCollapsed)}
                className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-full z-10 w-6 h-12 bg-slate-800 border border-slate-700 rounded-l-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-all"
              >
                <svg 
                  className={`w-4 h-4 transition-transform ${panelCollapsed ? 'rotate-180' : ''}`} 
                  fill="none" 
                  viewBox="0 0 24 24" 
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {!panelCollapsed && (
                <>
                  {/* Tab Header */}
                  <div className="flex border-b border-slate-800 shrink-0">
                    <button
                      onClick={() => setActiveTab('transcript')}
                      className={`flex-1 px-4 py-3 text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                        activeTab === 'transcript' 
                          ? 'text-white border-b-2 border-blue-500 bg-slate-800/50' 
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <FileText size={16} />
                      Transcript
                    </button>
                    <button
                      onClick={() => setActiveTab('chat')}
                      className={`flex-1 px-4 py-3 text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                        activeTab === 'chat' 
                          ? 'text-white border-b-2 border-blue-500 bg-slate-800/50' 
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <MessageCircle size={16} />
                      AI Assistant
                    </button>
                  </div>

                  {/* Tab Content */}
                  <div className="flex-1 overflow-hidden min-h-0">
                    {activeTab === 'transcript' ? (
                      <TranscriptPanel 
                        segments={segments}
                        currentTime={currentTime}
                        onSegmentClick={handleSegmentClick}
                      />
                    ) : (
                      <ChatPanel 
                        storyId={videoResult.story_id}
                        apiBase={API_BASE}
                      />
                    )}
                  </div>
                </>
              )}

              {/* Collapsed State */}
              {panelCollapsed && (
                <div className="flex flex-col items-center py-4 gap-4">
                  <button
                    onClick={() => { setActiveTab('transcript'); setPanelCollapsed(false); }}
                    className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all ${
                      activeTab === 'transcript' 
                        ? 'bg-blue-500/20 text-blue-400' 
                        : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                    }`}
                    title="Transcript"
                  >
                    <FileText size={20} />
                  </button>
                  <button
                    onClick={() => { setActiveTab('chat'); setPanelCollapsed(false); }}
                    className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all ${
                      activeTab === 'chat' 
                        ? 'bg-blue-500/20 text-blue-400' 
                        : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                    }`}
                    title="AI Assistant"
                  >
                    <MessageCircle size={20} />
                  </button>
                </div>
              )}
            </motion.aside>
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
