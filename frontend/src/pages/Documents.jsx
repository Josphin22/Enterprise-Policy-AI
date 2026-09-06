import React, { useState, useEffect, useCallback } from 'react';
import { Files, Info } from 'lucide-react';
import DocumentUploader from '../components/DocumentUploader';
import DocumentTable from '../components/DocumentTable';
import { getDocuments } from '../services/api';

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    const result = await getDocuments();
    setIsLoading(false);
    if (result.success) {
      setDocuments(result.documents);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  return (
    <div className="documents-page-container">
      {/* Page Header */}
      <div className="page-header-intro">
        <div>
          <h1 className="page-main-heading">Document Management</h1>
          <p className="page-sub-heading">
            Upload and organize corporate policy manuals, HR guidelines, and standard operating procedures.
          </p>
        </div>
      </div>

      {/* Information Callout */}
      <div className="enterprise-info-banner">
        <Info size={18} />
        <div>
          <strong>Document Storage:</strong> Uploaded files are safely stored in the backend repository and tracked via unique document identifiers.
        </div>
      </div>

      {/* Upload Section */}
      <DocumentUploader onUploadSuccess={fetchDocuments} />

      {/* Documents Table / Repository View */}
      <DocumentTable
        documents={documents}
        onRefresh={fetchDocuments}
        isLoading={isLoading}
      />
    </div>
  );
}
