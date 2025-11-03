import { useState } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
  Container,
  Divider,
  Paper,
} from "@mui/material";
import { Google as GoogleIcon, Apple as AppleIcon } from "@mui/icons-material";

interface SignInProps {
  onSignIn: () => void;
}

export default function SignIn({ onSignIn }: SignInProps) {
  const [email, setEmail] = useState("");

  const handleContinue = () => {
    if (email.trim()) {
      // Store username/email in localStorage for API calls
      localStorage.setItem('username', email.trim());
      onSignIn();
    }
  };

  const handleSocialLogin = (provider: string) => {
    console.log(`${provider} login clicked`);
    // For social login, use a default username or implement proper OAuth
    localStorage.setItem('username', `${provider.toLowerCase()}_user`);
    onSignIn();
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
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "center",
                  py: 4,
                  px: 2,
                  position: 'relative',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                }}
              >
        <Paper
          elevation={3}
          sx={{
            p: 4,
            borderRadius: 3,
            backgroundColor: "rgba(255, 255, 255, 0.95)",
          }}
        >
          <Typography
            variant="h4"
            component="h1"
            gutterBottom
            sx={{
              fontWeight: "bold",
              textAlign: "center",
              color: "#333",
              mb: 1,
            }}
          >
            Fast Food Ordering Agent
          </Typography>

          <Typography
            variant="body2"
            sx={{
              textAlign: "center",
              color: "#666",
              mb: 4,
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
              "& .MuiOutlinedInput-root": {
                borderRadius: 2,
                backgroundColor: "#f8f9fa",
              },
            }}
          />

          <Button
            fullWidth
            variant="contained"
            onClick={handleContinue}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: "none",
              fontSize: "16px",
              fontWeight: "bold",
              backgroundColor: "#000",
              mb: 3,
              "&:hover": {
                backgroundColor: "#333",
              },
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
            onClick={() => handleSocialLogin("Google")}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: "none",
              fontSize: "16px",
              mb: 2,
              borderColor: "#ddd",
              color: "#333",
              "&:hover": {
                borderColor: "#ccc",
                backgroundColor: "#f8f9fa",
              },
            }}
          >
            Continue with Google
          </Button>

          <Button
            fullWidth
            variant="outlined"
            startIcon={<AppleIcon />}
            onClick={() => handleSocialLogin("Apple")}
            sx={{
              py: 1.5,
              borderRadius: 2,
              textTransform: "none",
              fontSize: "16px",
              borderColor: "#ddd",
              color: "#333",
              "&:hover": {
                borderColor: "#ccc",
                backgroundColor: "#f8f9fa",
              },
            }}
          >
            Continue with Apple
          </Button>

          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              color: "#999",
              mt: 3,
              px: 2,
            }}
          >
            By creating an account, you agree to our Terms of Service and
            Privacy Policy
          </Typography>
        </Paper>
              </Box>
            </Container>
          </Box>
        </Box>
      </Box>
    </>
  );
}
