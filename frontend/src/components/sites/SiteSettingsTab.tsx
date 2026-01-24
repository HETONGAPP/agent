/**
 * Site Settings Tab Component
 * Displays site settings configuration
 */

import { Settings } from 'lucide-react';

export const SiteSettingsTab = () => {
  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-700/50">
        <Settings className="text-blue-400" size={20} />
        <h3 className="text-xl font-semibold text-white">Site Settings</h3>
      </div>
      <div className="text-center py-12">
        <Settings size={48} className="mx-auto text-gray-600 mb-4" />
        <p className="text-gray-400 text-lg mb-2">Settings configuration</p>
        <p className="text-gray-500 text-sm">Advanced settings will be displayed here</p>
      </div>
    </div>
  );
};








