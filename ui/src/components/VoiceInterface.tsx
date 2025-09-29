import { useState, useRef } from 'react';
import {
  Box,
  Fab,
  Typography,
  Paper,
  Container,
  Avatar,
  Chip
} from '@mui/material';
import { Mic, MicOff } from '@mui/icons-material';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

interface VoiceInterfaceProps {
  initialQuery?: string;
}

// Helper function to generate AI responses
const generateAIResponse = (userInput: string): string => {
  const lowerInput = userInput.toLowerCase();

  if (lowerInput.includes('chicken') && lowerInput.includes('chimi')) {
    return "Right now is fine...";
  } else if (lowerInput.includes('right now') || lowerInput.includes('now')) {
    return "AI: Understood. Crafting order for right now at Taco Bell on East Colonial Way 11264. I will alert you when I am at the confirmation screen.";
  } else if (lowerInput.includes('order') || lowerInput.includes('food')) {
    return "What would you like to order today?";
  } else if (lowerInput.includes('hungry')) {
    return "I can help you find something delicious! What are you in the mood for?";
  } else {
    return "I can help you place a food order. What would you like?";
  }
};

export default function VoiceInterface({ initialQuery = '' }: VoiceInterfaceProps) {
  const [isListening, setIsListening] = useState(false);
  const [messages, setMessages] = useState<Message[]>(() => {
    if (initialQuery) {
      return [
        {
          id: '1',
          text: initialQuery,
          isUser: true,
          timestamp: new Date()
        },
        {
          id: '2',
          text: generateAIResponse(initialQuery),
          isUser: false,
          timestamp: new Date()
        }
      ];
    }
    return [];
  });
  const [currentInput, setCurrentInput] = useState('');
  const recognitionRef = useRef<SpeechRecognition | null>(null);

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

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setCurrentInput(transcript);

        // Add user message
        const userMessage: Message = {
          id: Date.now().toString(),
          text: transcript,
          isUser: true,
          timestamp: new Date()
        };

        setMessages(prev => [...prev, userMessage]);

        // Simulate AI response
        setTimeout(() => {
          const aiResponse: Message = {
            id: (Date.now() + 1).toString(),
            text: generateAIResponse(transcript),
            isUser: false,
            timestamp: new Date()
          };
          setMessages(prev => [...prev, aiResponse]);
        }, 1000);
      };

      recognition.onerror = (event) => {
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
            Splash
          </Typography>
        </Box>

        {/* Messages Area */}
        <Box sx={{ flex: 1, px: 2, pb: 2 }}>
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

        {/* Voice Input Button */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            pb: 4
          }}
        >
          <Fab
            size="large"
            onClick={handleMicClick}
            sx={{
              width: 80,
              height: 80,
              backgroundColor: isListening ? '#f44336' : '#2196f3',
              color: 'white',
              '&:hover': {
                backgroundColor: isListening ? '#d32f2f' : '#1976d2'
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