import { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Container,
  Divider,
  Paper
} from '@mui/material';
import { Google as GoogleIcon, Apple as AppleIcon } from '@mui/icons-material';

interface SignInProps {
  onSignIn: () => void;
}

export default function SignIn({ onSignIn }: SignInProps) {
  const [email, setEmail] = useState('');

  const handleContinue = () => {
    if (email.trim()) {
      onSignIn();
    }
  };

  const handleSocialLogin = (provider: string) => {
    console.log(`${provider} login clicked`);
    onSignIn();
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
        <Paper
          elevation={3}
          sx={{
            p: 4,
            borderRadius: 3,
            backgroundColor: 'rgba(255, 255, 255, 0.95)'
          }}
        >
          <Typography
            variant="h4"
            component="h1"
            gutterBottom
            sx={{
              fontWeight: 'bold',
              textAlign: 'center',
              color: '#333',
              mb: 1
            }}
          >
            App name
          </Typography>

          <Typography
            variant="body2"
            sx={{
              textAlign: 'center',
              color: '#666',
              mb: 4
            }}
          >
            Create an account
          </Typography>

          <TextField
            fullWidth
            type="email"
            placeholder="email@domain.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            variant="outlined"
            sx={{
              mb: 3,
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
                backgroundColor: '#f8f9fa'
              }
            }}
          />

          <Button
            fullWidth
            variant="contained"
            onClick={handleContinue}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: 'none',
              fontSize: '16px',
              fontWeight: 'bold',
              backgroundColor: '#000',
              mb: 3,
              '&:hover': {
                backgroundColor: '#333'
              }
            }}
          >
            Continue
          </Button>

          <Divider sx={{ my: 2 }}>
            <Typography variant="body2" color="textSecondary">
              OR
            </Typography>
          </Divider>

          <Button
            fullWidth
            variant="outlined"
            startIcon={<GoogleIcon />}
            onClick={() => handleSocialLogin('Google')}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: 'none',
              fontSize: '16px',
              mb: 2,
              borderColor: '#ddd',
              color: '#333',
              '&:hover': {
                borderColor: '#ccc',
                backgroundColor: '#f8f9fa'
              }
            }}
          >
            Continue with Google
          </Button>

          <Button
            fullWidth
            variant="outlined"
            startIcon={<AppleIcon />}
            onClick={() => handleSocialLogin('Apple')}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: 'none',
              fontSize: '16px',
              borderColor: '#ddd',
              color: '#333',
              '&:hover': {
                borderColor: '#ccc',
                backgroundColor: '#f8f9fa'
              }
            }}
          >
            Continue with Apple
          </Button>

          <Typography
            variant="caption"
            sx={{
              display: 'block',
              textAlign: 'center',
              color: '#999',
              mt: 3,
              px: 2
            }}
          >
            By creating an account, you agree to our
            Terms of Service and Privacy Policy
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
}