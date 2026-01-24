/**
 * Diagnostic Output Component
 * Professional diagnostic report display with modern design
 */

import { motion } from 'framer-motion';
import { 
  X, 
  AlertTriangle, 
  Activity, 
  AlertCircle, 
  CheckCircle2, 
  FileText,
  Lightbulb,
  BookOpen,
  Shield,
  Download
} from 'lucide-react';
import { exportDiagnosticToPDFDirect } from '@/utils/pdf';

interface DiagnosticOutputProps {
  result: any;
  onClose?: () => void;
  variant?: 'overlay' | 'inline'; // 'overlay' for bottom overlay, 'inline' for page content
}

const RiskLevelBadge = ({ level }: { level: string }) => {
  const config = {
    High: {
      bg: 'bg-red-500/30',
      text: 'text-red-300',
      border: 'border-2 border-red-500',
      icon: AlertCircle,
      shadow: 'shadow-lg shadow-red-500/30',
      glow: 'ring-2 ring-red-500/50',
    },
    Medium: {
      bg: 'bg-amber-500/20',
      text: 'text-amber-400',
      border: 'border border-amber-500/50',
      icon: AlertTriangle,
      shadow: '',
      glow: '',
    },
    Low: {
      bg: 'bg-green-500/20',
      text: 'text-green-400',
      border: 'border border-green-500/50',
      icon: CheckCircle2,
      shadow: '',
      glow: '',
    },
  };

  const style = config[level as keyof typeof config] || config.Medium;
  const Icon = style.icon;

  return (
    <div className={`inline-flex items-center gap-2.5 px-5 py-2.5 rounded-lg ${style.bg} ${style.border} ${style.text} ${style.shadow} ${style.glow} ${
      level === 'High' ? 'font-bold' : 'font-semibold'
    }`}>
      <Icon size={level === 'High' ? 20 : 18} className={level === 'High' ? 'animate-pulse' : ''} />
      <span className={`${level === 'High' ? 'text-base' : 'text-sm'}`}>{level}</span>
    </div>
  );
};

const SectionCard = ({ 
  icon: Icon, 
  title, 
  children, 
  className = '' 
}: { 
  icon: any; 
  title: string; 
  children: React.ReactNode;
  className?: string;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className={`glass-dark rounded-xl p-5 border border-zinc-700/50 ${className}`}
  >
    <div className="flex items-center gap-3 mb-4">
      <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
        <Icon size={20} className="text-amber-400" />
      </div>
      <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide">
        {title}
      </h3>
    </div>
    <div className="text-zinc-300 text-sm leading-relaxed">
      {children}
    </div>
  </motion.div>
);

export const DiagnosticOutput = ({ result, onClose, variant = 'overlay' }: DiagnosticOutputProps) => {
  const report = result?.report || result;
  
  const containerClasses = variant === 'overlay' 
    ? "absolute bottom-0 left-0 right-0 bg-gradient-to-b from-zinc-900 via-zinc-900 to-black backdrop-blur-xl border-t border-amber-500/20 max-h-[70vh] overflow-y-auto shadow-2xl"
    : "relative bg-gradient-to-b from-zinc-900/95 via-zinc-900/95 to-black/95 backdrop-blur-xl border-0 rounded-lg overflow-hidden h-full";

  const handleDownloadPDF = async () => {
    if (!report) return;
    try {
      await exportDiagnosticToPDFDirect(report);
    } catch (error) {
      console.error('Failed to export PDF:', error);
    }
  };

  const renderMarkdown = (text: string) => {
    if (!text) return null;

    // Pre-process: Remove all ** and * symbols from the entire text
    const cleanText = text
      .replace(/\*\*/g, '')  // Remove all **
      .replace(/\*(?![*])/g, '')  // Remove single * (but not **)
      .replace(/###+/g, '##')  // Convert ### to ##
      .replace(/Prioritized Action Items for .+?:\s*/gi, '')  // Remove "Prioritized Action Items for X:"
      .replace(/\*\*?([^*]+)\*\*?:?\s*/g, '$1')  // Remove patterns like "*text:**"
      .replace(/\*+/g, '');  // Remove any remaining asterisks

    return cleanText.split('\n').map((line: string, idx: number) => {
      const trimmed = line.trim();
      
      if (!trimmed && idx === 0) return null;
      if (!trimmed) return <div key={idx} className="h-2" />;
      
      // Headers - convert ### to ##
      if (trimmed.startsWith('## ')) {
        let content = trimmed.replace(/^#+\s*/, '').trim();
        // Skip if it's a section label like "Prioritized Action Items"
        if (content.toLowerCase().includes('prioritized action items')) {
          return null;
        }
        return (
          <h2 key={idx} className="text-lg font-bold text-amber-400 mt-6 mb-3 first:mt-0 flex items-center gap-2">
            <div className="w-1 h-6 bg-amber-500 rounded-full" />
            {content}
          </h2>
        );
      }
      
      // Bullet points
      if (trimmed.startsWith('- ')) {
        let content = trimmed.substring(2).trim();
        // Skip if it's a section label
        if (content.toLowerCase().includes('prioritized action items') || 
            content.toLowerCase().startsWith('immediate') && content.toLowerCase().includes('activation')) {
          return null;
        }
        return (
          <div key={idx} className="flex items-start gap-3 mb-2.5 group">
            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0 group-hover:bg-amber-300 transition-colors" />
            <span className="text-zinc-300 flex-1 leading-relaxed">{content}</span>
          </div>
        );
      }
      
      // Numbered lists
      const numberedMatch = trimmed.match(/^\s*(\d+)[\.\)]\s*(.+)$/);
      if (numberedMatch) {
        let content = numberedMatch[2].trim();
        return (
          <div key={idx} className="flex items-start gap-3 mb-2.5">
            <span className="text-amber-400 font-semibold min-w-[24px] text-sm">{numberedMatch[1]}.</span>
            <span className="text-zinc-300 flex-1 leading-relaxed">{content}</span>
          </div>
        );
      }
      
      // Regular paragraph
      if (trimmed) {
        // Skip section labels
        if (trimmed.toLowerCase().includes('prioritized action items') ||
            (trimmed.toLowerCase().includes('immediate') && trimmed.toLowerCase().includes('activation'))) {
          return null;
        }
        return (
          <p key={idx} className="mb-3 text-zinc-300 leading-relaxed">
            {trimmed}
          </p>
        );
      }
      
      return <div key={idx} className="h-2" />;
    }).filter(Boolean);  // Remove null entries
  };

  const motionProps = variant === 'overlay' 
    ? {
        initial: { y: '100%' },
        animate: { y: 0 },
        exit: { y: '100%' },
        transition: { type: 'spring', damping: 25, stiffness: 200 }
      }
    : {
        initial: { opacity: 0, y: 20 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.3 }
      };

  return (
    <motion.div
      {...motionProps}
      className={containerClasses}
    >
      <div className={`${variant === 'inline' ? 'p-6' : 'p-6 max-w-6xl mx-auto'}`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-zinc-800/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-gradient-to-br from-amber-500/20 to-amber-600/10 border border-amber-500/30 shadow-lg shadow-amber-500/10">
              <FileText size={24} className="text-amber-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-zinc-100 tracking-tight">AI Diagnostic Analysis Result</h2>
              <p className="text-xs text-zinc-400 mt-0.5 font-medium">Comprehensive system health assessment</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {report && (
              <button
                onClick={handleDownloadPDF}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 hover:text-amber-300 border border-amber-500/30 hover:border-amber-500/50 transition-all text-sm font-medium"
                aria-label="Download PDF"
              >
                <Download size={16} />
                <span>Download PDF</span>
              </button>
            )}
            {onClose && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (onClose) {
                    onClose();
                  }
                }}
                className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/70 transition-all border border-transparent hover:border-zinc-700/50 cursor-pointer z-10 relative"
                aria-label="Close"
              >
                <X size={20} strokeWidth={2} />
              </button>
            )}
          </div>
        </div>

        {report && (
          <div id="diagnostic-report-content" className="space-y-6">
            {/* Risk Level - Simple Display */}
            {report.risk_level && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`rounded-xl border-2 overflow-hidden ${
                  report.risk_level === 'High' 
                    ? 'bg-gradient-to-br from-red-950/40 via-red-900/30 to-red-950/40 border-red-500/60 shadow-lg shadow-red-500/20' 
                    : report.risk_level === 'Medium'
                    ? 'bg-gradient-to-br from-amber-950/40 via-amber-900/30 to-amber-950/40 border-amber-500/60 shadow-lg shadow-amber-500/20'
                    : 'bg-gradient-to-br from-green-950/40 via-green-900/30 to-green-950/40 border-green-500/60 shadow-lg shadow-green-500/20'
                }`}
              >
                <div className="p-5">
                  <div className="flex items-center gap-4">
                    {/* Icon */}
                    <div className={`flex-shrink-0 p-3 rounded-lg ${
                      report.risk_level === 'High'
                        ? 'bg-red-500/20 border-2 border-red-500/50'
                        : report.risk_level === 'Medium'
                        ? 'bg-amber-500/20 border-2 border-amber-500/50'
                        : 'bg-green-500/20 border-2 border-green-500/50'
                    }`}>
                      {report.risk_level === 'High' ? (
                        <AlertCircle size={24} className="text-red-400" />
                      ) : report.risk_level === 'Medium' ? (
                        <AlertTriangle size={24} className="text-amber-400" />
                      ) : (
                        <Shield size={24} className="text-green-400" />
                      )}
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 flex items-center justify-between gap-4">
                      <div>
                        <div className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
                          Risk Assessment
                        </div>
                        <div className={`text-2xl font-bold ${
                          report.risk_level === 'High'
                            ? 'text-red-400'
                            : report.risk_level === 'Medium'
                            ? 'text-amber-400'
                            : 'text-green-400'
                        }`}>
                          {report.risk_level}
                        </div>
                      </div>
                      {report.risk_level === 'High' && (
                        <span className="px-3 py-1.5 text-xs font-semibold bg-red-500/30 text-red-300 border border-red-500/50 rounded-full whitespace-nowrap">
                          Immediate Attention
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Current Status */}
            {report.current_status && (
              <SectionCard icon={Activity} title="Current Status">
                <p className="text-zinc-200 leading-relaxed">{report.current_status}</p>
              </SectionCard>
            )}

            {/* Possible Causes */}
            {report.possible_causes && report.possible_causes.length > 0 && (
              <SectionCard icon={AlertCircle} title="Possible Causes">
                <ul className="space-y-2">
                  {report.possible_causes.map((cause: string, index: number) => (
                    <li key={index} className="flex items-start gap-2">
                      <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                      <span className="text-zinc-300">{cause}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}

            {/* Recommended Actions - Card Grid Layout */}
            {report.recommended_actions && report.recommended_actions.length > 0 && (
              <SectionCard icon={Lightbulb} title="Recommended Actions">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {report.recommended_actions.map((action: string, index: number) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700/50 hover:border-green-500/50 hover:bg-zinc-800/70 transition-all duration-200"
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                        <p className="text-sm text-zinc-300 leading-relaxed">{action}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* References */}
            {report.references && report.references.length > 0 && (
              <SectionCard icon={BookOpen} title="References">
                <ul className="space-y-2">
                  {report.references.map((ref: string, index: number) => (
                    <li key={index} className="flex items-start gap-2 text-zinc-400">
                      <span className="text-amber-400">→</span>
                      <span>{ref}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}

            {/* Full Markdown Report */}
            {report.markdown && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="glass-dark rounded-xl p-6 border border-zinc-700/50"
              >
                <div className="flex items-center gap-3 mb-5 pb-4 border-b border-zinc-800">
                  <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <FileText size={20} className="text-amber-400" />
                  </div>
                  <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide">
                    Full Report
                  </h3>
                </div>
                <div className="prose prose-invert max-w-none">
                  <div className="text-sm leading-relaxed space-y-2">
                    {renderMarkdown(report.markdown)}
                </div>
              </div>
              </motion.div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};
