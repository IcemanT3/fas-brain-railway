# FAS Brain API Documentation

## API Contract Compliance

This document clarifies which routes are **charter-compliant** (part of the official API contract) vs **beta/internal** routes (for testing and development).

---

## Contract Routes (Charter-Compliant)

These routes implement the official API contract defined in the project charter. They are stable, documented, and guaranteed to remain compatible.

### OneDrive Integration

#### `POST /sources/onedrive/sync`

Trigger OneDrive folder synchronization.

**Request Body:**
```json
{
  "folder_path": "optional/path",  // null = sync all configured folders
  "recursive": true,
  "deduplicate": true
}
```

**Response:**
```json
{
  "status": "accepted",
  "job_id": "uuid-here",
  "message": "OneDrive sync job queued. Check /admin/jobs/{job_id} for status."
}
```

**Status Codes:**
- `200` - Job enqueued successfully
- `429` - Queue full, try again later
- `500` - Server error

---

### Job Monitoring

#### `GET /admin/jobs/{job_id}`

Check the status of any background job (document processing, OneDrive sync, etc.).

**Response:**
```json
{
  "job_id": "uuid-here",
  "type": "onedrive_sync",
  "status": "RUNNING",  // QUEUED | RUNNING | DONE | ERROR
  "progress": 0.65,     // 0.0 to 1.0
  "progress_message": "Processing document 13 of 20...",
  "created_at": "2025-01-07T10:00:00Z",
  "started_at": "2025-01-07T10:00:05Z",
  "completed_at": null,
  "result": null,       // Populated when status=DONE
  "error": null         // Populated when status=ERROR
}
```

**Status Codes:**
- `200` - Job found
- `404` - Job not found
- `500` - Server error

---

## Beta Routes (Testing/Development)

These routes are functional but not part of the official charter API contract. They may change or be deprecated in future versions. Use for testing and development only.

### Document Upload (Beta)

#### `POST /api/documents/upload`

Direct document upload with async processing.

**Note:** For production OneDrive workflows, use the charter-compliant `/sources/onedrive/sync` endpoint instead.

**Request:**
- Multipart form upload
- Field: `file`

**Response:**
```json
{
  "job_id": "uuid-here",
  "filename": "document.pdf",
  "status": "queued",
  "message": "Document queued for processing. Check /api/jobs/{job_id} for status."
}
```

---

### Job Status (Beta)

#### `GET /api/jobs/{job_id}`

Beta version of job status endpoint. Same functionality as `/admin/jobs/{job_id}` but in beta namespace.

**Response:** Same as `/admin/jobs/{job_id}`

---

#### `GET /api/jobs`

Get job queue statistics.

**Response:**
```json
{
  "queue_depth": 5,
  "running_count": 3,
  "max_queue_size": 100,
  "max_concurrent": 3
}
```

---

## Migration Guide

If you're currently using beta routes, migrate to charter-compliant routes:

### Before (Beta):
```javascript
// Upload document directly
const response = await fetch('/api/documents/upload', {
  method: 'POST',
  body: formData
});
const { job_id } = await response.json();

// Check status
const status = await fetch(`/api/jobs/${job_id}`);
```

### After (Charter-Compliant):
```javascript
// Trigger OneDrive sync (recommended workflow)
const response = await fetch('/sources/onedrive/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    folder_path: null,  // sync all folders
    recursive: true,
    deduplicate: true
  })
});
const { job_id } = await response.json();

// Check status (admin namespace)
const status = await fetch(`/admin/jobs/${job_id}`);
```

---

## Backpressure & Rate Limiting

All async endpoints implement backpressure:

- **Max queue size:** 100 jobs
- **Max concurrent workers:** 3
- **HTTP 429** returned when queue is full
- **Retry strategy:** Exponential backoff recommended

---

## Job Types

The system supports these job types:

| Type | Description | Typical Duration |
|------|-------------|------------------|
| `process_document` | Extract text, entities, embeddings | 30-60s |
| `onedrive_sync` | Sync OneDrive folder | 1-5 min |
| `generate_package` | Create case package ZIP | 10-30s |
| `deduplicate` | Find and merge duplicates | 1-2 min |

---

## Charter Compliance Status

✅ **Charter-Compliant Routes:**
- `POST /sources/onedrive/sync`
- `GET /admin/jobs/{job_id}`

⚠️ **Beta Routes (Not in Charter):**
- `POST /api/documents/upload`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs`

---

## Support

For questions about the API contract or charter compliance:
- Review project charter in Supabase (`project_charter` table)
- Check `/health` endpoint for charter verification status
- Contact system administrator

---

**Last Updated:** 2025-01-07  
**Charter Hash:** `0855005508bfd5765b43ef85edacb7b2`  
**API Version:** 1.0.0
