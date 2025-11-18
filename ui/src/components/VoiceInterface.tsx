import { useState, useRef, useEffect } from 'react';
import {
  Box,
  Fab,
  Typography,
  Paper,
  Container,
  Chip,
  CircularProgress,
  TextField,
  IconButton,
  Collapse,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import { Mic, MicOff, Send, Videocam, VideocamOff, Fullscreen, Close, FullscreenExit } from '@mui/icons-material';
import { sendSessionChat, getScreenshotStreamUrl, sendBrowserClick, sendBrowserType } from '../services/api';
import { useGeolocation } from '../hooks/useGeolocation';
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  isComplete?: boolean;
}

interface VoiceInterfaceProps {
  initialQuery?: string;
}

interface ClickIndicator {
  id: number;
  x: number;
  y: number;
}

export default function VoiceInterface({ initialQuery = '' }: VoiceInterfaceProps) {
  const [isListening, setIsListening] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const [showScreenshot, setShowScreenshot] = useState(false);
  const [expandedView, setExpandedView] = useState(false);
  const [clickIndicators, setClickIndicators] = useState<ClickIndicator[]>([]);
  const [username] = useState(() => localStorage.getItem('username') || 'user');
  const recognitionRef = useRef<any | null>(null); // SpeechRecognition | null
  const { speak, speaking } = useSpeechSynthesis();
  const wsRef = useRef<WebSocket | null>(null);
  const currentBotIdRef = useRef<string | null>(null);
  const botBufferRef = useRef<string>("");   // accumulates raw chunks
  const isStreamingRef = useRef<boolean>(false);
  const endTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [log, setLog] = useState<string[]>([]);
  const [wsReady, setWsReady] = useState(false);
  const messageQueue = useRef<string[]>([]);

  // Text input modal state
  const [showTextModal, setShowTextModal] = useState(false);
  const [modalTextInput, setModalTextInput] = useState('');
  const [clickCoords, setClickCoords] = useState<{ x: number; y: number } | null>(null);

  // Detect if mobile based on screen width (simple check)
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    console.log("[TTS] speaking =", speaking);
  }, [speaking]);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Ordering mode (GUI = AI agent, API = scripted ordering)
  const [orderingMode, setOrderingMode] = useState<'GUI' | 'API-Wendys' | 'API-McDonalds'>('GUI');

  // Get user's geolocation
  const { location: geolocation, error: geoError, loading: geoLoading } = useGeolocation();

const handleSendMessage = (text: string) => {
  console.log("[SEND] User → Bot:", text);

  // Add user bubble
  const userMessage: Message = {
    id: "user-" + Date.now(),
    text,
    isUser: true,
    timestamp: new Date()
  };
  setMessages(prev => [...prev, userMessage]);

  // IMPORTANT: reset bot state for next response
  currentBotIdRef.current = null;
  botBufferRef.current = "";
  isStreamingRef.current = false;

  // Show thinking bubble
  setIsLoadingResponse(true);

  // send to WS
  sendWsMessage(text);
};

const forceEndMessage = () => {
  const botId = currentBotIdRef.current;
  if (!botId) return;

  console.warn("⚠️ FORCE END TRIGGERED (timeout)");

  setIsLoadingResponse(false);

  // Mark bubble complete
  setMessages(prev =>
    prev.map(m =>
      m.id === botId ? { ...m, isComplete: true } : m
    )
  );

  const finalText = botBufferRef.current.trim();
  console.log("[TTS FINAL FORCED]:", finalText);

  if (finalText.length > 0) {
    if (recognitionRef.current) recognitionRef.current.stop();
    speak(finalText);
  }

  // Reset all state
  botBufferRef.current = "";
  currentBotIdRef.current = null;
  isStreamingRef.current = false;

  // Clear timeout
  if (endTimeoutRef.current) {
    clearTimeout(endTimeoutRef.current);
    endTimeoutRef.current = null;
  }
};


  // Handle initial query - wait for geolocation to load first
  const hasProcessedInitialQuery = useRef(false);
  useEffect(() => {
    // Only send the initial query once geolocation has finished loading (or failed)
    if (initialQuery && !hasProcessedInitialQuery.current && !geoLoading) {
      hasProcessedInitialQuery.current = true;
      handleSendMessage(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geoLoading]); // Re-run when geoLoading changes

  const startListening = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();

      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setCurrentInput('Listening...');
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;

        console.log("[STT] Transcript detected:", transcript);
        console.log("[STT] isListening:", isListening);
        console.log("[STT] recognitionRef.current exists:", !!recognitionRef.current);
        
        // Detect TTS → STT feedback
        if (transcript && messages.length > 0) {
          const botMsg = messages[messages.length - 1];
          if (!botMsg.isUser && transcript.toLowerCase().includes(botMsg.text.toLowerCase().slice(0, 20))) {
            console.warn("[FEEDBACK WARNING] STT is hearing TTS audio! Loop detected.");
          }
        }

        setCurrentInput(transcript);
        handleSendMessage(transcript);
      };


      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        setCurrentInput('');
      };

      recognition.onend = () => {
        setIsListening(false);
        setCurrentInput('');
      };

      recognition.start();
      recognitionRef.current = recognition;
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setIsListening(false);
    setCurrentInput('');
  };


  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleTextSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (textInput.trim()) {
      handleSendMessage(textInput.trim());
      setTextInput('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTextSubmit();
    }
  };

  const handleScreenshotClick = async (e: React.MouseEvent<HTMLElement>) => {
    // Find the actual image element (if it exists)
    const imgElement = e.currentTarget.querySelector('img');
    const rect = imgElement
      ? imgElement.getBoundingClientRect()
      : e.currentTarget.getBoundingClientRect();

    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // Get pixel coordinates relative to image for visual feedback
    const pixelX = e.clientX - rect.left;
    const pixelY = e.clientY - rect.top;

    // Always log coordinates with session status
    if (sessionId) {
      console.log(`Click at (${x.toFixed(3)}, ${y.toFixed(3)}) | Session: ${sessionId}`);
    } else {
      console.log(`Click at (${x.toFixed(3)}, ${y.toFixed(3)}) | browserview-false | No session - API call skipped`);
    }

    // Add visual feedback
    const clickId = Date.now();
    const newIndicator: ClickIndicator = { id: clickId, x: pixelX, y: pixelY };
    setClickIndicators(prev => [...prev, newIndicator]);

    // Remove indicator after animation
    setTimeout(() => {
      setClickIndicators(prev => prev.filter(indicator => indicator.id !== clickId));
    }, 1000);

    // Only proceed if session exists
    if (sessionId) {
      // Store coordinates and show modal to ask user what to do
      setClickCoords({ x, y });
      setShowTextModal(true);
    }
  };

  const handleJustClick = async () => {
    if (!sessionId || !clickCoords) return;

    try {
      await sendBrowserClick(username, sessionId, clickCoords.x, clickCoords.y);
      console.log(`Click sent successfully`);
    } catch (error) {
      console.error('Error sending click:', error);
    }

    // Close modal and reset
    setShowTextModal(false);
    setModalTextInput('');
    setClickCoords(null);
  };

  const handleTypeText = async () => {
    if (!sessionId || !clickCoords || !modalTextInput.trim()) return;

    try {
      // First click to focus the element
      await sendBrowserClick(username, sessionId, clickCoords.x, clickCoords.y);
      console.log(`Click sent to focus element`);

      // Wait a brief moment for the element to focus
      await new Promise(resolve => setTimeout(resolve, 200));

      // Then type the text
      await sendBrowserType(username, sessionId, modalTextInput);
      console.log(`Text sent successfully: "${modalTextInput}"`);
    } catch (error) {
      console.error('Error sending text:', error);
    }

    // Close modal and reset
    setShowTextModal(false);
    setModalTextInput('');
    setClickCoords(null);
  };

  const handleCancelModal = () => {
    setShowTextModal(false);
    setModalTextInput('');
    setClickCoords(null);
  };

const hasWsInitialized = useRef(false);

useEffect(() => {
    if (hasWsInitialized.current) return;
  hasWsInitialized.current = true;

  console.log("### WebSocket initialized once ###");

  const ws = new WebSocket("ws://localhost:5000/ws");
  wsRef.current = ws;

  ws.onopen = () => {
    console.log("WS connected");
    setWsReady(true);

    // flush queued messages
    messageQueue.current.forEach(m => ws.send(m));
    messageQueue.current = [];
  };


  ws.onerror = (err) => {
    console.log("WS error", err);
    setLog(prev => [...prev, "WS error"]);
  };

  ws.onclose = () => {
    console.log("WS closed");
    setLog(prev => [...prev, "WS closed"]);
  };
  ws.onmessage = (event) => {
    const raw = event.data;
    const chunk = raw.trim();
    console.log("[WS] Chunk:", chunk);

    // =========================================
    // END OF BOT MESSAGE
    // =========================================
    if (chunk === "[[END]]") {
      // stop timeout
      if (endTimeoutRef.current) {
        clearTimeout(endTimeoutRef.current);
        endTimeoutRef.current = null;
      }

      setIsLoadingResponse(false);

      const botId = currentBotIdRef.current;
      if (!botId) return;

      // Mark bubble complete
      setMessages(prev =>
        prev.map(m =>
          m.id === botId ? { ...m, isComplete: true } : m
        )
      );

      const finalText = botBufferRef.current.trim();
      console.log("[TTS FINAL]:", finalText);

      if (finalText.length > 0) {
        if (recognitionRef.current) recognitionRef.current.stop();
        speak(finalText);
      }

      // Reset
      botBufferRef.current = "";
      currentBotIdRef.current = null;
      isStreamingRef.current = false;
      return;
    }


    // =========================================
    // FIRST TOKEN ARRIVES → CREATE BUBBLE
    if (!currentBotIdRef.current) {
      const botId = "bot-" + Date.now();
      currentBotIdRef.current = botId;
      isStreamingRef.current = true;

      setIsLoadingResponse(false);

      // Create new bubble
      setMessages(prev => [
        ...prev,
        {
          id: botId,
          text: "",
          isUser: false,
          isComplete: false,
          timestamp: new Date()
        }
      ]);

      // START TIMEOUT: 5 seconds
      if (endTimeoutRef.current) clearTimeout(endTimeoutRef.current);
      endTimeoutRef.current = setTimeout(() => {
        forceEndMessage();
      }, 5000); // 5 seconds
    }


    // =========================================
    // STREAMING APPEND
    // (happens for every chunk)
    // =========================================
    const botId = currentBotIdRef.current;
    if (!botId) return;

    // Accumulate text
    botBufferRef.current += " " + chunk;

    // Update bubble
    setMessages(prev =>
      prev.map(m =>
        m.id === botId
          ? { ...m, text: (m.text + " " + chunk).trim() }
          : m
      )
    );
  };

}, []); 

const sendWsMessage = (text: string) => {
  if (wsReady && wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(text);
  } else {
    console.log("[WS] Queueing until ready:", text);
    messageQueue.current.push(text);
  }
};

  return (
    <>
      {/* Animated Background Orbs - Full Screen */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: -1,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          overflow: 'hidden'
        }}
      >
        {/* Orb 1 */}
        <Box
          sx={{
            position: 'absolute',
            width: '500px',
            height: '500px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255, 182, 193, 0.4), transparent 70%)',
            filter: 'blur(60px)',
            animation: 'float1 20s infinite ease-in-out',
            top: '-10%',
            left: '-10%',
            '@keyframes float1': {
              '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
              '33%': { transform: 'translate(30vw, 20vh) scale(1.1)' },
              '66%': { transform: 'translate(-20vw, 40vh) scale(0.9)' }
            }
          }}
        />
        {/* Orb 2 */}
        <Box
          sx={{
            position: 'absolute',
            width: '400px',
            height: '400px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(135, 206, 250, 0.4), transparent 70%)',
            filter: 'blur(60px)',
            animation: 'float2 25s infinite ease-in-out',
            top: '20%',
            right: '-10%',
            '@keyframes float2': {
              '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
              '33%': { transform: 'translate(-40vw, 30vh) scale(1.2)' },
              '66%': { transform: 'translate(10vw, -20vh) scale(0.8)' }
            }
          }}
        />
        {/* Orb 3 */}
        <Box
          sx={{
            position: 'absolute',
            width: '600px',
            height: '600px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255, 215, 0, 0.3), transparent 70%)',
            filter: 'blur(80px)',
            animation: 'float3 30s infinite ease-in-out',
            bottom: '-15%',
            left: '50%',
            transform: 'translateX(-50%)',
            '@keyframes float3': {
              '0%, 100%': { transform: 'translate(-50%, 0) scale(1)' },
              '50%': { transform: 'translate(-30%, -40vh) scale(1.3)' }
            }
          }}
        />
        {/* Orb 4 */}
        <Box
          sx={{
            position: 'absolute',
            width: '350px',
            height: '350px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(186, 85, 211, 0.35), transparent 70%)',
            filter: 'blur(50px)',
            animation: 'float4 22s infinite ease-in-out',
            bottom: '10%',
            right: '5%',
            '@keyframes float4': {
              '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
              '50%': { transform: 'translate(-25vw, -30vh) scale(1.1)' }
            }
          }}
        />
      </Box>

      {/* Phone Frame Container */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          padding: isMobile ? '0' : '20px'
        }}
      >
        {/* Conditionally render phone bezel on desktop */}
        <Box
          sx={!isMobile ? {
            width: '100%',
            maxWidth: '550px', // Increased from 430px for better demo visibility
            minHeight: 'calc(100vh - 40px)',
            backgroundColor: '#1a1a1a',
            borderRadius: '50px',
            padding: '12px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
            position: 'relative'
          } : {
            width: '100%',
            height: '100%'
          }}
        >
          {/* Phone Notch - Only on desktop */}
          {!isMobile && (
            <Box
              sx={{
                position: 'absolute',
                top: '12px',
                left: '50%',
                transform: 'translateX(-50%)',
                width: '180px',
                height: '32px',
                backgroundColor: '#1a1a1a',
                borderRadius: '0 0 20px 20px',
                zIndex: 10
              }}
            />
          )}

          {/* Phone Screen / Mobile Screen */}
          <Box
            sx={!isMobile ? {
              width: '100%',
              height: '100%',
              minHeight: 'calc(100vh - 64px)',
              backgroundColor: '#000',
              borderRadius: '40px',
              overflow: 'hidden',
              position: 'relative'
            } : {
              width: '100%',
              height: '100%',
              minHeight: '100vh',
              backgroundColor: '#000',
              overflow: 'hidden',
              position: 'relative'
            }}
          >
            {expandedView ? (
              /* Fullscreen Browser View Inside Phone */
              <Box
                onClick={handleScreenshotClick as any}
                sx={{
                  width: '100%',
                  height: '100%',
                  minHeight: 'calc(100vh - 64px)',
                  backgroundColor: '#000',
                  display: 'flex',
                  flexDirection: 'column',
                  cursor: 'crosshair',
                  position: 'relative'
                }}
              >
                {/* Minimize Button */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: 10,
                    right: 10,
                    zIndex: 10
                  }}
                >
                  <IconButton
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedView(false);
                    }}
                    sx={{
                      backgroundColor: 'rgba(0, 0, 0, 0.6)',
                      color: 'white',
                      '&:hover': {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)'
                      }
                    }}
                  >
                    <FullscreenExit />
                  </IconButton>
                </Box>

                {/* Browser Content */}
                <Box
                  sx={{
                    flex: 1,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    position: 'relative'
                  }}
                >
                  {sessionId ? (
                    <>
                      <img
                        src={getScreenshotStreamUrl(username, sessionId)}
                        alt="Browser screenshot - fullscreen"
                        style={{
                          maxWidth: '100%',
                          maxHeight: '100%',
                          objectFit: 'contain',
                          display: 'block',
                          pointerEvents: 'none'
                        }}
                      />
                      {clickIndicators.map((indicator) => (
                        <Box
                          key={indicator.id}
                          sx={{
                            position: 'absolute',
                            left: indicator.x,
                            top: indicator.y,
                            width: '40px',
                            height: '40px',
                            marginLeft: '-20px',
                            marginTop: '-20px',
                            borderRadius: '50%',
                            border: '3px solid #2196f3',
                            backgroundColor: 'rgba(33, 150, 243, 0.3)',
                            pointerEvents: 'none',
                            animation: 'clickPulse 1s ease-out',
                            '@keyframes clickPulse': {
                              '0%': {
                                transform: 'scale(0.5)',
                                opacity: 1
                              },
                              '100%': {
                                transform: 'scale(2)',
                                opacity: 0
                              }
                            }
                          }}
                        />
                      ))}
                    </>
                  ) : (
                    <Typography sx={{ color: 'white', textAlign: 'center', p: 4 }}>
                      Browser view not available yet.<br />
                      Start ordering to see the live view of the agent
                    </Typography>
                  )}
                </Box>
              </Box>
            ) : (
              /* Normal Chat Interface */
              <Container
                maxWidth="sm"
                sx={{
                  height: '100%',
                  padding: 0,
                  margin: 0,
                  maxWidth: '100% !important'
                }}
              >
                <Box
                  sx={{
                    minHeight: 'calc(100vh - 64px)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    py: 2,
                    px: 2,
                    position: 'relative',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                  }}
                >
        {/* Header */}
        <Box sx={{ width: '100%', position: 'relative', py: 2, px: 2 }}>
          {/* Mode Selector - Top Left */}
          <Box sx={{ position: 'absolute', top: 8, left: 8 }}>
            <FormControl size="small">
              <Select
                value={orderingMode}
                onChange={(e) => setOrderingMode(e.target.value as any)}
                sx={{
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  borderRadius: 1.5,
                  fontSize: '0.75rem',
                  minWidth: '45px',
                  '& .MuiSelect-select': {
                    py: 0.5,
                    px: 1,
                    pr: '28px !important'
                  },
                  '& .MuiOutlinedInput-notchedOutline': {
                    border: 'none'
                  }
                }}
                renderValue={(value) => {
                  // Show only emoji in the closed dropdown
                  if (value === 'GUI') return '🤖';
                  if (value === 'API-Wendys') return '🍔';
                  if (value === 'API-McDonalds') return '🍟';
                  return '🤖';
                }}
              >
                <MenuItem value="GUI">🤖 GUI Mode</MenuItem>
                <MenuItem value="API-Wendys">🍔 Wendy's API</MenuItem>
                <MenuItem value="API-McDonalds">🍟 McDonald's API</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold', textAlign: 'center' }}>
            Fast Food Ordering Agent
          </Typography>
        </Box>

        {/* Browser Screenshot Stream (collapsible) */}
        <Collapse in={showScreenshot}>
          <Box sx={{ width: '100%', mb: 2, px: 2 }}>
            <Paper elevation={3} sx={{ p: 1, borderRadius: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="caption" sx={{ color: '#666' }}>
                  Agent Browser View
                </Typography>
                <Tooltip title={expandedView ? "Collapse view" : "Expand to side-by-side view"}>
                  <IconButton
                    size="small"
                    onClick={() => setExpandedView(!expandedView)}
                    sx={{ color: '#2196f3' }}
                  >
                    <Fullscreen fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              {sessionId ? (
                <Box
                  onClick={handleScreenshotClick as any}
                  sx={{
                    width: '100%',
                    cursor: 'pointer',
                    borderRadius: '8px',
                    overflow: 'hidden'
                  }}
                >
                  <img
                    src={getScreenshotStreamUrl(username, sessionId)}
                    alt="Browser screenshot stream"
                    style={{
                      width: '100%',
                      height: 'auto',
                      display: 'block',
                      pointerEvents: 'none'
                    }}
                  />
                </Box>
              ) : (
                <Box
                  onClick={handleScreenshotClick as any}
                  sx={{
                    width: '100%',
                    minHeight: '200px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '8px',
                    border: '2px dashed #ccc',
                    cursor: 'pointer',
                    '&:hover': {
                      backgroundColor: '#e8e8e8',
                      borderColor: '#999'
                    }
                  }}
                >
                  <Typography variant="body2" sx={{ color: '#999', textAlign: 'center', px: 2 }}>
                    Browser view not available yet.<br />
                    Start ordering to see the live view of the agent
                  </Typography>
                </Box>
              )}
            </Paper>
          </Box>
        </Collapse>

        {/* Messages Area */}
        <Box sx={{ flex: 1, px: 2, pb: 2, width: '100%' }}>
          {messages.map((message) => (
            <Box
              key={message.id}
              sx={{
                mb: 2,
                display: 'flex',
                justifyContent: message.isUser ? 'flex-end' : 'flex-start'
              }}
            >
              <Paper
                elevation={2}
                sx={{
                  p: 2,
                  maxWidth: '80%',
                  borderRadius: 3,
                  backgroundColor: message.isUser ? '#2196f3' : 'white',
                  color: message.isUser ? 'white' : '#333'
                }}
              >
                <Typography variant="body1">
                  {message.text}
                </Typography>
              </Paper>
            </Box>
          ))}

          {isLoadingResponse && (
            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-start' }}>
              <Paper
                elevation={2}
                sx={{
                  p: 2,
                  borderRadius: 3,
                  backgroundColor: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1
                }}
              >
                <CircularProgress size={20} />
                <Typography variant="body2" sx={{ color: '#666' }}>
                  Thinking...
                </Typography>
              </Paper>
            </Box>
          )}

          {currentInput && (
            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
              <Chip
                label={currentInput}
                sx={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  color: 'white'
                }}
              />
            </Box>
          )}
        </Box>

        {/* Text Input */}
        <Box sx={{ width: '100%', px: 2, pb: 2 }}>
          <Paper
            component="form"
            onSubmit={handleTextSubmit}
            elevation={2}
            sx={{
              display: 'flex',
              alignItems: 'center',
              borderRadius: 3,
              p: 1,
              backgroundColor: 'white'
            }}
          >
            <TextField
              fullWidth
              placeholder="Type your order here..."
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyPress={handleKeyPress}
              variant="standard"
              disabled={isLoadingResponse}
              InputProps={{
                disableUnderline: true,
                sx: {
                  fontSize: '16px',
                  px: 2
                }
              }}
            />
            <IconButton
              onClick={() => handleTextSubmit()}
              disabled={!textInput.trim() || isLoadingResponse}
              sx={{
                color: '#2196f3',
                '&:disabled': {
                  color: '#ccc'
                }
              }}
            >
              <Send />
            </IconButton>
          </Paper>
        </Box>

        {/* Voice Input and Screenshot Buttons */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 3,
            pb: 4
          }}
        >
          {/* Screenshot Toggle Button */}
          <Fab
            size="large"
            onClick={() => setShowScreenshot(!showScreenshot)}
            sx={{
              width: 70,
              height: 70,
              backgroundColor: showScreenshot ? '#4caf50' : 'rgba(255, 255, 255, 0.2)',
              color: 'white',
              '&:hover': {
                backgroundColor: showScreenshot ? '#388e3c' : 'rgba(255, 255, 255, 0.3)'
              }
            }}
          >
            {showScreenshot ? <Videocam sx={{ fontSize: 35 }} /> : <VideocamOff sx={{ fontSize: 35 }} />}
          </Fab>

          {/* Microphone Button */}
          <Fab
            size="large"
            onClick={handleMicClick}
            disabled={isLoadingResponse}
            sx={{
              width: 80,
              height: 80,
              backgroundColor: isListening ? '#f44336' : '#2196f3',
              color: 'white',
              '&:hover': {
                backgroundColor: isListening ? '#d32f2f' : '#1976d2'
              },
              '&:disabled': {
                backgroundColor: '#ccc'
              }
            }}
          >
            {isListening ? <MicOff sx={{ fontSize: 40 }} /> : <Mic sx={{ fontSize: 40 }} />}
          </Fab>
        </Box>

        {/* Status indicator */}
        {isListening && (
          <Box sx={{ textAlign: 'center', pb: 2 }}>
            <Typography variant="body2" sx={{ color: 'white' }}>
              Listening...
            </Typography>
          </Box>
        )}
                </Box>
              </Container>
            )}
          </Box>
        </Box>
      </Box>

      {/* Text Input Modal */}
      <Dialog
        open={showTextModal}
        onClose={handleCancelModal}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>What would you like to do?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2, color: '#666' }}>
            You clicked on the browser screen. Choose an action:
          </Typography>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={3}
            placeholder="Type text to enter (e.g., email, password, search query)..."
            value={modalTextInput}
            onChange={(e) => setModalTextInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && modalTextInput.trim()) {
                e.preventDefault();
                handleTypeText();
              }
            }}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelModal} color="inherit">
            Cancel
          </Button>
          <Button
            onClick={handleJustClick}
            variant="outlined"
            color="primary"
          >
            Just Click
          </Button>
          <Button
            onClick={handleTypeText}
            variant="contained"
            color="primary"
            disabled={!modalTextInput.trim()}
          >
            Click & Type Text
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}