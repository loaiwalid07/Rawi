import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'

function App() {
  const navigate = useNavigate()
  const [capturedImage, setCapturedImage] = useState(null)
  const [extractedText, setExtractedText] = useState('')
  const [selectedVoiceId, setSelectedVoiceId] = useState(0)
  const [voices, setVoices] = useState([])
  const [loading, setLoading] = useState(false)
  const [ocrCompleted, setOcrCompleted] = useState(false)
  const [language, setLanguage] = useState('en')
  const [processingStep, setProcessingStep] = useState('')
  const videoRef = useRef(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    fetchVoices()
  }, [])

  const translations = {
    en: {
      title: "Rawi",
      subtitle: "First Arabic Storyteller using AI",
      hero: "Capture or upload an image to extract and listen to text",
      captureImage: "Capture Image",
      startCamera: "Start Camera",
      capture: "Capture",
      uploadImage: "Upload Image",
      or: "Or",
      result: "Result",
      extractedText: "Extracted Text:",
      voiceType: "Voice Type:",
      generateVoice: "Generate Voice",
      processingOcr: "Extracting text from image...",
      processingTts: "Converting text to speech...",
      errorCamera: "Could not access camera. Please try uploading an image instead.",
      errorBackend: "Error processing image. Make sure the backend is running.",
      loadingVoices: "Loading voices...",
      noVoices: "No voices available"
    },
    ar: {
      title: "راوي",
      subtitle: "أول قاص عربي بالذكاء الاصطناعي",
      hero: "التقط أو ارفع صورة لاستخراج النص والاستماع إليه",
      captureImage: "التقاط صورة",
      startCamera: "تشغيل الكاميرا",
      capture: "التقاط",
      uploadImage: "رفع صورة",
      or: "أو",
      result: "النتيجة",
      extractedText: "النص المستخرج:",
      voiceType: "نوع الصوت:",
      generateVoice: "توليد الصوت",
      processingOcr: "جاري استخراج النص من الصورة...",
      processingTts: "جاري تحويل النص إلى صوت...",
      errorCamera: "تعذر الوصول إلى الكاميرا. يرجى المحاولة برفع صورة.",
      errorBackend: "خطأ في معالجة الصورة. تأكد من أن الخادم يعمل.",
      loadingVoices: "جاري تحميل الأصوات...",
      noVoices: "لا توجد أصوات متاحة"
    }
  }

  const t = translations[language]

  const fetchVoices = async () => {
    try {
      const response = await fetch('http://localhost:8000/voices')
      const data = await response.json()
      if (data.success && data.voices.length > 0) {
        setVoices(data.voices)
      }
    } catch (error) {
      console.error('Error fetching voices:', error)
    }
  }

  useEffect(() => {
    if (capturedImage) {
      performOCR()
    }
  }, [capturedImage])

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      videoRef.current.srcObject = stream
      videoRef.current.play()
    } catch (err) {
      console.error('Error accessing camera:', err)
      alert(t.errorCamera)
    }
  }

  const captureImage = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    setCapturedImage(canvas.toDataURL('image/jpeg'))
    const stream = video.srcObject
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
    }
  }

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => setCapturedImage(event.target.result)
      reader.readAsDataURL(file)
    }
  }

  const performOCR = async () => {
    if (!capturedImage) return

    setLoading(true)
    setProcessingStep(t.processingOcr)

    try {
      const ocrResponse = await fetch('http://localhost:8000/ocr', {
        method: 'POST',
        body: createFormDataFromImage(capturedImage)
      })

      const ocrData = await ocrResponse.json()

      if (ocrData.success) {
        setExtractedText(ocrData.text.trim())
        setOcrCompleted(true)
      }
    } catch (error) {
      console.error('Error processing image:', error)
      alert(t.errorBackend)
    }

    setLoading(false)
    setProcessingStep('')
  }

  const generateTTS = async () => {
    if (!extractedText) return

    setLoading(true)
    setProcessingStep(t.processingTts)

    try {
      const formData = new FormData()
      formData.append('text', extractedText)
      formData.append('voice_id', selectedVoiceId)

      const ttsResponse = await fetch('http://localhost:8000/tts', {
        method: 'POST',
        body: formData
      })

      const ttsData = await ttsResponse.json()

      if (ttsData.success) {
        navigate('/audio-player', {
          state: {
            audioUrl: ttsData.audio_url,
            text: extractedText,
            language: language
          }
        })
      }
    } catch (error) {
      console.error('Error generating TTS:', error)
      alert(t.errorBackend)
    }

    setLoading(false)
    setProcessingStep('')
  }

  const createFormDataFromImage = (imageDataUrl) => {
    const base64Data = imageDataUrl.split(',')[1]
    const byteCharacters = atob(base64Data)
    const byteNumbers = new Array(byteCharacters.length)
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    const blob = new Blob([byteArray], { type: 'image/jpeg' })
    const formData = new FormData()
    formData.append('file', blob, 'captured.jpg')
    return formData
  }

  const toggleLanguage = () => {
    setLanguage(prev => prev === 'en' ? 'ar' : 'en')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-ai-dark to-ai-card text-white" dir={language === 'ar' ? 'rtl' : 'ltr'}>
      <div className="container mx-auto px-4 py-8">
        <button
          onClick={toggleLanguage}
          className="fixed top-4 right-4 z-50 bg-gradient-to-r from-indigo-600 to-purple-600 hover:opacity-90 text-white font-semibold py-2 px-4 rounded-full transition-all duration-200 shadow-lg"
          type="button"
        >
          {language === 'en' ? 'العربية' : 'English'}
        </button>

        <header className="text-center mb-12 pt-16">
          <div className="mb-4">
            <div className="inline-block bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 p-1 rounded-2xl">
              <div className="bg-ai-dark rounded-xl px-8 py-4">
                <h1 className="text-6xl font-black bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  {t.title}
                </h1>
              </div>
            </div>
          </div>
          <p className="text-2xl font-light text-purple-300 mb-3">{t.subtitle}</p>
          <p className="text-gray-400 text-lg">{t.hero}</p>
        </header>

        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-ai-card/80 backdrop-blur-sm rounded-3xl p-8 shadow-2xl border border-purple-500/20 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
              
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3 text-purple-300">
                <span className="text-3xl">📷</span> {t.captureImage}
              </h2>
              
              <div className="space-y-5">
                <div className="relative rounded-xl overflow-hidden shadow-xl border-2 border-purple-500/30">
                  <video 
                    ref={videoRef}
                    className="w-full aspect-video bg-black object-cover"
                    autoPlay
                    playsInline
                  />
                  <canvas ref={canvasRef} className="hidden" />
                </div>
                
                <div className="flex gap-3">
                  <button
                    onClick={startCamera}
                    className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-3 px-6 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
                    type="button"
                  >
                    {t.startCamera}
                  </button>
                  <button
                    onClick={captureImage}
                    className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold py-3 px-6 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
                    type="button"
                  >
                    {t.capture}
                  </button>
                </div>

                <div className="text-center text-gray-500 font-medium my-4 flex items-center justify-center gap-4">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-600 to-transparent"></div>
                  <span className="px-4">{t.or}</span>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-600 to-transparent"></div>
                </div>

                <label className="block">
                  <span className={`flex-1 bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 text-white font-bold py-4 px-6 rounded-xl transition-all duration-200 text-center block cursor-pointer border-2 border-purple-500/30 hover:border-purple-500/50 shadow-lg`}>
                    📁 {t.uploadImage}
                  </span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    className="hidden"
                  />
                </label>
              </div>
            </div>

            <div className="bg-ai-card/80 backdrop-blur-sm rounded-3xl p-8 shadow-2xl border border-indigo-500/20 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
              
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3 text-indigo-300">
                <span className="text-3xl">🔮</span> {t.result}
              </h2>

              {loading && (
                <div className="text-center py-8">
                  <div className="flex justify-center mb-4">
                    <div className="relative w-16 h-16">
                      <div className="absolute inset-0 rounded-full border-4 border-purple-500/20"></div>
                      <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-indigo-500 animate-spin"></div>
                    </div>
                  </div>
                  <p className="text-purple-300 font-medium">{processingStep}</p>
                </div>
              )}

              {capturedImage && !loading && (
                <div className="mb-6">
                  <img src={capturedImage} alt="Captured" className="w-full rounded-xl shadow-lg border-2 border-indigo-500/20" />
                </div>
              )}

              {extractedText && !loading && (
                <div className="bg-gradient-to-br from-gray-900/50 to-gray-800/50 rounded-xl p-5 mb-5 max-h-48 overflow-y-auto border border-indigo-500/20">
                  <h3 className="text-sm font-bold text-indigo-400 mb-3 flex items-center gap-2">
                    <span>📝</span> {t.extractedText}
                  </h3>
                  <p className="text-white whitespace-pre-wrap leading-relaxed">{extractedText}</p>
                </div>
              )}

              {ocrCompleted && !loading && (
                <>
                  <div className="bg-gradient-to-br from-purple-900/30 to-indigo-900/30 rounded-xl p-5 mb-5 border border-purple-500/20">
                    <h3 className="text-sm font-bold text-purple-400 mb-3 flex items-center gap-2">
                      <span>🎙️</span> {t.voiceType}
                    </h3>
                    {voices.length > 0 ? (
                      <select
                        value={selectedVoiceId}
                        onChange={(e) => setSelectedVoiceId(parseInt(e.target.value))}
                        className="w-full bg-gray-700/50 border border-purple-500/30 rounded-lg p-3 text-white focus:outline-none focus:border-purple-500 transition-all"
                      >
                        {voices.map((voice) => (
                          <option key={voice.id} value={voice.id}>
                            {voice.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-gray-400 text-sm">{t.loadingVoices}</p>
                    )}
                  </div>

                  <button
                    onClick={generateTTS}
                    className="w-full bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white font-bold py-4 px-6 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg flex items-center justify-center gap-2"
                    type="button"
                  >
                    🎙️ {t.generateVoice}
                  </button>
                </>
              )}
            </div>
          </div>

          <footer className="text-center mt-12 pb-8">
            <div className="inline-block">
              <p className="text-gray-500 text-sm">© 2024 Rawi - First Arabic Storyteller using AI</p>
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}

export default App