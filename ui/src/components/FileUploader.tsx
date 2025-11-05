import { ChangeEvent, DragEvent, useRef, useState } from 'react';

import '../styles/uploader.css';

type FileUploaderProps = {
  accept?: string[];
  maxSizeMB?: number;
  onUpload: (file: File) => Promise<void> | void;
};

const ACCEPT_DEFAULT = ['.pptx', '.pdf'];

const FileUploader = ({ accept = ACCEPT_DEFAULT, maxSizeMB = 100, onUpload }: FileUploaderProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`;
    if (!accept.includes(ext)) {
      setError(`不支持的文件类型：${ext}`);
      return;
    }
    if (file.size / (1024 * 1024) > maxSizeMB) {
      setError(`文件大小超过 ${maxSizeMB}MB 限制`);
      return;
    }
    setError(null);
    try {
      setUploading(true);
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败，请稍后再试');
    } finally {
      setUploading(false);
    }
  };

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    void handleFile(file);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files?.[0];
    void handleFile(file);
  };

  const onBrowse = () => {
    inputRef.current?.click();
  };

  return (
    <div className="uploader-container">
      <div
        className={`uploader-dropzone ${dragOver ? 'dragging' : ''}`}
        role="button"
        tabIndex={0}
        onClick={onBrowse}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={onDrop}
        aria-label="上传 pptx 或 pdf 文件"
      >
        <p>{uploading ? '上传中，请稍候…' : '拖拽 PPT/PDF 到此处，或点击选择文件'}</p>
        <p className="uploader-hint">支持 {accept.join('、')}，最大 {maxSizeMB}MB</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept.join(',')}
        className="visually-hidden"
        onChange={onInputChange}
        tabIndex={-1}
      />
      {error && (
        <div className="uploader-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
};

export default FileUploader;
