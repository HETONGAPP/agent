/**
 * Loading Spinner Component
 * Uses Web Animations API on mobile/iOS where CSS animation often doesn't run
 */

import { useRef, useEffect, useState } from 'react';
import './LoadingSpinner.css';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const isMobileOrIOS = () =>
  typeof navigator !== 'undefined' &&
  (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
    ('ontouchstart' in window));

export const LoadingSpinner = ({ size = 'md', className = '' }: LoadingSpinnerProps) => {
  const spinRef = useRef<HTMLDivElement>(null);
  const [useJsAnim, setUseJsAnim] = useState(false);
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  useEffect(() => {
    if (!isMobileOrIOS()) return;
    setUseJsAnim(true);
  }, []);

  useEffect(() => {
    if (!useJsAnim || !spinRef.current) return;
    const el = spinRef.current;
    const anim = el.animate(
      [{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }],
      { duration: 1000, iterations: Infinity, easing: 'linear' }
    );
    return () => anim.cancel();
  }, [useJsAnim]);

  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="loading-spinner-wrap">
        <div
          ref={spinRef}
          className={`loading-spinner-inner ${sizeClasses[size]} border-4 border-gray-700 border-t-blue-500 rounded-full ${useJsAnim ? 'loading-spinner-no-css' : ''}`}
        />
      </div>
    </div>
  );
};














