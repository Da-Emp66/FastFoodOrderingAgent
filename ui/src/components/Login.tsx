import React, { useState } from 'react';
import './Login.css';
import { PageState } from '../pages/Home';
import type { PageStateType } from '../pages/Home';

interface LoginProps {
  setPageState: (state: PageStateType) => void;
}

const Login: React.FC<LoginProps> = ({ setPageState }) => {
  const [email, setEmail] = useState('');

  const handleContinue = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle email continue logic here
    console.log('Continue with email:', email);
    // Change to chatbot page after successful login
    setPageState(PageState.CHATBOT);
  };

  const handleGoogleLogin = () => {
    // Handle Google login logic here
    console.log('Continue with Google');
    // Change to chatbot page after successful login
    setPageState(PageState.CHATBOT);
  };

  const handleAppleLogin = () => {
    // Handle Apple login logic here
    console.log('Continue with Apple');
    // Change to chatbot page after successful login
    setPageState(PageState.CHATBOT);
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="text-center">
          <h2 className="app-title">Fast Food Ordering Agent</h2>
        </div>
        
        <div className="text-center">
          <h4 className="login-title">Create an account</h4>
          <p className="login-subtitle">Enter your email to sign up for this app</p>
        </div>

        <form onSubmit={handleContinue}>
          <div className="form-group">
            <input
              type="email"
              placeholder="email@domain.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="email-input"
              required
            />
          </div>

          <button 
            type="submit" 
            className="continue-btn"
            disabled={!email}
          >
            Continue
          </button>
        </form>

        <div className="divider-container">
          <hr className="divider-line" />
          <span className="divider-text">or</span>
          <hr className="divider-line" />
        </div>

        <div className="social-buttons">
          <button 
            className="social-btn google-btn"
            onClick={handleGoogleLogin}
          >
            <span className="google-icon">G</span>
            Continue with Google
          </button>

          <button 
            className="social-btn apple-btn"
            onClick={handleAppleLogin}
          >
            <span className="apple-icon">🍎</span>
            Continue with Apple
          </button>
        </div>

        <div className="text-center">
          <small className="terms-text">
            By clicking continue, you agree to our{' '}
            <a href="#" className="terms-link">Terms of Service</a>
            {' '}and{' '}
            <a href="#" className="terms-link">Privacy Policy</a>
          </small>
        </div>
      </div>
    </div>
  );
};

export default Login;