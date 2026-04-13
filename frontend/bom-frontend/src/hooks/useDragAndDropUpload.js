import { useCallback, useEffect, useRef, useState } from 'react';

export const useDragAndDropUpload = (processFile) => {
  const [isDragging, setIsDragging] = useState(false);
  const dragDepthRef = useRef(0);

  useEffect(() => {
    const preventWindowFileDrop = (event) => {
      if (event.dataTransfer?.types?.includes('Files')) {
        event.preventDefault();
      }
    };

    window.addEventListener('dragover', preventWindowFileDrop);
    window.addEventListener('drop', preventWindowFileDrop);

    return () => {
      window.removeEventListener('dragover', preventWindowFileDrop);
      window.removeEventListener('drop', preventWindowFileDrop);
    };
  }, []);

  const onDragEnter = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current += 1;
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.dataTransfer?.types?.includes('Files')) return;
    event.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  }, []);

  const onDrop = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current = 0;
    setIsDragging(false);
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      processFile(event.dataTransfer.files[0]);
      event.dataTransfer.clearData();
    }
  }, [processFile]);

  return {
    isDragging,
    onDragEnter,
    onDragLeave,
    onDragOver,
    onDrop,
  };
};
