# Frontend setup (Member 3)

From the repo root:
```bash
cd frontend
npm create vite@latest . -- --template react-ts
# if asked about a non-empty directory choose: "Ignore files and continue"
npm install
npm install @supabase/supabase-js cytoscape axios react-router-dom
npm install -D @types/cytoscape
mkdir -p src/components src/pages src/services src/types
```
Create `frontend/.env` (not committed):
```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_BASE_URL=http://localhost:8000
```
Never put the Supabase service-role key in the frontend.
Run: `npm run dev` -> http://localhost:5173
