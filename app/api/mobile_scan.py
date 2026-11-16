"""Mobile scan API routes - serves mobile capture page and handles image uploads.

All routes are registered on the NiceGUI ``app`` object (which is a FastAPI app)
and served on the same port as the main web UI.
"""
import os
import uuid
import logging
from pathlib import Path

from fastapi import UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from nicegui import app

from app.services.mobile_scan_service import MobileScanService
from analysercomptacore.services import ArchiveService

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
    'application/json',
}

EXTENSION_MAP = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/heic': '.heic',
    'image/heif': '.heif',
    'application/json': '.json',
}


def register_mobile_scan_routes() -> None:
    """Register all mobile-scan API routes on the NiceGUI FastAPI app."""

    # ------------------------------------------------------------------
    # Serve mobile import page (bulk folder upload)
    # ------------------------------------------------------------------
    @app.get('/mobile/import/{token}')
    async def mobile_import_page(token: str):
        session = MobileScanService.validate_session(token)
        if not session:
            return HTMLResponse(
                '<html><body><h2>Link expired or invalid</h2>'
                '<p>Please generate a new QR code from the desktop application.</p>'
                '</body></html>',
                status_code=404,
            )
        return HTMLResponse(_build_mobile_import_html(token))

    # ------------------------------------------------------------------
    # Route 5: Receive single file from bulk import
    # ------------------------------------------------------------------
    @app.post('/api/mobile/import/upload/{token}')
    async def upload_import_file(token: str, file: UploadFile = File(...)):
        import json as _json

        session = MobileScanService.validate_session(token)
        if not session:
            raise HTTPException(status_code=403, detail='Session expired or invalid')

        content_type = file.content_type or ''
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid file type: {content_type}. Accepted: JPEG, PNG, WebP, HEIC, JSON.',
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail='File too large (max 10 MB)')
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail='Empty file')

        file_extension = EXTENSION_MAP.get(content_type, '.jpg')
        original_name = file.filename or f'import{file_extension}'
        is_json = content_type == 'application/json'

        # Archive with original filename (dedup if name already exists)
        try:
            archive_dir = Path(ArchiveService._get_archive_dir())
            safe_name = Path(original_name).stem
            ext = file_extension.lstrip('.')
            target = archive_dir / f"{safe_name}.{ext}"
            counter = 1
            while target.exists():
                target = archive_dir / f"{safe_name}_{counter}.{ext}"
                counter += 1
            target.write_bytes(file_bytes)
            archived_filename = target.name
            logger.info(f"Archived import file: {archived_filename} (original: {original_name})")
        except Exception as e:
            logger.error(f"Failed to archive {original_name}: {e}")
            return JSONResponse({
                'status': 'error',
                'error': f'Archive failed: {e}',
            }, status_code=200)

        # JSON files are sidecars — archive only, no receipt entry
        if is_json:
            return JSONResponse({
                'status': 'json_archived',
                'archived_as': archived_filename,
                'original_name': original_name,
            })

        # --- Image file: create a receipt entry ---
        receipt_id = uuid.uuid4().hex[:12]
        MobileScanService.add_receipt(token, receipt_id, status='processing')

        ocr_result = {
            'success': True,
            'archived_filename': archived_filename,
            'original_name': original_name,
            'supplier_name': None,
            'facture_num': None,
            'facture_date': None,
            'amount_ht': None,
            'amount_tva': None,
            'amount_ttc': None,
            'line_items': [],
        }

        # Check for a JSON sidecar already in the archive (uploaded earlier
        # in the same batch or from a previous session).
        json_sidecar = archive_dir / f"{Path(archived_filename).stem}.json"
        if json_sidecar.exists():
            try:
                data = _json.loads(json_sidecar.read_text(encoding='utf-8'))
                from app.services.outbound_match_service import _parse_ocr_sidecar
                ocr_result.update(_parse_ocr_sidecar(data))
                logger.info(f"Populated receipt from JSON sidecar: {json_sidecar.name}")
            except Exception as e:
                logger.warning(f"Failed to read JSON sidecar {json_sidecar.name}: {e}")

        MobileScanService.update_receipt(
            token, receipt_id,
            status='ready',
            ocr_result=ocr_result,
        )

        return JSONResponse({
            'receipt_id': receipt_id,
            'status': 'ready',
            'archived_as': archived_filename,
            'original_name': original_name,
            'summary': {
                'supplier': ocr_result.get('supplier_name'),
                'amount': ocr_result.get('amount_ttc'),
                'invoice_num': ocr_result.get('facture_num'),
            },
            'error': None,
        })

    # ------------------------------------------------------------------
    # Route 6: Desktop polls import progress
    # ------------------------------------------------------------------
    @app.get('/api/mobile/import/status/{token}')
    async def check_import_status(token: str):
        session = MobileScanService.validate_session(token)
        if not session:
            return JSONResponse({'active': False, 'import_count': 0, 'files': []})

        receipts = MobileScanService.get_receipts(token)
        files = []
        for r in receipts:
            ocr = r.get('ocr_result') or {}
            files.append({
                'id': r['id'],
                'archived_as': ocr.get('archived_filename', ''),
                'original_name': ocr.get('original_name', ''),
            })
        return JSONResponse({
            'active': True,
            'import_count': len(receipts),
            'files': files,
        })

    logger.info("Mobile scan API routes registered")

def _build_mobile_import_html(token: str) -> str:
    """Build the self-contained mobile import HTML page for bulk folder upload."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Import Receipts</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            background: #6D4C41;
            color: white;
            padding: 16px 20px;
            text-align: center;
            font-size: 18px;
            font-weight: 600;
        }}
        .content {{
            flex: 1;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
        }}
        .info-box {{
            width: 100%;
            max-width: 360px;
            background: #FFF3E0;
            border-radius: 8px;
            padding: 14px 16px;
            font-size: 14px;
            color: #E65100;
            text-align: center;
        }}
        .counter {{
            font-size: 48px;
            font-weight: 700;
            color: #6D4C41;
        }}
        .counter-label {{
            font-size: 14px;
            color: #666;
            margin-top: -8px;
        }}
        .select-btn {{
            width: 100%;
            max-width: 320px;
            padding: 18px 24px;
            background: #6D4C41;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        .select-btn:active {{ background: #4E342E; }}
        .select-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .upload-btn {{
            width: 100%;
            max-width: 320px;
            padding: 18px 24px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            display: none;
        }}
        .upload-btn:active {{ background: #388E3C; }}
        .upload-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        #folderInput {{ display: none; }}
        .progress-section {{
            width: 100%;
            max-width: 320px;
            display: none;
        }}
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #E0E0E0;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 8px;
        }}
        .progress-bar-fill {{
            height: 100%;
            background: #6D4C41;
            width: 0%;
            transition: width 0.3s;
        }}
        .progress-text {{
            text-align: center;
            font-size: 14px;
            color: #666;
        }}
        .file-list {{
            width: 100%;
            max-width: 320px;
            max-height: 200px;
            overflow-y: auto;
            font-size: 13px;
            color: #555;
        }}
        .file-item {{
            padding: 4px 8px;
            border-bottom: 1px solid #eee;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .file-item.done {{ color: #2E7D32; }}
        .file-item.error {{ color: #C62828; }}
        .done-btn {{
            width: 100%;
            max-width: 320px;
            padding: 14px 24px;
            background: #757575;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 8px;
            display: none;
        }}
        .done-screen {{
            text-align: center;
            padding: 40px 20px;
        }}
        .done-screen .checkmark {{
            font-size: 64px;
            color: #4CAF50;
        }}
        .subfolder-info {{
            font-size: 13px;
            color: #888;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">&#128230; Import Receipts</div>

    <div class="content" id="mainContent">
        <div class="info-box">
            Select your Pictures folder, then your JSON folder. Tap each button once, then Upload All.
        </div>

        <div class="counter" id="counter">0</div>
        <div class="counter-label" id="counterLabel">files selected</div>

        <input type="file" id="folderInput" webkitdirectory multiple>

        <button class="select-btn" id="selectBtn" onclick="selectFolder('images')">
            &#128193; 1. Select Pictures Folder
        </button>

        <button class="select-btn" id="selectJsonBtn" onclick="selectFolder('json')" style="background:#5D4037; display:none">
            &#128196; 2. Select JSON Folder (optional)
        </button>

        <div class="subfolder-info" id="subfolderInfo"></div>

        <div class="file-list" id="fileList"></div>

        <button class="upload-btn" id="uploadBtn" onclick="startUpload()">
            &#128640; Upload All
        </button>

        <div class="progress-section" id="progressSection">
            <div class="progress-bar">
                <div class="progress-bar-fill" id="progressBarFill"></div>
            </div>
            <div class="progress-text" id="progressText">Uploading...</div>
        </div>

        <button class="done-btn" id="doneBtn" onclick="onDone()">Done</button>
    </div>

    <div class="done-screen" id="doneScreen" style="display:none">
        <div class="checkmark">&#10004;</div>
        <h2 style="margin:16px 0">Import Complete!</h2>
        <p style="color:#666" id="doneSummary"></p>
        <p style="color:#E65100; margin-top:16px; font-size:14px; font-weight:600">
            You can now delete these files from your phone.
        </p>
        <p style="color:#999; margin-top:12px; font-size:14px">You can close this page.</p>
    </div>

    <script>
        const TOKEN = '{token}';
        const API_UPLOAD = '/api/mobile/import/upload/' + TOKEN;
        const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

        let imageFiles = [];
        let jsonFiles = [];
        let pendingMode = null;   // 'images' or 'json'
        let uploadedCount = 0;
        let jsonUploadedCount = 0;
        let errorCount = 0;

        const folderInput = document.getElementById('folderInput');
        const selectBtn = document.getElementById('selectBtn');
        const selectJsonBtn = document.getElementById('selectJsonBtn');
        const uploadBtn = document.getElementById('uploadBtn');
        const counterEl = document.getElementById('counter');
        const counterLabel = document.getElementById('counterLabel');
        const subfolderInfo = document.getElementById('subfolderInfo');
        const fileList = document.getElementById('fileList');
        const progressSection = document.getElementById('progressSection');
        const progressBarFill = document.getElementById('progressBarFill');
        const progressText = document.getElementById('progressText');
        const doneBtn = document.getElementById('doneBtn');

        function selectFolder(mode) {{
            pendingMode = mode;
            folderInput.value = '';
            folderInput.click();
        }}

        function refreshUI() {{
            const totalFiles = imageFiles.length + jsonFiles.length;
            counterEl.textContent = totalFiles;

            const parts = [];
            if (imageFiles.length > 0) parts.push(`${{imageFiles.length}} image${{imageFiles.length !== 1 ? 's' : ''}}`);
            if (jsonFiles.length > 0) parts.push(`${{jsonFiles.length}} JSON${{jsonFiles.length !== 1 ? 's' : ''}}`);
            counterLabel.textContent = parts.join(' + ') || 'files selected';

            // Show file preview
            fileList.innerHTML = '';
            jsonFiles.forEach(f => {{
                const div = document.createElement('div');
                div.className = 'file-item';
                div.id = 'file-' + f.name.replace(/[^a-zA-Z0-9]/g, '_');
                div.textContent = '[JSON] ' + f.name;
                fileList.appendChild(div);
            }});
            imageFiles.forEach(f => {{
                const div = document.createElement('div');
                div.className = 'file-item';
                div.id = 'file-' + f.name.replace(/[^a-zA-Z0-9]/g, '_');
                div.textContent = f.webkitRelativePath || f.name;
                fileList.appendChild(div);
            }});

            uploadBtn.style.display = totalFiles > 0 ? 'block' : 'none';
        }}

        folderInput.addEventListener('change', (e) => {{
            const allFiles = Array.from(e.target.files);

            if (pendingMode === 'json') {{
                // Accept .json files from the selected folder
                const picked = allFiles.filter(f => f.name.toLowerCase().endsWith('.json'));
                jsonFiles = jsonFiles.concat(picked);
                if (picked.length === 0) {{
                    subfolderInfo.textContent = 'No JSON files found in selected folder.';
                }} else {{
                    subfolderInfo.textContent = `Added ${{picked.length}} JSON file${{picked.length !== 1 ? 's' : ''}}.`;
                }}
            }} else {{
                // Accept image files from the selected folder
                const picked = allFiles.filter(f => IMAGE_TYPES.includes(f.type));
                imageFiles = imageFiles.concat(picked);
                if (picked.length === 0) {{
                    subfolderInfo.textContent = 'No images found in selected folder.';
                }} else {{
                    subfolderInfo.textContent = `Added ${{picked.length}} image${{picked.length !== 1 ? 's' : ''}}.`;
                }}
                // Show the JSON button after images are selected
                selectJsonBtn.style.display = 'flex';
            }}

            selectBtn.innerHTML = '&#128193; Add More Images';
            refreshUI();
            pendingMode = null;
        }});

        async function startUpload() {{
            selectBtn.disabled = true;
            selectJsonBtn.disabled = true;
            uploadBtn.style.display = 'none';
            progressSection.style.display = 'block';
            uploadedCount = 0;
            jsonUploadedCount = 0;
            errorCount = 0;

            // Upload JSON files first so sidecars are in place before images
            const allFiles = [...jsonFiles, ...imageFiles];
            const totalFiles = allFiles.length;

            for (let i = 0; i < totalFiles; i++) {{
                const file = allFiles[i];
                const isJson = file.name.toLowerCase().endsWith('.json');
                const pct = Math.round(((i + 1) / totalFiles) * 100);
                progressBarFill.style.width = pct + '%';
                const phase = isJson ? 'JSON' : 'image';
                progressText.textContent = `Uploading ${{phase}} ${{i + 1}} of ${{totalFiles}}...`;

                const fileEl = document.getElementById('file-' + file.name.replace(/[^a-zA-Z0-9]/g, '_'));

                try {{
                    const formData = new FormData();
                    formData.append('file', file);

                    const resp = await fetch(API_UPLOAD, {{
                        method: 'POST',
                        body: formData,
                    }});
                    const data = await resp.json();

                    if (data.status === 'ready' || data.status === 'json_archived' || data.archived_as) {{
                        if (isJson) {{
                            jsonUploadedCount++;
                        }} else {{
                            uploadedCount++;
                        }}
                        if (fileEl) fileEl.className = 'file-item done';
                    }} else {{
                        errorCount++;
                        if (fileEl) {{
                            fileEl.className = 'file-item error';
                            fileEl.textContent += ' (' + (data.error || 'error') + ')';
                        }}
                    }}
                }} catch (err) {{
                    errorCount++;
                    if (fileEl) {{
                        fileEl.className = 'file-item error';
                        fileEl.textContent += ' (network error)';
                    }}
                }}
            }}

            // Upload complete
            counterEl.textContent = uploadedCount;
            counterLabel.textContent = 'images imported';
            let summary = `Done! ${{uploadedCount}} image${{uploadedCount !== 1 ? 's' : ''}} imported`;
            if (jsonUploadedCount > 0) summary += `, ${{jsonUploadedCount}} JSON sidecar${{jsonUploadedCount !== 1 ? 's' : ''}}`;
            if (errorCount > 0) summary += `, ${{errorCount}} error${{errorCount !== 1 ? 's' : ''}}`;
            progressText.textContent = summary;
            progressBarFill.style.width = '100%';
            doneBtn.style.display = 'block';
        }}

        function onDone() {{
            document.getElementById('mainContent').style.display = 'none';
            const doneScreen = document.getElementById('doneScreen');
            doneScreen.style.display = 'block';
            let msg = uploadedCount + ' image' + (uploadedCount !== 1 ? 's' : '') + ' imported to the archive.';
            if (jsonUploadedCount > 0) msg += ' ' + jsonUploadedCount + ' JSON sidecar' + (jsonUploadedCount !== 1 ? 's' : '') + ' uploaded.';
            if (errorCount > 0) msg += ' ' + errorCount + ' error(s).';
            document.getElementById('doneSummary').textContent = msg;
        }}
    </script>
</body>
</html>'''
