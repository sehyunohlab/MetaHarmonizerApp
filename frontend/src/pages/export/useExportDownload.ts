import { useState } from 'react';
import { toast } from 'sonner';

/** Runs one download at a time, with toast feedback; ``downloading`` holds the
 *  key of the download in progress. */
export function useExportDownload() {
  const [downloading, setDownloading] = useState<string | null>(null);

  const run = async (key: string, action: () => Promise<void>) => {
    setDownloading(key);
    try {
      await action();
      toast.success('Download started');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Download failed. Please try again.');
    } finally {
      setDownloading(null);
    }
  };

  return { downloading, run };
}
