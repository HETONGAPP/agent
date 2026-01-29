/**
 * Check Animation Component
 * Animated green circle with checkmark
 */

import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

interface CheckAnimationProps {
  size?: number;
  className?: string;
}

export const CheckAnimation = ({ size = 20, className = '' }: CheckAnimationProps) => {
  return (
    <div className={`inline-flex items-center justify-center ${className}`}>
      <motion.div
        className="relative"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{
          type: "spring",
          stiffness: 260,
          damping: 20,
        }}
      >
        {/* Green circle */}
        <motion.div
          className="rounded-full bg-green-500 flex items-center justify-center shadow-lg shadow-green-500/50"
          style={{ width: size, height: size }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{
            type: "spring",
            stiffness: 200,
            damping: 15,
            delay: 0.1,
          }}
        >
          {/* Checkmark */}
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{
              type: "spring",
              stiffness: 300,
              damping: 20,
              delay: 0.3,
            }}
          >
            <Check 
              size={size * 0.6} 
              className="text-white" 
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </motion.div>
        </motion.div>
        
        {/* Ripple effect */}
        <motion.div
          className="absolute inset-0 rounded-full bg-green-500 -z-10"
          initial={{ scale: 1, opacity: 0.4 }}
          animate={{ scale: 1.8, opacity: 0 }}
          transition={{
            duration: 0.8,
            ease: "easeOut",
            delay: 0.2,
          }}
        />
      </motion.div>
    </div>
  );
};
