/**
 * PDF Export Utility Functions
 * Helper functions for exporting diagnostic reports as PDF
 */

import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface DiagnosticReport {
  alarm_id?: string;
  risk_level?: string;
  current_status?: string;
  possible_causes?: string[];
  recommended_actions?: string[];
  references?: string[];
  markdown?: string;
  generated_at?: string;
  timestamp?: string;
}

/**
 * Format date for PDF
 */
const formatDate = (dateString?: string): string => {
  if (!dateString) return new Date().toLocaleString();
  try {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
};

/**
 * Clean markdown text for PDF
 */
const cleanMarkdown = (text: string): string => {
  if (!text) return '';
  return text
    // Remove markdown formatting
    .replace(/\*\*/g, '')
    .replace(/\*(?![*])/g, '')
    .replace(/###+/g, '##')
    .replace(/`/g, '')
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
    // Remove special characters that cause PDF issues
    .replace(/['']/g, "'")
    .replace(/[""]/g, '"')
    .replace(/[–—]/g, '-')
    .replace(/…/g, '...')
    // Remove extra whitespace
    .replace(/\s+/g, ' ')
    .replace(/\n\s*\n/g, '\n')
    // Remove control characters
    .replace(/[\x00-\x1F\x7F]/g, '')
    .trim();
};

/**
 * Export diagnostic report as PDF using html2canvas
 */
export const exportDiagnosticToPDF = async (
  report: DiagnosticReport,
  elementId: string = 'diagnostic-report-content'
): Promise<void> => {
  try {
    // Get the element to capture
    const element = document.getElementById(elementId);
    if (!element) {
      // Fallback: create a temporary element
      return await exportDiagnosticToPDFDirect(report);
    }

    // Capture the element as canvas
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#18181b', // zinc-900
      logging: false,
    });

    // Calculate PDF dimensions
    const imgWidth = 210; // A4 width in mm
    const imgHeight = (canvas.height * imgWidth) / canvas.width;
    const pdf = new jsPDF('p', 'mm', 'a4');
    
    // Add image to PDF
    const imgData = canvas.toDataURL('image/png');
    pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight);
    
    // Generate filename
    const filename = `diagnostic-report-${report.alarm_id || 'report'}-${Date.now()}.pdf`;
    
    // Save PDF
    pdf.save(filename);
  } catch (error) {
    console.error('Error exporting PDF:', error);
    // Fallback to direct PDF generation
    await exportDiagnosticToPDFDirect(report);
  }
};

/**
 * Export diagnostic report as PDF directly (without HTML capture)
 */
export const exportDiagnosticToPDFDirect = async (
  report: DiagnosticReport
): Promise<void> => {
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;
  const lineHeight = 7;
  const sectionSpacing = 10;

  // Helper function to add new page if needed
  const checkNewPage = (requiredSpace: number = lineHeight) => {
    if (yPos + requiredSpace > pageHeight - margin) {
      pdf.addPage();
      yPos = margin;
    }
  };

  // Helper function to add text with word wrap
  const addText = (text: string, fontSize: number = 11, isBold: boolean = false, color: string = '#000000') => {
    if (!text) return;
    
    // Clean text before adding to PDF
    const cleanedText = cleanMarkdown(String(text));
    
    pdf.setFontSize(fontSize);
    pdf.setTextColor(color);
    if (isBold) {
      pdf.setFont('helvetica', 'bold');
    } else {
      pdf.setFont('helvetica', 'normal');
    }
    
    const maxWidth = pageWidth - 2 * margin;
    const lines = pdf.splitTextToSize(cleanedText, maxWidth);
    
    lines.forEach((line: string) => {
      checkNewPage();
      // Ensure line is properly encoded and remove problematic characters
      const safeLine = line.replace(/[^\x20-\x7E\n\r]/g, '').trim();
      if (safeLine) {
        pdf.text(safeLine, margin, yPos);
        yPos += lineHeight;
      }
    });
  };

  // Title
  pdf.setFillColor(245, 158, 11); // amber-500
  pdf.rect(0, 0, pageWidth, 30, 'F');
  pdf.setTextColor('#ffffff');
  pdf.setFontSize(20);
  pdf.setFont('helvetica', 'bold');
  pdf.text('AI Diagnostic Analysis Report', margin, 20);
  yPos = 35;

  // Report Info
  addText(`Report ID: ${report.alarm_id || 'N/A'}`, 10, false, '#666666');
  addText(`Generated: ${formatDate(report.generated_at || report.timestamp)}`, 10, false, '#666666');
  yPos += sectionSpacing;

  // Risk Level
  if (report.risk_level) {
    checkNewPage(sectionSpacing);
    pdf.setFillColor(245, 158, 11, 0.1);
    pdf.rect(margin, yPos - 5, pageWidth - 2 * margin, 15, 'F');
    addText('Risk Level:', 12, true);
    const riskColor = report.risk_level === 'High' ? '#ef4444' : 
                     report.risk_level === 'Medium' ? '#f59e0b' : '#10b981';
    addText(report.risk_level, 14, true, riskColor);
    yPos += sectionSpacing;
  }

  // Current Status
  if (report.current_status) {
    checkNewPage(sectionSpacing);
    addText('Current Status', 14, true, '#f59e0b');
    yPos += 3;
    addText(cleanMarkdown(report.current_status), 11, false);
    yPos += sectionSpacing;
  }

  // Possible Causes
  if (report.possible_causes && report.possible_causes.length > 0) {
    checkNewPage(sectionSpacing);
    addText('Possible Causes', 14, true, '#f59e0b');
    yPos += 3;
    report.possible_causes.forEach((cause) => {
      checkNewPage();
      addText(`• ${cleanMarkdown(cause)}`, 11, false);
    });
    yPos += sectionSpacing;
  }

  // Recommended Actions
  if (report.recommended_actions && report.recommended_actions.length > 0) {
    checkNewPage(sectionSpacing);
    addText('Recommended Actions', 14, true, '#f59e0b');
    yPos += 3;
    report.recommended_actions.forEach((action) => {
      checkNewPage();
      addText(`• ${cleanMarkdown(action)}`, 11, false);
    });
    yPos += sectionSpacing;
  }

  // References
  if (report.references && report.references.length > 0) {
    checkNewPage(sectionSpacing);
    addText('References', 14, true, '#f59e0b');
    yPos += 3;
    report.references.forEach((ref, index) => {
      checkNewPage();
      // Clean reference text and format properly
      const cleanedRef = cleanMarkdown(ref);
      // Remove any markdown-style brackets and format as simple text
      const formattedRef = cleanedRef.replace(/^\[|\]$/g, '').trim();
      addText(`${index + 1}. ${formattedRef}`, 11, false);
    });
    yPos += sectionSpacing;
  }

  // Full Report (Markdown)
  if (report.markdown) {
    checkNewPage(sectionSpacing);
    addText('Full Report', 14, true, '#f59e0b');
    yPos += 3;
    
    const cleanedMarkdown = cleanMarkdown(report.markdown);
    const lines = cleanedMarkdown.split('\n');
    
    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        yPos += 3; // Empty line
        return;
      }
      
      if (trimmed.startsWith('## ')) {
        checkNewPage(sectionSpacing);
        addText(trimmed.replace(/^##\s+/, ''), 12, true, '#f59e0b');
        yPos += 2;
      } else if (trimmed.startsWith('- ')) {
        checkNewPage();
        addText(`• ${trimmed.substring(2)}`, 11, false);
      } else {
        checkNewPage();
        addText(trimmed, 11, false);
      }
    });
  }

  // Footer
  const totalPages = pdf.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);
    pdf.setFontSize(8);
    pdf.setTextColor('#999999');
    pdf.text(
      `Page ${i} of ${totalPages}`,
      pageWidth / 2,
      pageHeight - 10,
      { align: 'center' }
    );
    pdf.text(
      `Generated by BESS Diagnostic System`,
      margin,
      pageHeight - 10
    );
  }

  // Generate filename
  const filename = `diagnostic-report-${report.alarm_id || 'report'}-${Date.now()}.pdf`;
  
  // Save PDF
  pdf.save(filename);
};

/**
 * Export multiple diagnostic reports as a single PDF
 */
export const exportMultipleDiagnosticsToPDF = async (
  reports: DiagnosticReport[]
): Promise<void> => {
  if (!reports || reports.length === 0) {
    throw new Error('No reports to export');
  }

  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;
  const lineHeight = 7;
  const sectionSpacing = 10;

  // Helper function to add new page if needed
  const checkNewPage = (requiredSpace: number = lineHeight) => {
    if (yPos + requiredSpace > pageHeight - margin) {
      pdf.addPage();
      yPos = margin;
    }
  };

  // Helper function to add text with word wrap
  const addText = (text: string, fontSize: number = 11, isBold: boolean = false, color: string = '#000000') => {
    if (!text) return;
    
    // Clean text before adding to PDF
    const cleanedText = cleanMarkdown(String(text));
    
    pdf.setFontSize(fontSize);
    pdf.setTextColor(color);
    if (isBold) {
      pdf.setFont('helvetica', 'bold');
    } else {
      pdf.setFont('helvetica', 'normal');
    }
    
    const maxWidth = pageWidth - 2 * margin;
    const lines = pdf.splitTextToSize(cleanedText, maxWidth);
    
    lines.forEach((line: string) => {
      checkNewPage();
      // Ensure line is properly encoded and remove problematic characters
      const safeLine = line.replace(/[^\x20-\x7E\n\r]/g, '').trim();
      if (safeLine) {
        pdf.text(safeLine, margin, yPos);
        yPos += lineHeight;
      }
    });
  };

  // Process each report
  reports.forEach((report, index) => {
    // Add page break between reports (except first)
    if (index > 0) {
      pdf.addPage();
      yPos = margin;
    }

    // Title for each report
    pdf.setFillColor(245, 158, 11); // amber-500
    pdf.rect(0, 0, pageWidth, 30, 'F');
    pdf.setTextColor('#ffffff');
    pdf.setFontSize(18);
    pdf.setFont('helvetica', 'bold');
    pdf.text(`Diagnostic Report ${index + 1} of ${reports.length}`, margin, 20);
    yPos = 35;

    // Report Info
    addText(`Report ID: ${report.alarm_id || 'N/A'}`, 10, false, '#666666');
    addText(`Generated: ${formatDate(report.generated_at || report.timestamp)}`, 10, false, '#666666');
    yPos += sectionSpacing;

    // Risk Level
    if (report.risk_level) {
      checkNewPage(sectionSpacing);
      pdf.setFillColor(245, 158, 11, 0.1);
      pdf.rect(margin, yPos - 5, pageWidth - 2 * margin, 15, 'F');
      addText('Risk Level:', 12, true);
      const riskColor = report.risk_level === 'High' ? '#ef4444' : 
                       report.risk_level === 'Medium' ? '#f59e0b' : '#10b981';
      addText(report.risk_level, 14, true, riskColor);
      yPos += sectionSpacing;
    }

    // Current Status
    if (report.current_status) {
      checkNewPage(sectionSpacing);
      addText('Current Status', 14, true, '#f59e0b');
      yPos += 3;
      addText(cleanMarkdown(report.current_status), 11, false);
      yPos += sectionSpacing;
    }

    // Possible Causes
    if (report.possible_causes && report.possible_causes.length > 0) {
      checkNewPage(sectionSpacing);
      addText('Possible Causes', 14, true, '#f59e0b');
      yPos += 3;
      report.possible_causes.forEach((cause) => {
        checkNewPage();
        addText(`• ${cleanMarkdown(cause)}`, 11, false);
      });
      yPos += sectionSpacing;
    }

    // Recommended Actions
    if (report.recommended_actions && report.recommended_actions.length > 0) {
      checkNewPage(sectionSpacing);
      addText('Recommended Actions', 14, true, '#f59e0b');
      yPos += 3;
      report.recommended_actions.forEach((action) => {
        checkNewPage();
        addText(`• ${cleanMarkdown(action)}`, 11, false);
      });
      yPos += sectionSpacing;
    }

    // References
    if (report.references && report.references.length > 0) {
      checkNewPage(sectionSpacing);
      addText('References', 14, true, '#f59e0b');
      yPos += 3;
      report.references.forEach((ref, index) => {
        checkNewPage();
        // Clean reference text and format properly
        const cleanedRef = cleanMarkdown(ref);
        // Remove any markdown-style brackets and format as simple text
        const formattedRef = cleanedRef.replace(/^\[|\]$/g, '').trim();
        addText(`${index + 1}. ${formattedRef}`, 11, false);
      });
      yPos += sectionSpacing;
    }

    // Full Report (Markdown) - truncated for batch export
    if (report.markdown && index === 0) {
      // Only include full markdown for first report to save space
      checkNewPage(sectionSpacing);
      addText('Full Report', 14, true, '#f59e0b');
      yPos += 3;
      
      const cleanedMarkdown = cleanMarkdown(report.markdown);
      const lines = cleanedMarkdown.split('\n').slice(0, 20); // Limit to first 20 lines
      
      lines.forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
          yPos += 3;
          return;
        }
        
        if (trimmed.startsWith('## ')) {
          checkNewPage(sectionSpacing);
          addText(trimmed.replace(/^##\s+/, ''), 12, true, '#f59e0b');
          yPos += 2;
        } else if (trimmed.startsWith('- ')) {
          checkNewPage();
          addText(`• ${trimmed.substring(2)}`, 11, false);
        } else {
          checkNewPage();
          addText(trimmed, 11, false);
        }
      });
    }
  });

  // Footer
  const totalPages = pdf.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);
    pdf.setFontSize(8);
    pdf.setTextColor('#999999');
    pdf.text(
      `Page ${i} of ${totalPages}`,
      pageWidth / 2,
      pageHeight - 10,
      { align: 'center' }
    );
    pdf.text(
      `Generated by BESS Diagnostic System - ${reports.length} reports`,
      margin,
      pageHeight - 10
    );
  }

  // Generate filename
  const filename = `diagnostic-reports-batch-${Date.now()}.pdf`;
  
  // Save PDF
  pdf.save(filename);
};

