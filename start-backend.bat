@echo off
set WEBUI_SECRET_KEY=%WEBUI_SECRET_KEY%
set DATA_DIR=C:\DbizProjects\ai-dev\TG\data-tg
set ENABLE_SIGNUP=true
set OFFLINE_MODE=true
set HF_HUB_OFFLINE=1
set RAG_EMBEDDING_MODEL_AUTO_UPDATE=false
set RAG_RERANKING_MODEL_AUTO_UPDATE=false
set WHISPER_MODEL_AUTO_UPDATE=false
set ENABLE_OLLAMA_API=false
set ENABLE_OPENAI_API=false
set CORS_ALLOW_ORIGIN=*
cd /d C:\DbizProjects\ai-dev\TG\open-webui\backend
..\.venv-tg\Scripts\python.exe -m uvicorn open_webui.main:app --port 8080
