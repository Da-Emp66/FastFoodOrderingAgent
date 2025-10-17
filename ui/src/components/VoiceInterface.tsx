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
  Collapse
} from '@mui/material';
import { Mic, MicOff, Send, Videocam, VideocamOff } from '@mui/icons-material';
import { sendSessionChat, getScreenshotStreamUrl } from '../services/api';
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

export default function VoiceInterface({ initialQuery = '' }: VoiceInterfaceProps) {
  const [isListening, setIsListening] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const [showScreenshot, setShowScreenshot] = useState(false);
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

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          py: 2,
          px: 2
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
              <Typography variant="caption" sx={{ color: '#666', display: 'block', mb: 1 }}>
                Agent Browser View
              </Typography>
              {sessionId ? (
                <img
                  src={getScreenshotStreamUrl(username, sessionId)}
                  alt="Browser screenshot stream"
                  style={{
                    width: '100%',
                    height: 'auto',
                    borderRadius: '8px',
                    display: 'block'
                  }}
                />
              ) : (
                <Box
                  sx={{
                    width: '100%',
                    minHeight: '200px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '8px',
                    border: '2px dashed #ccc'
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
  );
}

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}