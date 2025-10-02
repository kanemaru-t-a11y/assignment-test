"""
config.py
固定の文字列や数値をまとめる
"""
from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
import os

# 画面表示系
APP_TITLE = "Campus Guide AI"
DESCRIPTION = "学内情報検索機能を備えた教育向けAIアシスタントです。"
FOOTER_COPYRIGHT = "© 2025 Your Company. All Rights Reserved."
DATA_FOLDER = "data/"
CHAT_INPUT_PLACEHOLDER = "ここにメッセージを入力してください。"

# ログ
LOG_DIR = "./logs"
APP_LOGGER_NAME = "app_logger"
LOG_FILE = "app.log"
APP_START_MESSAGE = "アプリが正常に起動しました。"

# LLM
MODEL_NAME = "gpt-4o-mini"
MAX_TOKENS = 100
TOP_K = 8                 # まとめ系に効くよう広めに
TEMPERATURE = 0.5
VECTORSTORE_DIR = "./vectorstore"
EMBEDDING_MODEL_NAME = "text-embedding-ada-002"
CHUNK_OVERLAP = 50
CHUNK_SIZE = 500
CHUNK_SEPARATOR = "\n"

# RAGデータ
RAG_ROOT_PATH = "./data"
ALLOWED_EXTENSIONS = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".csv": lambda path: CSVLoader(path, encoding="utf-8"),
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
}

# --- フォルダ判定用キー（パスの一部に含めてください） ---
FOLDER_KEY_FACULTY = "faculty"     # ./data/faculty/...
FOLDER_KEY_DEPARTMENT = "department"  # ./data/department/...
FOLDER_KEY_RESEARCH = "research"    # ./data/research/...
FOLDER_KEY_CAMPUS = "campus"      # ./data/campus/...

# Web取り込み（任意）
USE_WEB_SOURCES = False
WEB_URLS = []
CRAWL_USER_AGENT = os.getenv(
    "USER_AGENT", "CampusGuideBot/1.0 (+https://example.com)")

# 会話履歴 保存/読み込み
HISTORY_DIR = "./histories"
AUTOSAVE_HISTORY = True
MAX_HISTORY_MESSAGES = 50   # 保存上限（画面表示はhelpers側）

# メッセージ
ERROR_MSG_GENERAL = "エラーが発生しました。再度お試しください。解決しない場合は管理者へお問い合わせください。"
ERROR_MSG_INIT_FAILED = "初期化に失敗しました。アプリを再起動してください。解決しない場合は管理者へお問い合わせください。"
ERROR_MSG_NO_DOCUMENT_FOUND = "該当する情報が見つかりませんでした。検索条件を変更して再度お試しください。"
ERROR_MSG_CONVERSATION_LOG_FAILED = "会話ログの保存に失敗しました。再度お試しください。解決しない場合は管理者にお問い合わせください。"
ERROR_MSG_LLM_RESPONSE_FAILED = "回答生成に失敗しました。再度お試しください。解決しない場合は管理者にお問い合わせください。"
ERROR_MSG_DISPLAY_ANSWER_FAILED = "回答表示に失敗しました。再度お試しください。解決しない場合は管理者にお問い合わせください。"
