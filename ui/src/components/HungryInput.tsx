import { useState, useRef } from 'react';
import {
  Box,
  TextField,
  Container,
  Typography,
  InputAdornment,
  Fab,
  Button
} from '@mui/material';
import { Search, Mic, MicOff, Send } from '@mui/icons-material';

interface HungryInputProps {
  onSubmit: (query: string) => void;
}

export default function HungryInput({ onSubmit }: HungryInputProps) {
  const [query, setQuery] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any | null>(null); // SpeechRecognition | null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query.trim());
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  const startListening = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();

      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setQuery(transcript);
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
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
          justifyContent: 'center',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          py: 4,
          px: 2
        }}
      >
        <Box sx={{ textAlign: 'center', mb: 6 }}>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
            Splash
          </Typography>
        </Box>

        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center' }}>
          <Box sx={{ width: '100%' }}>
            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                placeholder={isListening ? "Listening..." : "I'm hungry for..."}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                variant="outlined"
                autoFocus
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search sx={{ color: '#999' }} />
                    </InputAdornment>
                  ),
                  sx: {
                    backgroundColor: 'white',
                    borderRadius: 3,
                    fontSize: '18px',
                    height: '60px',
                    '& fieldset': {
                      border: 'none'
                    },
                    '&:hover fieldset': {
                      border: 'none'
                    },
                    '&.Mui-focused fieldset': {
                      border: '2px solid #2196f3'
                    }
                  }
                }}
                sx={{
                  '& .MuiInputBase-input': {
                    fontSize: '18px',
                    fontWeight: '400'
                  },
                  '& .MuiInputBase-input::placeholder': {
                    fontSize: '18px',
                    fontWeight: '400',
                    opacity: 0.7
                  }
                }}
              />
            </form>

            <Typography
              variant="body2"
              sx={{
                color: 'rgba(255, 255, 255, 0.8)',
                textAlign: 'center',
                mt: 3,
                px: 2
              }}
            >
              Type what you're craving or use the microphone below
            </Typography>

            {query.trim() && (
              <Box sx={{ textAlign: 'center', mt: 3 }}>
                <Button
                  variant="contained"
                  onClick={() => onSubmit(query)}
                  endIcon={<Send />}
                  sx={{
                    backgroundColor: '#2196f3',
                    borderRadius: 3,
                    px: 4,
                    py: 1.5,
                    textTransform: 'none',
                    fontSize: '16px',
                    fontWeight: 'bold',
                    '&:hover': {
                      backgroundColor: '#1976d2'
                    }
                  }}
                >
                  Continue
                </Button>
              </Box>
            )}
          </Box>
        </Box>

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