import { useState, useEffect } from 'react';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import SignIn from './components/SignIn';
import HungryInput from './components/HungryInput';
import VoiceInterface from './components/VoiceInterface';
// import TTS from './components/TTS';

type AppState = "signin" | "hungry" | "voice";

const theme = createTheme({
  palette: {
    primary: {
      main: "#2196f3",
    },
    secondary: {
      main: "#f50057",
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function App() {
  const [currentState, setCurrentState] = useState<AppState>("signin");
  const [hungryQuery, setHungryQuery] = useState("");

  const handleSignIn = () => {
    setCurrentState("hungry");
  };

  const handleHungrySubmit = (query: string) => {
    setHungryQuery(query);
    setCurrentState("voice");
  };

  const renderCurrentScreen = () => {
    switch (currentState) {
      case "signin":
        return <SignIn onSignIn={handleSignIn} />;
      case "hungry":
        return <HungryInput onSubmit={handleHungrySubmit} />;
      case "voice":
        return <VoiceInterface initialQuery={hungryQuery} />;
      default:
        return <SignIn onSignIn={handleSignIn} />;
    }
  };

  // ✅ New effect: when entering 'voice' state, automatically trigger TTS
  useEffect(() => {
    if (currentState === 'voice' && hungryQuery) {
      const utterance = new SpeechSynthesisUtterance(
        `Okay, I heard you say ${hungryQuery}. Let's start working on your order.`
      );
      window.speechSynthesis.speak(utterance);
    }
  }, [currentState, hungryQuery]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {renderCurrentScreen()}

      {/* ✅ Optional: render manual TTS controls below the main UI */}
      {/* {currentState === 'voice' && (
        <div style={{ marginTop: '2rem' }}>
          <TTS />
        </div>
      )} */}
    </ThemeProvider>
  );
}

export default App;
