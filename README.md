# FAS Brain - Legal Document Research System

Full-stack application for legal document research with AI-powered search and entity extraction.

## Architecture

- **Frontend**: React (to be deployed on Railway)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (Supabase or Railway)
- **Hosting**: Railway.app (all-in-one)

## Features

- Document upload and processing (PDF, Word, Text)
- Automatic document categorization
- Entity extraction (people, organizations, locations, dates, amounts, events)
- Hybrid search (vector + keyword)
- Entity filtering
- AI-powered answer generation

## Backend Setup

### Local Development

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Run locally:
```bash
uvicorn main:app --reload
```

### Railway Deployment

1. Push code to GitHub
2. Connect GitHub repo to Railway
3. Railway will auto-detect Python and deploy
4. Add environment variables in Railway dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `OPENAI_API_KEY`

## API Endpoints

### Health Check
- `GET /` - Service status
- `GET /health` - Detailed health check

### Documents
- `POST /api/documents/upload` - Upload and process document
- `GET /api/documents` - List all documents
- `GET /api/documents/{id}` - Get document details
- `DELETE /api/documents/{id}` - Delete document

### Search
- `POST /api/search` - Enhanced hybrid search with entity filtering

### Entities
- `GET /api/entities` - List all entities
- `GET /api/entities/stats` - Entity statistics
- `GET /api/entities/types` - Available entity types

### Metadata
- `GET /api/document-types` - Available document types

## Frontend Setup

(To be added in Phase 2)

## Environment Variables

### Required
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `OPENAI_API_KEY` - OpenAI API key for entity extraction and answer generation

### Optional
- `PORT` - Server port (Railway sets this automatically)

## Technology Stack

### Backend
- FastAPI - Web framework
- Sentence Transformers - Embeddings (all-MiniLM-L6-v2)
- OpenAI - Entity extraction and answer generation
- Supabase - Database and storage
- Uvicorn - ASGI server

### Frontend (Coming)
- React
- Tailwind CSS
- Axios for API calls

## Cost Estimate

- Railway: $5/month free tier
- Supabase: Free tier (or existing subscription)
- OpenAI: ~$0.01-0.02 per document
- **Total**: ~$5-10/month for moderate usage

## Development Status

- [x] Backend API complete
- [x] Document processing pipeline
- [x] Entity extraction
- [x] Hybrid search
- [ ] Frontend UI
- [ ] Railway deployment
- [ ] Production testing

## License

Proprietary - FAS Brain Legal Research System
