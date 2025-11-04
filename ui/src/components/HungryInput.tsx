import { useState, useRef } from 'react';
import {
  Box,
  TextField,
  Container,
  Typography,
  InputAdornment,
  Fab,
  Button,
  Chip,
  CircularProgress
} from '@mui/material';
import { Search, Mic, MicOff, Send, LocationOn } from '@mui/icons-material';
import { useGeolocation } from '../hooks/useGeolocation';

interface HungryInputProps {
  onSubmit: (query: string) => void;
}

export default function HungryInput({ onSubmit }: HungryInputProps) {
  const [query, setQuery] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any | null>(null); // SpeechRecognition | null

  // Get user's geolocation
  const { location: geolocation, locationName, error: geoError, loading: geoLoading } = useGeolocation();

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
                  justifyContent: 'center',
                  alignItems: 'center',
                  py: 4,
                  px: 2,
                  position: 'relative',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                }}
              >
        {/* Location Chip - Top Right */}
        <Box sx={{ width: '100%', display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          {geoLoading && (
            <Chip
              icon={<CircularProgress size={16} sx={{ color: 'white !important' }} />}
              label="Getting location..."
              size="small"
              sx={{
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                fontSize: '12px'
              }}
            />
          )}
          {geolocation && !geoLoading && locationName && (
            <Chip
              icon={<LocationOn sx={{ color: 'white !important' }} />}
              label={locationName}
              size="small"
              sx={{
                backgroundColor: 'rgba(76, 175, 80, 0.3)',
                color: 'white',
                fontSize: '12px',
                border: '1px solid rgba(255, 255, 255, 0.3)'
              }}
            />
          )}
          {geoError && !geoLoading && (
            <Chip
              icon={<LocationOn sx={{ color: 'white !important' }} />}
              label="No location"
              size="small"
              sx={{
                backgroundColor: 'rgba(244, 67, 54, 0.3)',
                color: 'white',
                fontSize: '12px',
                border: '1px solid rgba(255, 255, 255, 0.3)'
              }}
            />
          )}
        </Box>

        {/* Title with Burger - Centered and Lower */}
        <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', mb: 6, mt: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h5" sx={{ fontSize: '24px' }}>
              🍔
            </Typography>
            <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
              Fast Food Agent
            </Typography>
          </Box>
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