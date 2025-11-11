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
  Tooltip
} from '@mui/material';
import { Mic, MicOff, Send, Videocam, VideocamOff, Fullscreen, Close, FullscreenExit } from '@mui/icons-material';
import { sendSessionChat, getScreenshotStreamUrl, sendBrowserClick } from '../services/api';
import { useGeolocation } from '../hooks/useGeolocation';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
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

  // Get user's geolocation
  const { location: geolocation, error: geoError, loading: geoLoading } = useGeolocation();

  // Function to send message to backend
  const handleSendMessage = async (text: string) => {
    // Add user message to UI
    const userMessage: Message = {
      id: Date.now().toString(),
      text,
      isUser: true,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    // Send to backend
    setIsLoadingResponse(true);
    try {
      const response = await sendSessionChat(
        username,
        text,
        sessionId,
        geolocation
      );

      // Update session ID if returned
      if (response.session_id) {
        setSessionId(response.session_id);
      }

      // Add AI response to UI
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        isUser: false,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Sorry, there was an error processing your request. Please try again.',
        isUser: false,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      //Speak the error aloud using TTS
      try {
        const utterance = new SpeechSynthesisUtterance(errorMessage.text);
        utterance.rate = 1;
        utterance.pitch = 1;
        window.speechSynthesis.cancel(); // stop any ongoing speech
        window.speechSynthesis.speak(utterance);
      } catch (ttsError) {
        console.error('TTS failed to speak error:', ttsError);
      }
    } finally {
      setIsLoadingResponse(false);
    }
  };

  // Handle initial query - only run once when component mounts
  const hasProcessedInitialQuery = useRef(false);
  useEffect(() => {
    if (initialQuery && !hasProcessedInitialQuery.current) {
      hasProcessedInitialQuery.current = true;
      handleSendMessage(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Speak the latest AI response
  useEffect(() => {
    if (messages.length === 0) return;
    const last = messages[messages.length - 1];

    // Only speak non-user messages (AI responses)
    if (!last.isUser && last.text) {
      const utter = new SpeechSynthesisUtterance(last.text);
      utter.rate = 1;
      utter.pitch = 1;
      window.speechSynthesis.cancel(); // Stop any ongoing speech
      window.speechSynthesis.speak(utter);
    }
  }, [messages]);
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
        setCurrentInput(transcript);

        // Send message to backend
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
      console.log(`Click at (${x.toFixed(3)}, ${y.toFixed(3)}) | Session: ${sessionId} | Sending to backend...`);
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

    // Only send API call if session exists
    if (sessionId) {
      try {
        await sendBrowserClick(username, sessionId, x, y);
        console.log(`Click sent successfully`);
      } catch (error) {
        console.error('Error sending click:', error);
      }
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
          padding: '20px'
        }}
      >
        {/* Phone Bezel */}
        <Box
          sx={{
            width: '100%',
            maxWidth: '430px',
            minHeight: 'calc(100vh - 40px)',
            backgroundColor: '#1a1a1a',
            borderRadius: '50px',
            padding: '12px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
            position: 'relative'
          }}
        >
          {/* Phone Notch */}
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '140px',
              height: '28px',
              backgroundColor: '#1a1a1a',
              borderRadius: '0 0 20px 20px',
              zIndex: 10
            }}
          />

          {/* Phone Screen */}
          <Box
            sx={{
              width: '100%',
              height: '100%',
              minHeight: 'calc(100vh - 64px)',
              backgroundColor: '#000',
              borderRadius: '40px',
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
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
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
    </>
  );
}

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}