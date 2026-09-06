import React, { useState, useRef } from 'react';
import { UploadCloud, File, X, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { uploadDocument } from '../services/api';

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt'];
const MAX_FILE_SIZE_MB = 25;

export default function DocumentUploader({ onUploadSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [successMessage, setSuccessMessage] = useState('');
  const fileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const validateAndSetFile = (file) => {
    setValidationError('');
    setSuccessMessage('');
    if (!file) return;

    const extension = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setValidationError(`Unsupported file type: "${extension}". Supported formats: PDF, DOCX, TXT`);
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setValidationError(`File exceeds max limit of ${MAX_FILE_SIZE_MB}MB.`);
      return;
    }

    setSelectedFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setValidationError('');
    setSuccessMessage('');
    setUploadProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleExecuteUpload = async () => {
    if (!selectedFile || isUploading) return;
    setIsUploading(true);
    setValidationError('');
    setSuccessMessage('');
    setUploadProgress(0);

    const result = await uploadDocument(selectedFile, (progress) => {
      setUploadProgress(progress);
    });

    setIsUploading(false);

    if (result.success) {
      setSuccessMessage(`Document "${result.data?.filename}" uploaded successfully.`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (onUploadSuccess) onUploadSuccess(result.data);
    } else {
      setValidationError(result.error || 'Failed to upload document.');
    }
  };

  return (
    <div className="document-uploader-card">
      <div className="uploader-header">
        <h3>Upload Enterprise Documents</h3>
        <p>Ingest policy manuals, handbooks, and SOPs into the local repository.</p>
      </div>

      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        id="document-file-input"
        disabled={isUploading}
      />

      {/* Drag & Drop Area */}
      {!selectedFile ? (
        <div
          className={`dropzone-box ${isDragging ? 'dragging' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && fileInputRef.current && fileInputRef.current.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              fileInputRef.current && fileInputRef.current.click();
            }
          }}
        >
          <div className="dropzone-icon-wrap">
            <UploadCloud size={36} />
          </div>
          <div className="dropzone-text-group">
            <p className="dropzone-main-text">
              <strong>Click to browse</strong> or drag & drop documents here
            </p>
            <p className="dropzone-sub-text">
              Supported formats: <strong>PDF, DOCX, TXT</strong> (Max {MAX_FILE_SIZE_MB}MB)
            </p>
          </div>
        </div>
      ) : (
        /* Selected File Display */
        <div className="selected-file-card">
          <div className="file-info-group">
            <div className="file-icon-wrap">
              <File size={22} />
            </div>
            <div className="file-meta">
              <div className="file-name">{selectedFile.name}</div>
              <div className="file-details">
                <span>{formatFileSize(selectedFile.size)}</span>
                <span>&bull;</span>
                <span className="file-type-pill">{selectedFile.name.split('.').pop().toUpperCase()}</span>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn-remove-file"
            onClick={handleRemoveFile}
            disabled={isUploading}
            title="Remove selected file"
            aria-label="Remove selected file"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Upload Progress Bar */}
      {isUploading && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.35rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Uploading document...</span>
            <span style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>{uploadProgress}%</span>
          </div>
          <div style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'linear-gradient(90deg, var(--accent-indigo), var(--accent-cyan))', transition: 'width 0.2s' }} />
          </div>
        </div>
      )}

      {/* Success Message */}
      {successMessage && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--color-online-bg)', border: '1px solid var(--color-online-border)', color: '#34d399', padding: '0.65rem 1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', marginTop: '1rem' }}>
          <CheckCircle size={16} />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Error Message */}
      {validationError && (
        <div className="uploader-error-banner" role="alert">
          <AlertCircle size={16} />
          <span>{validationError}</span>
        </div>
      )}

      {/* Upload Action Panel */}
      <div className="uploader-actions">
        <button
          type="button"
          id="btn-execute-upload"
          className="btn-upload-primary"
          disabled={!selectedFile || isUploading}
          onClick={handleExecuteUpload}
          title={selectedFile ? "Upload document to backend storage" : "Select a document first"}
        >
          {isUploading ? (
            <>
              <Loader2 size={16} className="spin-animation" />
              <span>Uploading to Storage...</span>
            </>
          ) : (
            <>
              <UploadCloud size={16} />
              <span>Upload Document</span>
            </>
          )}
        </button>
        <span className="uploader-phase-hint">
          Files are stored locally in <code>backend/documents/</code>.
        </span>
      </div>
    </div>
  );
}
