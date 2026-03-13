# MySmartReport Backend Server

This repository contains the backend server for the MySmartReport application, built with Python and FastAPI. It handles parsing IPG syllabus documents, generating AI-enriched academic reflections and teaching strategies using Google Gemini, and managing user data with Firebase.

## Technology Stack

- **Framework:** FastAPI (Python)
- **AI Integration:** Google GenAI SDK (Gemini)
- **Authentication & Database:** Firebase Admin SDK (Auth & Firestore)
- **File Parsing:** `openpyxl` (for reading `.xlsx` template files)
- **Server:** Uvicorn (ASGI)

## Prerequisites

- Python 3.10+
- A Google Gemini API Key
- A Firebase project with Firestore and Authentication enabled
- A Firebase Admin SDK Service Account JSON file

## Setup

1. **Clone the repository and navigate to the backend directory.**

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root of the backend directory with the following variables:
   ```env
   # Firebase Database configuration
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com

   # Gemini AI integration
   GEMINI_API_KEY=your-gemini-api-key
   GEMINI_MODEL=gemini-2.5-pro # Or your preferred model

   # Admin & Security
   ADMIN_EMAILS=admin@example.com
   PROMO_CODES=BETA2025:30,FREEPREMIUM:14 # Code:Days
   ```
   *(Alternatively, you can place your `serviceAccountKey.json` directly in the backend directory instead of using individual FIREBASE_ variables).*

## Running Locally

To start the FastAPI development server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be accessible at `http://localhost:8000`. FastAPIs automatic interactive API documentation will be available at `http://localhost:8000/docs`.

## Key Features & Endpoints

- **`/api/upload`**: Parses IPG syllabus Excel templates. Uses Gemini to extract metadata (course code, lecturer, intake, etc.) and week-by-week topics.
- **`/api/draft/generate` (SSE)**: Streams AI-generated teaching strategies (Lecture, Tutorial, E-Learning) and reflections paragraph-by-paragraph via Server-Sent Events.
- **`/api/download`**: Compiles chosen drafts into downloadable `.xlsx` files or a zipped archive of multiple drafts.
- **`/api/auth`**: Validates Firebase credentials and handles promotion code redemption for Premium tier access.

## Deployment

The backend is designed to be easily deployed to containerized platforms like Render or Koyeb.

### Deploying to Koyeb / Render:
1. Connect this repository to your hosting provider.
2. Ensure the build command is set to install requirements (`pip install -r requirements.txt`).
3. Ensure the start command is set to run Uvicorn (`uvicorn main:app --host 0.0.0.0 --port $PORT`).
4. **Crucial:** Add all the `.env` variables from above directly into the Environment Variables settings of your hosting dashboard. *Do not commit the `.env` or Service Account JSON file to the repository.*
