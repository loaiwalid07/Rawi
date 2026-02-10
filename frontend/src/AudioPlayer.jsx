import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import './AudioPlayer.css'

function AudioPlayer() {
  const location = useLocation()
  const navigate = useNavigate()
  const { audioUrl, text, language: lang } = location.state || {}
  const audioRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [waveformData, setWaveformData] = useState([])

  useEffect(() => {
    if (audioUrl && audioRef.current) {
      audioRef.current.src = audioUrl
    }
  }, [audioUrl])

  useEffect(() => {
    const audio = audioRef.current
    if (audio) {
      audio.addEventListener('timeupdate', handleTimeUpdate)
      audio.addEventListener('loadedmetadata', handleLoadedMetadata)
      audio.addEventListener('ended', handleEnded)
    }
    return () => {
      if (audio) {
        audio.removeEventListener('timeupdate', handleTimeUpdate)
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
        audio.removeEventListener('ended', handleEnded)
      }
    }
  }, [])

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime)
    }
  }

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration)
    }
  }

  const handleEnded = () => {
    setIsPlaying(false)
    setCurrentTime(0)
  }

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause()
      } else {
        audioRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleSeek = (e) => {
    const progressBar = e.currentTarget
    const rect = progressBar.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    if (audioRef.current) {
      audioRef.current.currentTime = percent * duration
    }
  }

  const formatTime = (seconds) => {
    if (isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const generateWaveform = () => {
    const bars = []
    const barCount = 80
    const progress = currentTime / duration

    for (let i = 0; i < barCount; i++) {
      const height = Math.random() * 80 + 20
      const isPast = i / barCount < progress
      bars.push(
        <div
          key={i}
          className="wave-bar"
          style={{
            height: `${height}px`,
            backgroundColor: isPast ? '#8b5cf6' : 'rgba(139, 92, 246, 0.3)'
          }}
        />
      )
    }
    return bars
  }

  const translations = {
    en: {
      title: "Audio Player",
      back: "Back",
      noAudio: "No audio to play. Please generate audio first.",
      voiceResult: "Voice Result"
    },
    ar: {
      title: "مشغل الصوت",
      back: "عودة",
      noAudio: "لا يوجد صوت للتشغيل. يرجى توليد الصوت أولاً.",
      voiceResult: "نتيجة الصوت"
    }
  }

  const t = translations[lang] || translations.en

  if (!audioUrl) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ai-dark to-ai-card text-white flex items-center justify-center" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-purple-300 mb-4">{t.noAudio}</h1>
          <button
            onClick={() => navigate('/')}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:opacity-90 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200"
          >
            {t.back}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-ai-dark to-ai-card text-white" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <div className="container mx-auto px-4 py-8">
        <button
          onClick={() => navigate('/')}
          className="mb-8 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200"
        >
          ← {t.back}
        </button>

        <header className="text-center mb-12">
          <div className="mb-4">
            <div className="inline-block bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 p-1 rounded-2xl">
              <div className="bg-ai-dark rounded-xl px-8 py-4">
                <h1 className="text-5xl font-black bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  راوي
                </h1>
              </div>
            </div>
          </div>
          <p className="text-2xl font-light text-purple-300">{t.title}</p>
        </header>

        <div className="max-w-4xl mx-auto">
          <div className="bg-ai-card/80 backdrop-blur-sm rounded-3xl p-8 shadow-2xl border border-purple-500/30 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>

            <div className="mb-8">
              <h2 className="text-xl font-bold text-purple-300 mb-4 flex items-center gap-2">
                <span>🎧</span> {t.voiceResult}
              </h2>
              {text && (
                <p className="text-gray-300 bg-gray-800/50 rounded-lg p-4 max-h-40 overflow-y-auto">
                  {text}
                </p>
              )}
            </div>

            <div className="waveform-container mb-8">
              {generateWaveform()}
            </div>

            <div className="flex items-center gap-4 mb-6">
              <button
                onClick={togglePlay}
                className="w-20 h-20 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-full flex items-center justify-center text-3xl transition-all duration-200 transform hover:scale-105 shadow-lg"
              >
                {isPlaying ? '⏸' : '▶️'}
              </button>

              <div className="flex-1">
                <div className="text-gray-400 mb-2">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </div>
                <div
                  className="progress-bar h-2 bg-gray-700 rounded-full cursor-pointer"
                  onClick={handleSeek}
                >
                  <div
                    className="progress-fill h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-100"
                    style={{ width: `${(currentTime / duration) * 100}%` }}
                  />
                </div>
              </div>
            </div>

            <audio ref={audioRef} hidden />
          </div>
        </div>
      </div>
    </div>
  )
}

export default AudioPlayer