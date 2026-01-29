/**
 * Register Page
 * Two-step registration: verify email first, then set password
 */

import { useState, FormEvent, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/store/useAuthStore';
import { Button } from '@/components/ui/Button';
import { useToastStore } from '@/store/useToastStore';
import { sendVerificationCode, verifyCode } from '@/api/auth';
import logoIcon from '@/assets/icon.svg';

export const Register = () => {
  const navigate = useNavigate();
  const { register, isLoading, error, clearError } = useAuthStore();
  const { addToast } = useToastStore();
  
  // Step 1: Email verification
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [sendingCode, setSendingCode] = useState(false);
  const [verifyingCode, setVerifyingCode] = useState(false);
  const [codeVerified, setCodeVerified] = useState(false);
  
  // Step 2: User info and password
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  });
  
  const [localError, setLocalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Countdown timer for verification code
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Step 1: Send verification code
  const handleSendVerificationCode = async () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      setLocalError('Please enter a valid email address');
      return;
    }

    setSendingCode(true);
    setLocalError(null);
    setSuccessMessage(null);
    clearError();
    
    // Reset verification code when resending
    if (codeSent) {
      setVerificationCode('');
    }
    
    // Set codeSent to true immediately to show verification code input and animation
    setCodeSent(true);

    try {
      const response = await sendVerificationCode(email);
      
      if (response.status === 'success') {
        setCountdown(60);
        setSuccessMessage('Verification code sent successfully');
        setLocalError(null);
        
        // In dev mode, show code prominently if returned
        if (response.data?.verification_code) {
          const devCode = response.data.verification_code;
          addToast(`[DEV MODE] Verification code: ${devCode}`, 'info');
          // Auto-fill verification code in dev mode
          setVerificationCode(devCode);
          // Show a more prominent message
          setTimeout(() => {
            alert(`[DEV MODE]\n\nEmail sending failed, but here's your verification code:\n\n${devCode}\n\nThis code has been auto-filled.`);
          }, 500);
        }
      } else {
        setSuccessMessage(null);
        setLocalError(response.message || 'Failed to send verification code');
        addToast(response.message || 'Failed to send verification code', 'error');
        
        // Check if response contains verification code (dev mode)
        if (response.data?.verification_code) {
          const devCode = response.data.verification_code;
          setVerificationCode(devCode);
          // codeSent already set to true above
          setTimeout(() => {
            alert(`[DEV MODE]\n\nRate limited or email failed, but here's your verification code:\n\n${devCode}\n\nThis code has been auto-filled.`);
          }, 500);
        }
      }
    } catch (err: any) {
      setSuccessMessage(null);
      // Handle 429 rate limit error
      if (err.response?.status === 429) {
        const errorMessage = err.response?.data?.detail || 'Too many requests. Please wait before trying again.';
        setLocalError(errorMessage);
        addToast(errorMessage, 'error');
        
        // In dev mode, check if rate limit response contains code
        if (err.response?.data?.verification_code) {
          const devCode = err.response.data.verification_code;
          setVerificationCode(devCode);
          // codeSent already set to true above
          setTimeout(() => {
            alert(`[DEV MODE]\n\nRate limited, but here's your existing verification code:\n\n${devCode}\n\nThis code has been auto-filled.`);
          }, 500);
        }
      } else {
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to send verification code';
        setLocalError(errorMessage);
        addToast(errorMessage, 'error');
        
        // Check if error response contains verification code (dev mode)
        if (err.response?.data?.verification_code) {
          const devCode = err.response.data.verification_code;
          setVerificationCode(devCode);
          // codeSent already set to true above
          setTimeout(() => {
            alert(`[DEV MODE]\n\nEmail sending failed, but here's your verification code:\n\n${devCode}\n\nThis code has been auto-filled.`);
          }, 500);
        }
      }
    } finally {
      setSendingCode(false);
    }
  };

  // Step 1: Verify code
  const handleVerifyCode = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setSuccessMessage(null);
    clearError();

    // Normalize verification code: ensure it's exactly 6 digits, pad with zeros if needed
    const normalizedCode = verificationCode.replace(/\D/g, '').padStart(6, '0').slice(0, 6);
    
    if (!normalizedCode || normalizedCode.length !== 6) {
      setLocalError('Please enter a valid 6-digit verification code');
      return;
    }

    // Update state with normalized code
    setVerificationCode(normalizedCode);

    setVerifyingCode(true);

    try {
      const response = await verifyCode(email, normalizedCode);
      if (response.status === 'success' && response.data?.verified) {
        setCodeVerified(true);
        setStep(2);
        addToast('Email verified successfully', 'success');
      } else {
        setLocalError('Verification failed. Please check the code and try again.');
        addToast('Verification failed', 'error');
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Verification failed. Please check the code and try again.';
      setLocalError(errorMessage);
      addToast(errorMessage, 'error');
    } finally {
      setVerifyingCode(false);
    }
  };

  // Step 2: Register
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (!formData.username || !formData.password) {
      setLocalError('Please fill in all required fields');
      return;
    }

    if (formData.password.length < 6) {
      setLocalError('Password must be at least 6 characters');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setLocalError('Passwords do not match');
      return;
    }

    try {
      await register(
        formData.username,
        email, // Use verified email
        formData.password,
        verificationCode, // Use verified code
        formData.fullName || undefined
      );
      navigate('/');
    } catch (err: any) {
      const errorMessage = err.message || 'Registration failed, please try again';
      setLocalError(errorMessage);
      addToast(errorMessage, 'error');
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 px-4 py-8">
      <div className="max-w-md w-full">
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex flex-col items-center mb-6">
              <img 
                src={logoIcon} 
                alt="BESS Agent Logo" 
                className="h-20 w-auto mb-4" 
              />
              <h1 className="text-3xl font-bold text-white mb-2">Register</h1>
              <p className="text-gray-400 mb-3">
                {step === 1 ? 'Step 1: Verify your email' : 'Step 2: Create your account'}
              </p>
              {/* Progress indicator */}
              <div className="flex items-center justify-center gap-2">
                <div className={`h-2 w-12 rounded-full ${step >= 1 ? 'bg-blue-500' : 'bg-gray-600'}`} />
                <div className={`h-2 w-12 rounded-full ${step >= 2 ? 'bg-blue-500' : 'bg-gray-600'}`} />
              </div>
            </div>
          </div>

          {/* Success Message */}
          {successMessage && (
            <div className="mb-6 p-4 bg-green-900/30 border border-green-700 rounded-lg">
              <p className="text-green-300 text-sm">{successMessage}</p>
            </div>
          )}

          {/* Error Message */}
          {displayError && (
            <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg">
              <p className="text-red-300 text-sm">{displayError}</p>
            </div>
          )}

          {/* Step 1: Email Verification */}
          {step === 1 && (
            <form onSubmit={handleVerifyCode} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                  Email <span className="text-red-400">*</span>
                </label>
                <div className="flex gap-2">
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setCodeSent(false);
                      setCodeVerified(false);
                      setVerificationCode('');
                      setSuccessMessage(null);
                      setLocalError(null);
                    }}
                    className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Enter email address"
                    disabled={isLoading || sendingCode || codeVerified}
                    autoComplete="email"
                    required
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleSendVerificationCode}
                    disabled={isLoading || sendingCode || countdown > 0 || !email || codeVerified}
                    loading={sendingCode}
                    className="whitespace-nowrap"
                  >
                    {countdown > 0 ? `${countdown}s` : 'Send Code'}
                  </Button>
                </div>
                {codeSent && countdown > 0 && (
                  <p className="mt-1 text-xs text-gray-400">
                    Didn't receive the code? Resend in {countdown}s
                  </p>
                )}
                {codeSent && countdown === 0 && (
                  <button
                    type="button"
                    onClick={handleSendVerificationCode}
                    disabled={sendingCode}
                    className="mt-1 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                  >
                    Didn't receive the code? Click to resend
                  </button>
                )}
              </div>

              {codeSent && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.2 }}
                  className="mt-4"
                >
                  <label htmlFor="verificationCode" className="block text-sm font-medium text-gray-300 mb-2">
                    Verification Code <span className="text-red-400">*</span>
                  </label>
                  <input
                    id="verificationCode"
                    type="text"
                    value={verificationCode}
                    onChange={(e) => {
                      // Keep leading zeros - just remove non-digits and limit to 6 digits
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setVerificationCode(value);
                    }}
                    onBlur={(e) => {
                      // Ensure code is exactly 6 digits, pad with zeros if needed
                      const value = e.target.value.replace(/\D/g, '').padStart(6, '0').slice(0, 6);
                      setVerificationCode(value);
                    }}
                    className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl tracking-widest"
                    placeholder="000000"
                    disabled={isLoading || verifyingCode || codeVerified}
                    autoComplete="off"
                    maxLength={6}
                    required
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    Enter the 6-digit code sent to your email
                  </p>
                </motion.div>
              )}

              {codeSent && !codeVerified && (
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  loading={verifyingCode}
                  disabled={verifyingCode || verificationCode.length !== 6}
                >
                  Verify Code
                </Button>
              )}

              {codeVerified && (
                <div className="p-4 bg-green-900/30 border border-green-700 rounded-lg">
                  <p className="text-green-300 text-sm text-center">
                    ✓ Email verified successfully! Proceeding to next step...
                  </p>
                </div>
              )}
            </form>
          )}

          {/* Step 2: User Info and Password */}
          {step === 2 && (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="mb-4 p-3 bg-blue-900/30 border border-blue-700 rounded-lg">
                <p className="text-blue-300 text-sm">
                  ✓ Verified email: <strong>{email}</strong>
                </p>
              </div>

              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
                  Username <span className="text-red-400">*</span>
                </label>
                <input
                  id="username"
                  type="text"
                  value={formData.username}
                  onChange={(e) => {
                    const value = e.target.value;
                    // Auto-fill email if username looks like an email
                    if (!formData.username && value.includes('@') && value.includes('.')) {
                      setFormData(prev => ({ ...prev, username: value }));
                    } else {
                      setFormData(prev => ({ ...prev, username: value }));
                    }
                  }}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Enter username or email"
                  disabled={isLoading}
                  autoComplete="username"
                  required
                />
                <p className="mt-1 text-xs text-gray-400">
                  You can use your email address as username
                </p>
              </div>

              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-gray-300 mb-2">
                  Full Name (Optional)
                </label>
                <input
                  id="fullName"
                  type="text"
                  value={formData.fullName}
                  onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Enter full name"
                  disabled={isLoading}
                  autoComplete="name"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                  Password <span className="text-red-400">*</span>
                </label>
                <input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="At least 6 characters"
                  disabled={isLoading}
                  autoComplete="new-password"
                  required
                  minLength={6}
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-2">
                  Confirm Password <span className="text-red-400">*</span>
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Re-enter password"
                  disabled={isLoading}
                  autoComplete="new-password"
                  required
                />
              </div>

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setStep(1);
                    setCodeVerified(false);
                  }}
                  disabled={isLoading}
                  className="flex-1"
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="flex-1"
                  loading={isLoading}
                  disabled={isLoading}
                >
                  Register
                </Button>
              </div>
            </form>
          )}

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-gray-400 text-sm">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
