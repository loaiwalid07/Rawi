import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Send, RotateCcw, CheckCircle2, AlertCircle } from 'lucide-react';
import axios from 'axios';

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
  };
}

const App: React.FC = () => {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<ProgressUpdate | null>(null);
  const [videoResult, setVideoResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const subscribeToTask = (taskId: string) => {
    const eventSource = new EventSource(`${API_BASE}/stream-progress/${taskId}`);
    
    eventSource.onmessage = (event) => {
      const data: ProgressUpdate = JSON.parse(event.data);
      setStatus(data);
      
      if (data.status === 'completed') {
        setVideoResult(data.result);
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

  return (
    <div className="min-h-screen bg-[#050510] text-white flex flex-col items-center justify-center p-6 overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-600/20 blur-[120px] rounded-full animate-pulse" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600/20 blur-[120px] rounded-full animate-pulse [animation-delay:2s]" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-2xl z-10"
      >
        {!isGenerating && !videoResult && (
          <div className="text-center space-y-8">
            <header className="space-y-2">
              <h1 className="text-5xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-indigo-400">
                RAWI <span className="text-indigo-500">Storyteller</span>
              </h1>
              <p className="text-indigo-300/60 font-medium">Transform any topic into a cinematic journey</p>
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

            <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                initial={{ width: 0 }}
                animate={{ width: `${status.progress}%` }}
              />
            </div>
          </div>
        )}

        {videoResult && (
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="space-y-6"
          >
            <div className="aspect-video rounded-3xl overflow-hidden border border-white/10 shadow-2xl relative bg-black">
              <video 
                src={`${API_BASE}${videoResult.video_url}`}
                controls
                autoPlay
                className="w-full h-full"
              />
            </div>
            
            <div className="p-8 rounded-3xl bg-white/5 backdrop-blur-3xl border border-white/10 space-y-4">
               <h3 className="text-indigo-400 font-semibold flex items-center gap-2">
                 <CheckCircle2 size={18} /> Story Finalized
               </h3>
               <p className="text-white/70 leading-relaxed text-lg italic">
                 {videoResult.narration_text}
               </p>
               <button 
                onClick={() => { setVideoResult(null); setTopic(''); }}
                className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors"
               >
                 <RotateCcw size={18} /> Create another story
               </button>
            </div>
          </motion.div>
        )}

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

      {/* Footer Branding */}
      <div className="absolute bottom-8 text-white/10 font-mono text-xs tracking-widest uppercase">
        Rawi Multimodal Engine v1.1
      </div>
    </div>
  );
};

export default App;
