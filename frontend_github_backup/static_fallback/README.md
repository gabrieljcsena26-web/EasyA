Fallback static dashboard

Purpose
- Quick way to verify backend endpoints and dev JWT flow without depending on the CRA dev server.

Usage
1. Ensure backend is running at http://127.0.0.1:8000
2. Serve this folder (options):

   - With Python 3 built-in server (quick):
     ```powershell
     cd frontend_v2/static_fallback
     python -m http.server 3002
     ```

   - With `npx serve` (recommended for single-page lookups):
     ```powershell
     cd frontend_v2/static_fallback
     npx serve -s . -l 3002
     ```

3. Open http://localhost:3002 in your browser.
4. Paste a dev JWT into the "Dev JWT" box and click "Salvar". Then click "Carregar /admin/config" and "Carregar /appointments".

Notes
- If your backend runs on another host/port, edit `app.js` and change `API_BASE` accordingly.
